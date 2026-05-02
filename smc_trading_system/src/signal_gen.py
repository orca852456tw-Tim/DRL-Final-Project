import pandas as pd
from typing import Dict, Any, List
from utils.logger import setup_logger

logger = setup_logger(__name__)

class SignalGenerator:
    def __init__(self):
        self.state = 0 # 0: Neutral, 1: Mitigation

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
                    logger.debug(f"State 0 -> 1 (Mitigation) at {date}, Low={current_bar['Low']}")
            
            elif self.state == 1:
                # Zone broken
                if current_bar['Low'] < zone_bottom:
                    self.state = 0
                    logger.debug(f"State 1 -> 0 (Zone Broken) at {date}")
                    continue
                    
                # Reclaim (Close > Prev High) -> BUY
                if current_bar['Close'] > prev_bar['High']:
                    self.state = 0 # Reset after triggering buy
                    logger.info(f"BUY Signal Triggered at {date}")
                    signals.append({
                        'action': 'BUY',
                        'date': date,
                        'entry': current_bar['Close'],
                        'stop_loss': zone_bottom
                    })
                    
        return signals
