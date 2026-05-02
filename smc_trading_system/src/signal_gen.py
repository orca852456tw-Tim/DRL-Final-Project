import pandas as pd
from typing import Dict, Any, List
from utils.logger import setup_logger

logger = setup_logger(__name__)

class SignalGenerator:
    def __init__(self):
        self.state = 0 # 0: Neutral, 1: Mitigation
        self.has_sweep = False

    def generate_signals(self, htf_df: pd.DataFrame, ltf_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Generate trading signals based on SMC state machine.
        """
        logger.info("Generating signals...")
        signals = []
        
        active_demand_zone = None
        
        for i in range(1, len(ltf_df)):
            current_bar = ltf_df.iloc[i]
            prev_bar = ltf_df.iloc[i-1]
            date = ltf_df.index[i]
            
            # Find active demand zone from HTF
            htf_past = htf_df[htf_df.index <= date]
            if not htf_past.empty:
                dz_series = htf_past['demand_zone'].dropna()
                if not dz_series.empty:
                    active_demand_zone = dz_series.iloc[-1]
            
            if active_demand_zone is None:
                continue
                
            zone_top, zone_bottom = active_demand_zone
            
            if self.state == 0:
                # Check for Mitigation (enter zone)
                if current_bar['Low'] <= zone_top and current_bar['Low'] >= zone_bottom:
                    self.state = 1
                    self.has_sweep = current_bar.get('bullish_liquidity_sweep', False)
                    logger.debug(f"State 0 -> 1 (Mitigation) at {date}, Low={current_bar['Low']}")
            
            elif self.state == 1:
                if current_bar.get('bullish_liquidity_sweep', False):
                    self.has_sweep = True
                    
                # Zone broken
                if current_bar['Low'] < zone_bottom:
                    self.state = 0
                    self.has_sweep = False
                    logger.debug(f"State 1 -> 0 (Zone Broken) at {date}")
                    continue
                    
                # Reclaim (Close > Prev High) -> BUY
                if current_bar['Close'] > prev_bar['High'] and self.has_sweep:
                    
                    target_tp = None
                    for j in range(i, -1, -1):
                        if ltf_df['swing_high'].iloc[j]:
                            sh_price = ltf_df['High'].iloc[j]
                            if not (ltf_df['Close'].iloc[j:i+1] > sh_price).any():
                                target_tp = sh_price
                                break
                    
                    if target_tp is None or target_tp <= current_bar['Close']:
                        target_tp = current_bar['Close'] + 2 * (current_bar['Close'] - zone_bottom)
                        
                    self.state = 0 # Reset after triggering buy
                    self.has_sweep = False
                    logger.info(f"BUY Signal Triggered at {date}")
                    signals.append({
                        'action': 'BUY',
                        'date': date,
                        'entry': current_bar['Close'],
                        'stop_loss': zone_bottom,
                        'zone_top': zone_top,
                        'zone_bottom': zone_bottom,
                        'reclaim_price': prev_bar['High'],
                        'target_tp': target_tp,
                        'has_sweep': True
                    })
                    
        return signals
