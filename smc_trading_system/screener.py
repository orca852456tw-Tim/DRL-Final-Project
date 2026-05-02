import sys
import os
import pandas as pd
import pandas_ta as ta
import yfinance as yf
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import WATCHLIST
from src.smc_detection import SMCDetection
from src.signal_gen import SignalGenerator
from utils.logger import setup_logger

logger = setup_logger("Screener")

import logging

def main():
    # 強制將雷達輸出紀錄到 screener_output.md，並指定 utf-8 編碼
    file_handler = logging.FileHandler('screener_output.md', mode='w', encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(message)s'))
    logging.getLogger().addHandler(file_handler)

    logger.info("Starting Multi-Asset SMC Screener...")
    logger.info(f"Watchlist: {WATCHLIST}")
    
    # 針對終端機輸出修正編碼 (相容 Windows)
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    
    logger.info("=" * 60)
    logger.info("今日 SMC 掃描雷達報告")
    logger.info("=" * 60)
    
    found_targets = False
    
    for ticker in WATCHLIST:
        logger.info(f"Scanning {ticker}...")
        try:
            # Download 1 year of daily data to ensure HTF swings form correctly
            df_1d = yf.download(ticker, period="1y", interval="1d", progress=False)
            if df_1d.empty:
                logger.warning(f"No data fetched for {ticker}. Skipping.")
                continue
                
            if isinstance(df_1d.columns, pd.MultiIndex):
                df_1d.columns = df_1d.columns.get_level_values(0)
                
            df_1d = df_1d.dropna()
            
            # Form weekly data
            resample_dict = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
            df_1w = df_1d.resample('W-FRI').agg(resample_dict).dropna()
            
            tf_data = {'1W': df_1w, '1D': df_1d}
            
            # Run SMC Feature Detection
            smc_mod = SMCDetection()
            tf_data_with_features = smc_mod.process_all_timeframes(tf_data)
            
            # Generate Signals
            signal_gen = SignalGenerator()
            htf = tf_data_with_features['1W']
            ltf = tf_data_with_features['1D']
            
            signals = signal_gen.generate_signals(htf, ltf)
            
            if signals:
                last_sig = signals[-1]
                last_sig_date = last_sig['date']
                
                # Get the last 5 trading days in the dataframe
                recent_dates = ltf.index[-5:]
                
                if last_sig_date in recent_dates:
                    found_targets = True
                    zone_top = round(last_sig['zone_top'], 2)
                    zone_bottom = round(last_sig['zone_bottom'], 2)
                    reclaim = round(last_sig['reclaim_price'], 2)
                    entry_price = round(last_sig['entry'], 2)
                    tp = round(last_sig['target_tp'], 2)
                    sl = round(last_sig['stop_loss'], 2)
                    
                    name_map = {
                        '2330.TW': '台積電',
                        '2317.TW': '鴻海',
                        '2454.TW': '聯發科',
                        '2308.TW': '台達電',
                        '2881.TW': '富邦金'
                    }
                    ticker_name = name_map.get(ticker, ticker)
                    
                    logger.info(f"\n[!!! 狙擊目標 !!!] {ticker} {ticker_name} - 已完成 Sweep 與 Reclaim")
                    logger.info(f"   => 觸發日期：{last_sig_date.strftime('%Y-%m-%d')}")
                    logger.info(f"   => 狀態：價格位於大級別需求區 [{zone_top}-{zone_bottom}]")
                    sweep_msg = "是" if last_sig.get('has_sweep') else "否"
                    logger.info(f"   => 流動性掃蕩 (Sweep)：{sweep_msg}")
                    logger.info(f"   => 建議進場價：{entry_price}")
                    logger.info(f"   => 動態停利目標：{tp}")
                    logger.info(f"   => 結構停損點：{sl}")
                    
        except Exception as e:
            logger.error(f"Error processing {ticker}: {e}")
            
    if not found_targets:
        logger.info("\n目前無符合「高勝率 SMC 共振」之狙擊目標。")
        
    logger.info("\n" + "=" * 60)

if __name__ == "__main__":
    main()
