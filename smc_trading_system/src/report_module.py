import pandas as pd
import numpy as np
from typing import List, Dict, Any
from utils.logger import setup_logger

logger = setup_logger(__name__)

class ReportModule:
    def __init__(self):
        pass

    def generate_report(self, trade_log: List[Dict[str, Any]], initial_capital: float) -> Dict[str, float]:
        """
        Calculate metrics like Total Return, MDD, Win Rate, Sharpe Ratio.
        """
        logger.info("Generating performance report...")
        if not trade_log:
            logger.warning("No trades executed.")
            return {'Total Return (%)': 0.0, 'Win Rate (%)': 0.0, 'MDD (%)': 0.0, 'Sharpe Ratio': 0.0, 'Total Trades': 0}

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
