import gymnasium as gym
from gymnasium import spaces
import numpy as np
import pandas as pd

class SMCTradingEnv(gym.Env):
    """
    A Custom SMC Trading Environment perfectly aligned with the DQN Discrete Action spec.
    """
    metadata = {"render_modes": ["human"]}

    def __init__(self, df: pd.DataFrame, risk_profile: str = '穩健型'):
        super().__init__()
        self.df = df
        self.current_step = 0
        self.max_steps = len(df) - 1
        self.risk_profile = risk_profile

        # 核心實作 1：根據風險屬性，動態設定獎勵權重 (omega)
        if self.risk_profile == '保守型':
            self.omega_1, self.omega_2, self.omega_3 = 1.0, 5.0, 2.0  # 極度厭惡回撤
        elif self.risk_profile == '積極型':
            self.omega_1, self.omega_2, self.omega_3 = 3.0, 1.0, 2.0  # 追求獲利，容忍回撤
        else: # 穩健型預設
            self.omega_1, self.omega_2, self.omega_3 = 2.0, 2.0, 2.0

        # 核心實作 2：離散動作空間 (Discrete Action Space)
        # 0: 觀望 | 1: 保守型買進 | 2: 穩健型買進 | 3: 積極型買進
        self.action_space = spaces.Discrete(4)

        # 觀察空間 (Observation Space): SMC 的 5 大降維特徵
        self.observation_space = spaces.Box(
            low=-np.inf, high=np.inf, shape=(5,), dtype=np.float32
        )

    def _get_observation(self):
        row = self.df.iloc[self.current_step]
        obs = np.array([
            row.get('D_top', 0.0),
            row.get('D_bottom', 0.0),
            row.get('FVG_flag', 0.0),
            row.get('Sweep_flag', 0.0),
            row.get('ATR_norm', 0.0)
        ], dtype=np.float32)
        return obs

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.current_step = 0
        return self._get_observation(), {}

    def step(self, action):
        row = self.df.iloc[self.current_step]
        sweep_flag = row.get('Sweep_flag', 0.0)
        
        reward = 0.0
        smc_violation = 0.0
        pnl_estimate = 0.0
        drawdown_penalty = 0.0
        
        # 只有當 Agent 決定進場 (action 1, 2, 3) 時才進行評估
        if action in [1, 2, 3]:
            # 轉換 action 為曝險比例，用來計算獎勵/懲罰的幅度
            risk_exposure = {1: 0.01, 2: 0.02, 3: 0.05}[action]

            # 核心實作 3：SMC 紀律懲罰 (無 Sweep 亂買)
            if sweep_flag == 0:
                smc_violation = 1.0 
                
            # 模擬盤勢反饋：若有 Sweep 則給予正向預期，否則給予負向回撤懲罰
            if sweep_flag == 1:
                pnl_estimate = 1.0 * risk_exposure
            else:
                drawdown_penalty = 1.0 * risk_exposure
                
            # 嚴格套用規格書的 DQN 獎勵函數公式
            reward = (self.omega_1 * pnl_estimate) - (self.omega_2 * drawdown_penalty) - (self.omega_3 * smc_violation)

        self.current_step += 1
        terminated = self.current_step >= self.max_steps
        truncated = False
        info = {'action_taken': action, 'reward': reward}

        return self._get_observation(), reward, terminated, truncated, info

    def render(self):
        pass
