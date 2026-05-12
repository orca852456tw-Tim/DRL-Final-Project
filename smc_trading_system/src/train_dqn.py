import sys
import os
import logging
import pandas as pd
import yfinance as yf
import json
from stable_baselines3 import DQN
from stable_baselines3.common.vec_env import DummyVecEnv
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.logger import configure

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.env_builder import SMCTradingEnv
from src.smc_detection import SMCDetection
from utils.logger import setup_logger

logger = setup_logger("TrainDQN")

# 定義訓練集的時間範圍 (2016 - 2023)
TRAIN_START = '2016-01-01'
TRAIN_END = '2023-12-31'

# 進行 Data Augmentation 的多檔權值股清單
TRAIN_TICKERS = ['2330.TW', '2317.TW', '2454.TW']

def process_data_for_env(ticker: str) -> pd.DataFrame:
    """抓取單一股票資料並生成 SMC 降維特徵"""
    logger.info(f"Fetching and processing training data for {ticker}...")
    df_1d = yf.download(ticker, start=TRAIN_START, end=TRAIN_END, interval="1d", progress=False)
    
    if df_1d.empty:
        logger.error(f"Failed to fetch data for {ticker}")
        return pd.DataFrame()
        
    if isinstance(df_1d.columns, pd.MultiIndex):
        df_1d.columns = df_1d.columns.get_level_values(0)
        
    df_1d = df_1d.dropna()
    resample_dict = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'}
    df_1w = df_1d.resample('W-FRI').agg(resample_dict).dropna()
    
    tf_data = {'1W': df_1w, '1D': df_1d}
    smc_mod = SMCDetection()
    tf_data_with_features = smc_mod.process_all_timeframes(tf_data)
    
    ltf = tf_data_with_features['1D']
    import pandas_ta as ta
    ltf.ta.atr(length=14, append=True)
    atr_col = ltf.columns[-1]
    
    htf = tf_data_with_features['1W']
    
    # 預先計算並合併所有觀察特徵，加速訓練時的環境讀取
    features_list = []
    active_zone = None
    
    for i in range(len(ltf)):
        current_date = ltf.index[i]
        bar = ltf.iloc[i]
        close_p = bar['Close']
        
        past_htf = htf[htf.index <= current_date]
        if not past_htf.empty:
            for j in range(len(past_htf)-1, -1, -1):
                if past_htf['demand_zone'].iloc[j] is not None:
                    active_zone = past_htf['demand_zone'].iloc[j]
                    break
                    
        if active_zone:
            d_top = float((close_p - active_zone[0]) / close_p)
            d_bottom = float((close_p - active_zone[1]) / close_p)
        else:
            d_top, d_bottom = 0.0, 0.0
            
        fvg_flag = 1.0 if bar.get('bullish_fvg') is not None else 0.0
        sweep_flag = 1.0 if bar.get('bullish_liquidity_sweep') else 0.0
        atr_raw = bar.get(atr_col, 0.0)
        atr_val = 0.0 if pd.isna(atr_raw) else float(atr_raw)
        atr_norm = atr_val / close_p if close_p != 0 and atr_val != 0.0 else 0.0
        
        features_list.append({
            'D_top': d_top,
            'D_bottom': d_bottom,
            'FVG_flag': fvg_flag,
            'Sweep_flag': sweep_flag,
            'ATR_norm': atr_norm
        })
        
    return pd.DataFrame(features_list)

def make_env(ticker, risk_profile, log_dir):
    """建立單一環境的工廠函數 (供 DummyVecEnv 使用)"""
    def _init():
        df = process_data_for_env(ticker)
        env = SMCTradingEnv(df=df, risk_profile=risk_profile)
        env = Monitor(env, os.path.join(log_dir, f"monitor_{ticker}"))
        return env
    return _init

def main():
    logger.info("Starting Multi-Ticker DQN Training Process...")
    
    # 我們選擇以「穩健型」的價值觀來訓練模型作為 Baseline
    target_risk_profile = '穩健型'
    
    # 建立平行訓練環境 (Data Augmentation)
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "models", "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    env_fns = [make_env(ticker, target_risk_profile, log_dir) for ticker in TRAIN_TICKERS]
    vec_env = DummyVecEnv(env_fns)
    
    logger.info("Initializing DQN Model...")
    # 初始化 DQN 神經網路
    # learning_rate: 神經網路學習速度
    # buffer_size: 經驗回放池的大小 (重要參數，讓 AI 記住過去的教訓)
    model = DQN(
        policy="MlpPolicy",
        env=vec_env,
        learning_rate=1e-3,
        buffer_size=100000,
        exploration_fraction=0.2, # 前 20% 的時間多嘗試隨機動作
        verbose=1
    )
    
    new_logger = configure(log_dir, ["stdout", "csv"])
    model.set_logger(new_logger)
    
    # 設定訓練總步數 (3檔股票 x 8年約2000天 = 6000筆資料，我們讓它跑 50 回合)
    total_timesteps = len(TRAIN_TICKERS) * 2000 * 50
    
    logger.info(f"Starting Training for {total_timesteps} timesteps...")
    # --- 這裡就是模型真正開始學習的地方 ---
    model.learn(total_timesteps=total_timesteps)
    
    # 建立 models 資料夾並存檔
    model_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "models")
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, "dqn_smc_model.zip")
    
    model.save(model_path)
    logger.info(f"Training Complete! Model saved to {model_path}")
    
    # 擷取 DQN 真實的訓練歷程
    import numpy as np
    rewards = []
    for ticker in TRAIN_TICKERS:
        mon_file = os.path.join(log_dir, f"monitor_{ticker}.monitor.csv")
        if os.path.exists(mon_file):
            df_mon = pd.read_csv(mon_file, skiprows=1)
            rewards.extend(df_mon['r'].tolist())
            
    if rewards:
        chunks = np.array_split(rewards, 7)
        avg_rewards = [float(np.mean(chunk)) for chunk in chunks]
    else:
        avg_rewards = []
        
    loss_file = os.path.join(log_dir, "progress.csv")
    losses = []
    if os.path.exists(loss_file):
        df_loss = pd.read_csv(loss_file)
        if 'train/loss' in df_loss.columns:
            losses = df_loss['train/loss'].dropna().tolist()
            if len(losses) > 50:
                indices = np.linspace(0, len(losses)-1, 50, dtype=int)
                losses = [float(losses[i]) for i in indices]
            else:
                losses = [float(l) for l in losses]

    stats = {
        "avg_rewards_7_stages": avg_rewards,
        "loss_curve": losses
    }
    with open(os.path.join(model_dir, "training_stats.json"), "w") as f:
        json.dump(stats, f)
    logger.info("Training stats saved to training_stats.json")

if __name__ == "__main__":
    main()
