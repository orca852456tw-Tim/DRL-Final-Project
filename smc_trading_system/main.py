import sys
import os
import logging
import numpy as np
import pandas as pd
import pandas_ta as ta
import yfinance as yf
from stable_baselines3 import DQN

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import TICKER, START_DATE, END_DATE, INITIAL_CAPITAL
from src.data_module import DataModule
from src.smc_detection import SMCDetection
from src.risk_filter import RiskFilter
from src.report_module import ReportModule
from utils.logger import setup_logger

logger = setup_logger("Main")

def main():
    logger.info("Starting DRL SMC Trading System Backtest...")
    
    file_handler = logging.FileHandler('report_output.md', mode='w', encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(message)s'))
    logging.getLogger().addHandler(file_handler)
    
    data_mod = DataModule(TICKER, START_DATE, END_DATE)
    
    logger.info(f"Fetching 1D data from {START_DATE} to {END_DATE} for backtest...")
    df_1d = yf.download(data_mod.ticker, start=START_DATE, end=END_DATE, interval="1d", progress=False)
    if df_1d.empty:
        logger.error("Failed to fetch 1D data. Exiting.")
        return
        
    if isinstance(df_1d.columns, pd.MultiIndex):
        df_1d.columns = df_1d.columns.get_level_values(0)
        
    df_1d = df_1d.dropna()
    resample_dict = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
    df_1w = df_1d.resample('W-FRI').agg(resample_dict).dropna()
    
    tf_data = {'1W': df_1w, '1D': df_1d}
    
    # SMC Detection Module
    smc_mod = SMCDetection()
    tf_data_with_features = smc_mod.process_all_timeframes(tf_data)
    
    ltf = tf_data_with_features['1D']
    ltf.ta.atr(length=14, append=True)
    atr_col = ltf.columns[-1]
    
    htf = tf_data_with_features['1W']

    # Load DQN Model
    model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "dqn_smc_model.zip")
    if not os.path.exists(model_path):
        logger.error("DQN model not found. Please train first.")
        return
    model = DQN.load(model_path)
    
    active_zone = None
    trade_log = []
    buy_observations = []
    account_balance = INITIAL_CAPITAL
    active_trade = False
    
    report_mod = ReportModule()
    
    action_to_profile = {
        1: '保守型',
        2: '穩健型',
        3: '積極型'
    }
    
    logger.info("Executing DQN Inference...")
    
    for i in range(len(ltf)):
        current_date = ltf.index[i]
        bar = ltf.iloc[i]
        
        past_htf = htf[htf.index <= current_date]
        if not past_htf.empty:
            for j in range(len(past_htf)-1, -1, -1):
                if past_htf['demand_zone'].iloc[j] is not None:
                    active_zone = past_htf['demand_zone'].iloc[j]
                    break
                    
        close_p = bar['Close']
        if active_zone:
            d_top = (close_p - active_zone[0]) / close_p
            d_bottom = (close_p - active_zone[1]) / close_p
        else:
            d_top = 0.0
            d_bottom = 0.0
            
        fvg_flag = 1.0 if bar.get('bullish_fvg') is not None else 0.0
        sweep_flag = 1.0 if bar.get('bullish_liquidity_sweep') else 0.0
        atr_raw = bar.get(atr_col, 0.0)
        atr_val = 0.0 if pd.isna(atr_raw) else float(atr_raw)
        atr_norm = atr_val / close_p if close_p != 0 and atr_val != 0.0 else 0.0
        
        obs = np.array([d_top, d_bottom, fvg_flag, sweep_flag, atr_norm], dtype=np.float32)
        
        if not active_trade:
            action, _ = model.predict(obs, deterministic=True)
            action = int(action.item() if hasattr(action, 'item') else action)
            
            if action in [1, 2, 3]:
                buy_observations.append(obs.tolist())
                profile = action_to_profile[action]
                risk_filter = RiskFilter(profile)
                
                entry_price = float(close_p)
                stop_loss_zone = float(active_zone[1]) if active_zone else float(entry_price * 0.95)
                
                pos_info = risk_filter.calculate_position(account_balance, entry_price, stop_loss_zone, float(atr_val))
                shares = pos_info['shares']
                final_stop_loss = pos_info['final_stop_loss']
                
                if shares > 0:
                    risk_amount = entry_price - final_stop_loss
                    take_profit = entry_price + (risk_amount * 2)
                    
                    active_trade = True
                    entry_trade_info = {
                        'entry_date': current_date,
                        'entry_price': entry_price,
                        'shares': shares,
                        'stop_loss_price': final_stop_loss,
                        'take_profit_price': take_profit,
                        'zone_top': active_zone[0] if active_zone else entry_price,
                        'zone_bottom': active_zone[1] if active_zone else entry_price,
                        'reclaim_price': entry_price,
                        'risk_pct': risk_filter.risk_pct,
                        'has_sweep': bool(sweep_flag),
                        'profile': profile
                    }
        else:
            if bar['Low'] <= entry_trade_info['stop_loss_price']:
                exit_price = entry_trade_info['stop_loss_price']
                pnl = (exit_price - entry_trade_info['entry_price']) * entry_trade_info['shares']
                return_pct = pnl / account_balance
                account_balance += pnl
                entry_trade_info.update({
                    'exit_date': current_date, 'exit_price': exit_price, 'pnl': pnl, 'return_pct': return_pct,
                    'balance': account_balance, 'result': 'LOSS'
                })
                trade_log.append(entry_trade_info)
                active_trade = False
            elif bar['High'] >= entry_trade_info['take_profit_price']:
                exit_price = entry_trade_info['take_profit_price']
                pnl = (exit_price - entry_trade_info['entry_price']) * entry_trade_info['shares']
                return_pct = pnl / account_balance
                account_balance += pnl
                entry_trade_info.update({
                    'exit_date': current_date, 'exit_price': exit_price, 'pnl': pnl, 'return_pct': return_pct,
                    'balance': account_balance, 'result': 'WIN'
                })
                trade_log.append(entry_trade_info)
                active_trade = False
                
    if active_trade:
        exit_price = float(ltf.iloc[-1]['Close'])
        pnl = (exit_price - entry_trade_info['entry_price']) * entry_trade_info['shares']
        return_pct = pnl / account_balance
        account_balance += pnl
        entry_trade_info.update({
            'exit_date': ltf.index[-1], 'exit_price': exit_price, 'pnl': pnl, 'return_pct': return_pct,
            'balance': account_balance, 'result': 'END'
        })
        trade_log.append(entry_trade_info)

    metrics = report_mod.generate_report(trade_log, INITIAL_CAPITAL)
    
    if trade_log:
        df_trades = pd.DataFrame(trade_log)
        win_trades = df_trades[df_trades['result'] == 'WIN']
        loss_trades = df_trades[df_trades['result'] == 'LOSS']
        
        avg_win_pct = win_trades['return_pct'].mean() if not win_trades.empty else 0.0
        avg_loss_pct = loss_trades['return_pct'].mean() if not loss_trades.empty else 0.0
        win_rate_pct = metrics.get('Win Rate (%)', 0.0)
        win_rate = win_rate_pct / 100.0
        mdd = metrics.get('MDD (%)', 0.0)
        total_return = metrics.get('Total Return (%)', 0.0)
        
        backtest_years = (ltf.index[-1] - ltf.index[0]).days / 365.25
        cagr = report_mod.calculate_cagr(INITIAL_CAPITAL, account_balance, backtest_years)
        trades_per_year = int(len(trade_log) / backtest_years) if backtest_years > 0 else 0
        
        mc_results = report_mod.run_monte_carlo(win_rate, avg_win_pct, avg_loss_pct, trades_per_year, years=3, simulations=1000)
    else:
        cagr = 0.0
        mc_results = {'best_case_95th': 0, 'expected_50th': 0, 'worst_case_5th': 0}
        win_rate_pct = 0.0
        mdd = 0.0
        total_return = 0.0

    if buy_observations:
        avg_obs = np.mean(buy_observations, axis=0)
        radar_features = [
            float(min(100, max(0, avg_obs[0] * 1000))), # D_top
            float(min(100, max(0, avg_obs[1] * 1000))), # D_bottom
            float(min(100, max(0, avg_obs[2] * 100))),  # FVG
            float(min(100, max(0, avg_obs[3] * 100))),  # Sweep
            float(min(100, max(0, avg_obs[4] * 2000)))  # ATR
        ]
    else:
        radar_features = [0, 0, 0, 0, 0]

    import json
    stats_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "training_stats.json")
    if os.path.exists(stats_file):
        with open(stats_file, 'r') as f:
            stats = json.load(f)
            avg_rewards = stats.get("avg_rewards_7_stages", [])
            loss_curve = stats.get("loss_curve", [])
    else:
        avg_rewards = []
        loss_curve = []

    from src.plot_module import generate_xai_dashboard_html
    from datetime import timedelta
    
    if trade_log:
        logger.info("Generating HTML Dashboard...")
        first_trade = trade_log[0]['entry_date']
        last_trade = trade_log[-1]['exit_date']
        
        start_plot_date = first_trade - timedelta(days=20)
        end_plot_date = last_trade + timedelta(days=20)
        
        plot_df = ltf[(ltf.index >= start_plot_date) & (ltf.index <= end_plot_date)]
        
        zones = []
        for t in trade_log:
            zone = [t['zone_top'], t['zone_bottom']]
            if zone not in zones:
                zones.append(zone)
                
        generate_xai_dashboard_html(plot_df, trade_log, zones, "DQN AI Agent", cagr, mc_results, win_rate_pct, mdd, total_return, radar_features, avg_rewards, loss_curve)
        logger.info("Dashboard saved to drl_xai_dashboard.html")

if __name__ == "__main__":
    main()
