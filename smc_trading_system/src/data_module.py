import pandas as pd
import yfinance as yf
from typing import Dict
from utils.logger import setup_logger

logger = setup_logger(__name__)

class DataModule:
    def __init__(self, ticker: str, start_date: str, end_date: str):
        # Ensure .TW is appended for Taiwan stocks if not present
        self.ticker = ticker if '.TW' in ticker else f"{ticker}.TW"
        self.start_date = start_date
        self.end_date = end_date

    def fetch_and_resample(self) -> Dict[str, pd.DataFrame]:
        """
        Fetch data using yfinance and perform Multi-Timeframe resampling.
        Returns a dict of DataFrames for different timeframes.
        """
        logger.info(f"Fetching data for {self.ticker}...")
        
        # We fetch 1mo 5m data for testing purposes as specified
        df_5m = yf.download(self.ticker, period="1mo", interval="5m", progress=False)
        if df_5m.empty:
            logger.warning("Empty data returned from yfinance")
            return {}

        # yfinance returns MultiIndex columns sometimes, flatten it
        if isinstance(df_5m.columns, pd.MultiIndex):
            df_5m.columns = df_5m.columns.get_level_values(0)
            
        df_5m.index = df_5m.index.tz_convert('Asia/Taipei')
        
        # Filter trading hours (09:00 - 13:30)
        df_5m = df_5m.between_time('09:00', '13:30')
        
        # Resampling dictionary
        resample_dict = {
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }
        
        # Resampling
        df_1h = df_5m.resample('1h', closed='left', label='left').agg(resample_dict).dropna()
        df_2h = df_5m.resample('2h', closed='left', label='left').agg(resample_dict).dropna()
        df_4h = df_5m.resample('4h', closed='left', label='left').agg(resample_dict).dropna()
        df_1d = df_5m.resample('D').agg(resample_dict).dropna()
        df_1w = df_1d.resample('W-FRI').agg(resample_dict).dropna()
        
        return {
            '1W': df_1w,
            '1D': df_1d,
            '4H': df_4h,
            '2H': df_2h,
            '1H': df_1h
        }
