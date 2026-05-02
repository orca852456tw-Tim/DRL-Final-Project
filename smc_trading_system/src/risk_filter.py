import math
from typing import Dict, Any
from utils.logger import setup_logger
from config import RISK_SETTINGS

logger = setup_logger(__name__)

class RiskFilter:
    def __init__(self, risk_profile: str):
        self.risk_profile = risk_profile
        settings = RISK_SETTINGS.get(risk_profile, RISK_SETTINGS['保守型'])
        self.risk_pct = settings['risk_pct']
        self.atr_stop_multiplier = settings['atr_stop_multiplier']

    def calculate_position(self, account_balance: float, entry_price: float, stop_loss: float, atr: float = 0.0) -> Dict[str, Any]:
        """
        Calculate actual position size based on risk profile.
        """
        final_stop_loss = stop_loss - (self.atr_stop_multiplier * atr)
        max_loss_amount = account_balance * self.risk_pct
        risk_per_share = entry_price - final_stop_loss
        
        if risk_per_share <= 0:
            logger.warning("Risk per share is <= 0. Cannot calculate position.")
            return {'shares': 0, 'final_stop_loss': final_stop_loss}
            
        shares = math.floor(max_loss_amount / risk_per_share)
        logger.debug(f"Calculated shares: {shares} for balance {account_balance}")
        return {'shares': shares, 'final_stop_loss': final_stop_loss}
