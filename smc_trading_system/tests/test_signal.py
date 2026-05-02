import sys
import os
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.signal_gen import SignalGenerator

def run_test():
    print("=== Testing Signal Generation Module ===")
    
    # 1. Dummy LTF Data
    data = [
        [110, 112, 108, 109], # 0
        [109, 110, 105, 106], # 1
        [106, 107, 100, 101], # 2: Low=100 (enters 102~95) -> State 1
        [101, 101.5, 98, 99], # 3: inside zone, Close 99 < Prev High 107 -> State 1
        [99, 100, 96, 97],    # 4: inside zone, Close 97 < Prev High 101.5 -> State 1
        [97, 105, 96, 102],   # 5: Reclaim! Close 102 > Prev High 100 -> BUY
        [102, 110, 100, 108], # 6
    ]
    dates = pd.date_range('2024-01-01', periods=len(data), freq='h')
    ltf_df = pd.DataFrame(data, columns=['Open', 'High', 'Low', 'Close'], index=dates)
    
    # 2. Dummy HTF Data
    htf_data = [{'demand_zone': [102, 95]}]
    htf_df = pd.DataFrame(htf_data, index=[dates[0]])
    
    # 3. Generate Signals
    signal_gen = SignalGenerator()
    signals = signal_gen.generate_signals(htf_df, ltf_df)
    
    print("\n--- Signals Generated ---")
    if signals:
        for sig in signals:
            print(f"Action: {sig['action']}")
            print(f"Date: {sig['date']}")
            print(f"Entry Price: {sig['entry']}")
            print(f"Stop Loss: {sig['stop_loss']}")
    else:
        print("No signals generated.")

if __name__ == "__main__":
    run_test()
