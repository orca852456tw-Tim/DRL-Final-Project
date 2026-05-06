import pandas as pd
import numpy as np
from typing import List, Dict, Any
from utils.logger import setup_logger

logger = setup_logger(__name__)

class ReportModule:
    def __init__(self):
        pass

    def calculate_cagr(self, start_capital: float, end_capital: float, years: float) -> float:
        """Calculate Compound Annual Growth Rate."""
        if start_capital <= 0 or years <= 0:
            return 0.0
        return (max(end_capital / start_capital, 0) ** (1 / years)) - 1

    def run_monte_carlo(self, win_rate: float, avg_win_pct: float, avg_loss_pct: float, trades_per_year: int, years: int = 3, simulations: int = 1000) -> Dict[str, float]:
        """Run Monte Carlo simulation for future performance."""
        logger.info(f"Running Monte Carlo simulation for {years} years...")
        np.random.seed(42) # For reproducibility
        
        results = []
        for _ in range(simulations):
            capital = 1.0 # Start with 1.0 as base multiplier
            total_trades = trades_per_year * years
            
            # Generate random results based on win rate
            random_draws = np.random.rand(total_trades)
            for draw in random_draws:
                if draw < win_rate:
                    capital *= (1 + avg_win_pct)
                else:
                    capital *= (1 - abs(avg_loss_pct))
            results.append(capital)
            
        results = np.array(results)
        
        # Calculate percentiles
        best = np.percentile(results, 95)
        median = np.median(results)
        worst = np.percentile(results, 5)
        
        return {
            'best_case_95th': best,
            'expected_50th': median,
            'worst_case_5th': worst
        }

    def generate_report(self, trade_log: List[Dict[str, Any]], initial_capital: float, hide_ledger: bool = False) -> Dict[str, float]:
        """
        Calculate metrics like Total Return, MDD, Win Rate, Sharpe Ratio.
        """
        logger.info("Generating performance report...")
        if not trade_log:
            logger.warning("No trades executed.")
            return {'Total Return (%)': 0.0, 'Win Rate (%)': 0.0, 'MDD (%)': 0.0, 'Sharpe Ratio': 0.0, 'Total Trades': 0}

        if not hide_ledger:
            logger.info("\n=== Detailed Trade Ledger ===")
            for idx, trade in enumerate(trade_log, 1):
                entry_date_str = trade['entry_date'].strftime('%Y-%m-%d') if hasattr(trade['entry_date'], 'strftime') else str(trade['entry_date'])
                exit_date_str = trade['exit_date'].strftime('%Y-%m-%d') if hasattr(trade['exit_date'], 'strftime') else str(trade['exit_date'])
                
                entry_price = round(trade['entry_price'], 2)
                exit_price = round(trade['exit_price'], 2)
                
                shares = trade['shares']
                ret_pct = round(trade['return_pct'] * 100, 2)
                risk_pct = round(trade.get('risk_pct', 0.01) * 100, 2)
                
                zone_top = round(trade.get('zone_top', 0), 2)
                zone_bottom = round(trade.get('zone_bottom', 0), 2)
                reclaim_price = round(trade.get('reclaim_price', 0), 2)
                stop_loss_price = round(trade.get('stop_loss_price', 0), 2)
                take_profit_price = round(trade.get('take_profit_price', 0), 2)

                if trade['result'] == 'WIN':
                    reason_str = f"達到動態停利目標 (前高 {take_profit_price}) 觸發 Take Profit。"
                elif trade['result'] == 'LOSS':
                    reason_str = f"跌破需求區底線 [{stop_loss_price}] 觸發強制停損。"
                else:
                    reason_str = "回測結束強制作平倉。"
                    
                logger.info(f"\n---")
                logger.info(f"Trade #{idx} | {entry_date_str}")
                sweep_msg = "，觸發流動性掃蕩 (Liquidity Sweep)" if trade.get('has_sweep', False) else ""
                logger.info(f"【買進理由】價格進入大級別需求區 [{zone_top}-{zone_bottom}]{sweep_msg} 並完成收復確認 (突破前高 {reclaim_price})。")
                logger.info(f"【進場資訊】價格：{entry_price} | 股數：{shares} | 風險：{risk_pct}%")
                logger.info(f"【出場資訊】{exit_date_str} | 價格：{exit_price} | 報酬：{ret_pct}%")
                logger.info(f"【賣出理由】{reason_str}")
            logger.info("---")

        df = pd.DataFrame(trade_log)
        
        final_balance = df['balance'].iloc[-1]
        total_return = (final_balance - initial_capital) / initial_capital * 100
        
        winning_trades = df[df['pnl'] > 0]
        win_rate = (len(winning_trades) / len(df)) * 100
        
        balances = [initial_capital] + df['balance'].tolist()
        balance_series = pd.Series(balances)
        rolling_max = balance_series.cummax()
        drawdown = (balance_series - rolling_max) / rolling_max
        mdd = drawdown.min() * 100
        
        returns = df['return_pct']
        sharpe = 0.0
        risk_free_rate = 0.02
        if returns.std() != 0:
            # Simple Sharpe Ratio with 0.02 risk free rate
            sharpe = ((returns.mean() - risk_free_rate) / returns.std()) * np.sqrt(len(df))
            
        report = {
            'Total Trades': len(df),
            'Total Return (%)': round(total_return, 2),
            'Win Rate (%)': round(win_rate, 2),
            'MDD (%)': round(mdd, 2),
            'Sharpe Ratio': round(sharpe, 2)
        }
        
        report_text = (
            f"\n--- Performance Report ---\n"
            f"Total Trades: {report['Total Trades']}\n"
            f"Total Return: {report['Total Return (%)']}%\n"
            f"Win Rate: {report['Win Rate (%)']}%\n"
            f"MDD: {report['MDD (%)']}%\n"
            f"Sharpe Ratio: {report['Sharpe Ratio']}\n"
            f"--------------------------"
        )
        logger.info(report_text)
        return report
