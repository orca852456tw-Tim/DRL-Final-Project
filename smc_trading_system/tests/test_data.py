import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_module import DataModule
from config import TICKER, START_DATE, END_DATE

def run_test():
    print("=== Testing Data Module ===")
    data_mod = DataModule(TICKER, START_DATE, END_DATE)
    tf_data = data_mod.fetch_and_resample()
    
    print("\nKeys in returned dict:")
    print(tf_data.keys())
    
    if '1H' in tf_data and not tf_data['1H'].empty:
        print("\ndf_1H Head (2 rows):")
        print(tf_data['1H'].head(2))
        print("\ndf_1H Tail (2 rows):")
        print(tf_data['1H'].tail(2))
    else:
        print("\n1H Data is empty")
    
    if '1D' in tf_data and not tf_data['1D'].empty:
        print("\ndf_1D Head (2 rows):")
        print(tf_data['1D'].head(2))
        print("\ndf_1D Tail (2 rows):")
        print(tf_data['1D'].tail(2))
    else:
        print("\n1D Data is empty")

if __name__ == "__main__":
    run_test()
