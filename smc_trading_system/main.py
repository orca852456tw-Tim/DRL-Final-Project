import sys
import os
import logging
import pandas as pd
import pandas_ta as ta
import yfinance as yf

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import TICKER, START_DATE, END_DATE, INITIAL_CAPITAL, CURRENT_RISK_PROFILE
from src.data_module import DataModule
from src.smc_detection import SMCDetection
from src.signal_gen import SignalGenerator
from src.risk_filter import RiskFilter
from src.report_module import ReportModule
from utils.logger import setup_logger

logger = setup_logger("Main")

def main():
    logger.info("Starting SMC Trading System Backtest...")
    
    # 強制將輸出紀錄到 report_output.md，並指定 utf-8 編碼以避免中文亂碼
    file_handler = logging.FileHandler('report_output.md', mode='w', encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(message)s'))
    logging.getLogger().addHandler(file_handler)
    
    data_mod = DataModule(TICKER, START_DATE, END_DATE)
    
    # 由於 yfinance 免費 API 限制 5m 資料只能抓 60 天
    # 為了執行長達 4 年 (2021~2024) 的回測，我們在此將 LTF 降級為 1D，HTF 設定為 1W。
    logger.info(f"Fetching 1D data from {START_DATE} to {END_DATE} for 4-year backtest...")
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
    
    # 2. SMC Detection Module
    smc_mod = SMCDetection()
    tf_data_with_features = smc_mod.process_all_timeframes(tf_data)
    
    # 3. Calculate ATR on LTF (1D)
    ltf = tf_data_with_features['1D']
    ltf.ta.atr(length=14, append=True)
    atr_col = ltf.columns[-1] # pandas-ta appends as 'ATRr_14'
    
    # 4. Signal Generation
    signal_gen = SignalGenerator()
    htf = tf_data_with_features['1W']
    
    signals = signal_gen.generate_signals(htf, ltf)
    logger.info(f"Generated {len(signals)} raw BUY signals.")
    
    from config import RISK_SETTINGS
    
    # 5. Risk Filter & Trade Execution Simulation (Multi-Scenario)
    report_mod = ReportModule()
    
    for profile_name in RISK_SETTINGS.keys():
        logger.info(f"\n========== [{profile_name}] 績效報告 ==========")
        risk_filter = RiskFilter(profile_name)
        trade_log = []
        account_balance = INITIAL_CAPITAL
        
        active_trade = False
        
        for sig in signals:
            if active_trade:
                continue # 不允許同時持有多筆單
                
            entry_date = sig['date']
            entry_price = float(sig['entry'])
            stop_loss_zone = float(sig['stop_loss'])
            
            # Get ATR at entry
            atr_value = float(ltf.loc[entry_date, atr_col])
            if pd.isna(atr_value):
                atr_value = 0.0
                
            pos_info = risk_filter.calculate_position(account_balance, entry_price, stop_loss_zone, atr_value)
            shares = pos_info['shares']
            final_stop_loss = pos_info['final_stop_loss']
            
            if shares <= 0:
                continue
                
            take_profit = float(sig['target_tp'])
            
            active_trade = True
            logger.debug(f"Entering Trade on {entry_date} at {entry_price}, Stop: {final_stop_loss}, TP: {take_profit}, Shares: {shares}")
            
            # Walk forward to find exit
            trade_closed = False
            start_idx = ltf.index.get_loc(entry_date)
            for i in range(start_idx + 1, len(ltf)):
                bar = ltf.iloc[i]
                exit_date = ltf.index[i]
                
                # Check Stop Loss
                if bar['Low'] <= final_stop_loss:
                    exit_price = final_stop_loss
                    pnl = (exit_price - entry_price) * shares
                    return_pct = pnl / account_balance
                    account_balance += pnl
                    trade_log.append({
                        'entry_date': entry_date, 'exit_date': exit_date,
                        'entry_price': entry_price, 'exit_price': exit_price,
                        'shares': shares, 'pnl': pnl, 'return_pct': return_pct,
                        'balance': account_balance, 'result': 'LOSS',
                        'zone_top': sig['zone_top'], 'zone_bottom': sig['zone_bottom'],
                        'reclaim_price': sig['reclaim_price'], 'stop_loss_price': final_stop_loss,
                        'take_profit_price': take_profit, 'risk_pct': risk_filter.risk_pct,
                        'has_sweep': sig['has_sweep']
                    })
                    trade_closed = True
                    break
                    
                # Check Take Profit
                elif bar['High'] >= take_profit:
                    exit_price = take_profit
                    pnl = (exit_price - entry_price) * shares
                    return_pct = pnl / account_balance
                    account_balance += pnl
                    trade_log.append({
                        'entry_date': entry_date, 'exit_date': exit_date,
                        'entry_price': entry_price, 'exit_price': exit_price,
                        'shares': shares, 'pnl': pnl, 'return_pct': return_pct,
                        'balance': account_balance, 'result': 'WIN',
                        'zone_top': sig['zone_top'], 'zone_bottom': sig['zone_bottom'],
                        'reclaim_price': sig['reclaim_price'], 'stop_loss_price': final_stop_loss,
                        'take_profit_price': take_profit, 'risk_pct': risk_filter.risk_pct,
                        'has_sweep': sig['has_sweep']
                    })
                    trade_closed = True
                    break
                    
            if not trade_closed:
                # End of data, close at last price
                exit_price = float(ltf.iloc[-1]['Close'])
                exit_date = ltf.index[-1]
                pnl = (exit_price - entry_price) * shares
                return_pct = pnl / account_balance
                account_balance += pnl
                trade_log.append({
                    'entry_date': entry_date, 'exit_date': exit_date,
                    'entry_price': entry_price, 'exit_price': exit_price,
                    'shares': shares, 'pnl': pnl, 'return_pct': return_pct,
                    'balance': account_balance, 'result': 'END',
                    'zone_top': sig['zone_top'], 'zone_bottom': sig['zone_bottom'],
                    'reclaim_price': sig['reclaim_price'], 'stop_loss_price': final_stop_loss,
                    'take_profit_price': take_profit, 'risk_pct': risk_filter.risk_pct,
                    'has_sweep': sig['has_sweep']
                })
            active_trade = False

        # 6. Report
        metrics = report_mod.generate_report(trade_log, INITIAL_CAPITAL)
    
    # 7. Plotting
    from src.plot_module import plot_trade_chart
    from datetime import timedelta
    
    if trade_log:
        logger.info("Generating Backtest Chart...")
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
                
        plot_trade_chart(plot_df, trade_log, zones)
        logger.info("Chart saved to backtest_result.html")

if __name__ == "__main__":
    main()
