import pandas as pd
import numpy as np
from scipy.signal import argrelextrema
from typing import Dict
from utils.logger import setup_logger

logger = setup_logger(__name__)

class SMCDetection:
    def __init__(self, fvg_threshold: float = 0.002):
        self.fvg_threshold = fvg_threshold
        
    def detect_fvg(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect FVG and mark them in the dataframe.
        """
        logger.info("Detecting FVG...")
        df['bullish_fvg'] = None
        
        shift2_high = df['High'].shift(2)
        shift2_close = df['Close'].shift(2)
        low = df['Low']

        shift2_close_safe = shift2_close.replace(0, np.nan)
        fvg_cond = (low > shift2_high) & ((low - shift2_high) / shift2_close_safe >= self.fvg_threshold)
        
        for i in df[fvg_cond].index:
            df.at[i, 'bullish_fvg'] = [low.loc[i], shift2_high.loc[i]]
            
        return df

    def detect_swing_high_low(self, df: pd.DataFrame, window: int = 5) -> pd.DataFrame:
        """
        Detect Swing Highs and Lows.
        """
        logger.info("Detecting Swing High/Low...")
        df['swing_high'] = False
        df['swing_low'] = False
        
        # argrelextrema expects numpy array
        high_peaks = argrelextrema(df['High'].values, np.greater, order=window)[0]
        low_peaks = argrelextrema(df['Low'].values, np.less, order=window)[0]
        
        df.loc[df.index[high_peaks], 'swing_high'] = True
        df.loc[df.index[low_peaks], 'swing_low'] = True
        
        return df
        
    def detect_demand_supply_zones(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect Demand and Supply Zones based on BOS.
        """
        logger.info("Detecting Demand/Supply Zones...")
        df['demand_zone'] = None
        df['supply_zone'] = None
        
        last_swing_high = None
        for i in range(len(df)):
            if df['swing_high'].iloc[i]:
                last_swing_high = df['High'].iloc[i]
                
            # Upward BOS
            if last_swing_high is not None and df['Close'].iloc[i] > last_swing_high:
                # Find last red K-line
                for j in range(i-1, -1, -1):
                    if df['Close'].iloc[j] < df['Open'].iloc[j]:
                        # List of [Top, Bottom]
                        df.at[df.index[i], 'demand_zone'] = [df['High'].iloc[j], df['Low'].iloc[j]]
                        break
                # Reset to avoid continuous BOS from the same swing high
                last_swing_high = None
                
        return df
        
    def detect_liquidity_sweep(self, df: pd.DataFrame, window: int = 5) -> pd.DataFrame:
        logger.info("Detecting Liquidity Sweep...")
        df['bullish_liquidity_sweep'] = False
        
        last_sl = pd.Series(np.nan, index=df.index)
        swing_low_indices = df[df['swing_low']].index
        
        for idx in swing_low_indices:
            loc = df.index.get_loc(idx)
            confirm_loc = min(loc + window, len(df) - 1)
            confirm_idx = df.index[confirm_loc]
            last_sl.iloc[confirm_loc:] = df.at[idx, 'Low']
            
        df['last_swing_low'] = last_sl
        
        # Condition 1: Low is below last_swing_low in recent bars
        sweep_0 = df['Low'] < df['last_swing_low']
        sweep_1 = df['Low'].shift(1) < df['last_swing_low']
        sweep_2 = df['Low'].shift(2) < df['last_swing_low']
        
        # Condition 2: Close reclaims last_swing_low
        reclaimed = df['Close'] >= df['last_swing_low']
        
        df.loc[reclaimed & (sweep_0 | sweep_1 | sweep_2), 'bullish_liquidity_sweep'] = True
        return df

    def process_all_timeframes(self, tf_data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        logger.info("Running SMC Detection on all timeframes")
        processed_data = {}
        for tf, df in tf_data.items():
            df = df.copy()
            df = self.detect_fvg(df)
            df = self.detect_swing_high_low(df, window=5)
            df = self.detect_liquidity_sweep(df, window=5)
            df = self.detect_demand_supply_zones(df)
            processed_data[tf] = df
            
        return processed_data
