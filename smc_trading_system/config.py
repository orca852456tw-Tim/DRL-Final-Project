"""
Configuration Management
"""

# --- 基本回測設定 ---
TICKER = '2330.TW' # 若後續測試 yfinance，可能需要改為 '2330.TW'
WATCHLIST = ['2330.TW', '2317.TW', '2454.TW', '2308.TW', '2881.TW']
START_DATE = '2021-01-01'
END_DATE = '2024-12-31'
INITIAL_CAPITAL = 1000000.0

# --- SMC 特徵偵測參數 ---
FVG_THRESHOLD = 0.002  # FVG 缺口門檻 (0.2%)
SWING_WINDOW = 5       # 尋找 Swing High/Low 的左右 K 線數量

# --- 風險與資金控管參數 ---
CURRENT_RISK_PROFILE = '保守型'  # '保守型' | '穩健型' | '積極型'

# 結構化定義不同風險情境的具體數值
RISK_SETTINGS = {
    '保守型': {
        'risk_pct': 0.01,              # 總資金 1%
        'atr_stop_multiplier': 0.0     # 停損嚴格設於 Zone Bottom
    },
    '穩健型': {
        'risk_pct': 0.02,              # 總資金 2%
        'atr_stop_multiplier': 0.5     # 停損需多讓出 0.5 倍 ATR
    },
    '積極型': {
        'risk_pct': 0.05,              # 總資金 5%
        'atr_stop_multiplier': 1.0     # 停損需多讓出 1.0 倍 ATR
    }
}
