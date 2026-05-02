import sys
import os
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.smc_detection import SMCDetection
from config import FVG_THRESHOLD

def run_test():
    print("=== Testing SMC Detection Module ===")
    data = []
    # 0-4: left side of swing high
    data.append([100, 105, 95, 102]) # 0
    data.append([102, 108, 100, 106]) # 1
    data.append([106, 110, 104, 109]) # 2
    data.append([109, 115, 108, 114]) # 3
    data.append([114, 118, 112, 117]) # 4
    # 5: SWING HIGH
    data.append([117, 125, 115, 120]) # 5 (High = 125)
    # 6-10: right side of swing high
    data.append([120, 122, 110, 112]) # 6
    data.append([112, 115, 105, 108]) # 7
    data.append([108, 110, 100, 105]) # 8
    data.append([105, 108, 98, 100])  # 9 (Red candle, High=108, Low=98)
    data.append([100, 102, 95, 98])   # 10 (Red candle, High=102, Low=95)
    # 11-13: FVG and move up
    data.append([98, 105, 96, 100])   # 11 
    data.append([100, 120, 99, 118])  # 12
    data.append([118, 128, 108, 127]) # 13 -> FVG: Low=108, High(11)=105
    # 14: BOS (Close > Swing High 125)
    data.append([127, 135, 125, 130]) # 14
    
    df = pd.DataFrame(data, columns=['Open', 'High', 'Low', 'Close'])
    
    detector = SMCDetection(fvg_threshold=FVG_THRESHOLD)
    res = detector.process_all_timeframes({'test_tf': df})
    res_df = res['test_tf']
    
    print("--- FVG Detected ---")
    fvg_rows = res_df.dropna(subset=['bullish_fvg'])
    if not fvg_rows.empty:
        for idx, row in fvg_rows.iterrows():
            print(f"Index: {idx}, FVG [Top, Bottom]: {row['bullish_fvg']}")
    else:
        print("No FVG detected!")
        
    print("\n--- Demand Zone Detected ---")
    dz_rows = res_df.dropna(subset=['demand_zone'])
    if not dz_rows.empty:
        for idx, row in dz_rows.iterrows():
            print(f"Index (BOS trigger): {idx}, Demand Zone [Top, Bottom]: {row['demand_zone']}")
    else:
        print("No Demand Zone detected!")

if __name__ == "__main__":
    run_test()
