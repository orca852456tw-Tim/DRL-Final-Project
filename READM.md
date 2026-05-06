# 專案設計規格書：結合個性化 SMC 與多時框分析之智能交易回測系統

## 一、 系統架構與實作目標
請使用 Python 實作一個「結合 SMC (聰明錢概念) 的多時框智能交易回測系統」。目標標的為台積電 (2330.TW)。系統採 Pipeline-based Architecture，請開發者嚴格遵循以下 I/O 定義與模組邏輯進行開發。

**技術堆疊：**
* 語言：Python 3.11+
* 資料處理：`pandas`, `numpy`
* 技術指標：`pandas-ta`, `scipy`
* 資料來源：`yfinance` (免費抓取歷史報價)
* 前端展現：獨立的 HTML/CSS/JS 機構級量化分析儀表板 (`drl_dashboard.html` 與 `demo_dashboard.html`)。

---

## 二、 模組詳細規格與 I/O 定義

### 模組 1：Data Module (多時框資料處理)
負責抓取資料並進行多時框 (Multi-Timeframe) 的重採樣。
* **Inputs:** 
  * `ticker` (str): '2330'
  * `start_date` (str): '2021-01-01'
  * `end_date` (str): '2024-12-31'
  * `initial_capital` (float): 1,000,000
  * `risk_profile` (str): '保守型' | '穩健型' | '積極型'
* **Data Fetching & Resampling:**
  1. 使用 API (`yfinance`) 取得歷史日K (Daily) 資料。
  2. 因應免費 API 長期回測 (例如 4 年) 的資料長度限制，採用 `1D` 為基礎時框，利用 Pandas `.resample()` 將日線聚合為週線 `1W` 作為高階時框。
* **Output:** 回傳包含各時框 DataFrame 的 Dict：`{'1W': df_1W, '1D': df_1D}`，確保皆包含 OHLCV 且索引為 Datetime。

### 模組 2：SMC Detection Module (特徵工程)
在所有時框的 DataFrame 上標註 SMC 結構。供需區/缺口必須以 `[上限價格, 下限價格]` 的形式儲存。
* **FVG (價值缺口) 嚴格定義：**
  * Bullish FVG: `df['High'].shift(2) < df['Low']` 且缺口大小 `(df['Low'] - df['High'].shift(2)) / df['Close'].shift(2) >= 0.002` (大於 0.2%)。
  * 紀錄格式: `{'type': 'bullish_fvg', 'top': df['Low'], 'bottom': df['High'].shift(2), 'mitigated': False}`。若後續價格跌破 bottom，`mitigated` 設為 True。
* **Swing High/Low (波段高低點) 嚴格定義：**
  * 使用左右各 5 根 K 線 (Window=5) 尋找局部極值 (`scipy.signal.argrelextrema`)。
* **Demand/Supply Zone (供需區) 嚴格定義：**
  * 發生向上 BOS (收盤價實體突破前一個 Swing High) 時，導致該次突破的「最後一根下跌紅 K 線」高低點，記為 Demand Zone `[Top, Bottom]`。

### 模組 3：Signal Generation Module (狀態機邏輯)
**嚴禁單純觸碰支撐即無腦買入**，需實作「承接 + 收復 (Mitigation & Reclaim)」的兩段式確認 (Buy Program)：
1. **狀態 0 (Neutral):** 程式逐根 K 線掃描。
2. **狀態 1 (Mitigation):** 低階時框 (如 2H/4H) 的 `Low` 跌入高階時框 (1D/1W) 未失效的 Demand Zone 區間時，進入狀態 1 (觀察承接)。
3. **狀態 2 (Reclaim):** 維持狀態 1 期間 (價格未跌破 Zone Bottom)，若低階時框出現一根 K 線的 `Close` **大於前一根 K 線的 `High`** (小級別 ChoCH 轉強確認)，則正式觸發 `BUY` 訊號。
  * **Output Format:** `{'action': 'BUY', 'date': index, 'entry': df['Close'], 'stop_loss': demand_zone['bottom']}`

### 模組 4：Risk Filter Module (資金與部位控管)
接收 Signal，結合帳戶當下資金與風險偏好，計算實際下單股數：
* **保守型：** `risk_pct = 0.01` (總資金 1%)，停損嚴格設於 Signal 的 `stop_loss`。
* **穩健型：** `risk_pct = 0.02` (總資金 2%)，停損設於 `stop_loss - (0.5 * ATR)`。
* **積極型：** `risk_pct = 0.05` (總資金 5%)，停損設於 `stop_loss - (1.0 * ATR)`。
* **部位計算公式：**
  * `單筆最大虧損金額 = account_balance * risk_pct`
  * `每股承擔虧損 = entry_price - final_stop_loss`
  * `建議買入股數 = math.floor(單筆最大虧損金額 / 每股承擔虧損)`

### 模組 5：Report & Output Module
根據實際 Trade Log 結算量化績效：
* 總報酬率 (Total Return)
* 最大回撤 (MDD)
* 勝率 (Win Rate)
* 夏普值 (Sharpe Ratio)

---

## 三、 核心程式碼守則 (Coding Conventions)

1. **關注點分離 (Separation of Concerns, SoC)：** 
   嚴格遵守 Pipeline 架構，每個模組只能存取它需要的資料，禁止跨模組直接修改狀態。例如：`Data Module` 絕對不能包含任何交易決策邏輯。
2. **強制型別提示 (Type Hinting) 與文檔字串 (Docstrings)：** 
   所有的 Python 函式都必須標明輸入與輸出的資料型態（如 `def calc_position(balance: float) -> int:`），以降低幻覺與跨模組呼叫錯誤。
3. **配置檔抽離 (Configuration Management)：** 
   嚴禁在業務邏輯中「硬編碼 (Hardcode)」任何參數（如 API 金鑰、日期、Ticker、FVG 門檻）。所有變數集中於 `config.py` 管理。
4. **使用標準日誌 (Logging) 取代 Print：** 
   系統必須使用 Python 內建的 `logging` 模組。依照 `INFO` (系統狀態)、`DEBUG` (狀態機流轉細節)、`WARNING` (資料缺失) 來記錄系統運行狀況。

---

## 四、 專案檔案結構定義 (Directory Layout)

請依照以下目錄結構建立專案，確保高可維護性：
```text
smc_trading_system/
│
├── main.py                 # 程式主入口 (Entry Point)
├── config.py               # 全域設定檔 (環境變數、風險參數、交易標的設定)
├── requirements.txt        # 相依套件清單
│
├── src/                    # 核心業務模組
│   ├── __init__.py
│   ├── data_module.py      # 負責 yfinance 串接與 Multi-Timeframe (1D/1W) 重採樣
│   ├── smc_detection.py    # 負責 FVG、Swing High/Low 與 Demand/Supply Zone 特徵運算
│   ├── signal_gen.py       # 負責實作「承接 + 收復」的兩階段狀態機邏輯
│   ├── risk_filter.py      # 負責資金控管、ATR 計算與實際下單部位計算
│   ├── report_module.py    # 負責統整日誌、Monte Carlo 與績效計算
│   └── plot_module.py      # 負責 Plotly 圖表生成與儀表板渲染
│
├── demo_dashboard.html     # 回測結果視覺化儀表板
├── drl_dashboard.html      # 互動式 DRL 操控與洞察儀表板
└── utils/                  # 通用工具
    ├── __init__.py
    └── logger.py           # 日誌系統設定

---

## 五、 最新更新：DRL 理論基礎與分析模式 (2026-05 最新進展)

本專案現已擴充整合「深度強化學習 (DRL)」與進階的「儀表板 (Dashboard) 系統」，其理論與實作進度如下：

### 1. 理論基礎 (Theoretical Foundation)
* **Smart Money Concepts (SMC)**：除了既有的 FVG、Swing High/Low 外，進一步強調「流動性掃蕩 (Liquidity Sweep)」的狙擊手特質，系統在大多數時間會處於「觀望 (Hold)」狀態，拒絕頻繁交易，僅在高勝率結構出現時介入。
* **深度強化學習 (Deep Reinforcement Learning, DRL)**：
  * 結合 Actor-Critic 架構，使 AI 模型能透過環境的回饋不斷最佳化決策。
  * **PPO (Proximal Policy Optimization)**：限制單次學習幅度，確保訓練收斂穩健。
  * **SAC (Soft Actor-Critic)**：鼓勵模型進行高探索性 (Entropy Maximization)，以適應極端盤勢變化。
  * **DQN (Deep Q-Network)**：專注於尋找絕對價值最大化的離散交易動作。

### 2. 分析模式 (Analysis Models)
* **風險管理與多情境回測**：支援保守型、穩健型、積極型，並結合 ATR (Average True Range) 進行動態停損位設定。
* **蒙地卡羅模擬 (Monte Carlo Simulation)**：基於歷史勝率、平均獲利/虧損百分比與年均交易次數，執行 1,000 次隨機漫步模型，預測未來 3 年的最佳 (95th)、預期 (50th) 與最差 (5th) 資產變化情境。

### 3. 目前實作情況 (Current Implementation Status)
* **核心回測引擎 (main.py)**：已完成 4 年歷史數據 (2021-2024) 驗證，並整合了蒙地卡羅未來績效預測功能。
* **視覺化儀表板 (demo_dashboard.html / drl_dashboard.html)**：
  * 成功將單純的終端機文字報告升級為 **「機構級 Web 儀表板」**。
  * 實作了深色模式、玻璃擬態 (Glassmorphism) 的高質感互動設計。
  * 儀表板支援：左側參數控制 (標的、模型、風險屬性、資金)、動態載入動畫、三大 KPI 橫幅、Chart.js 決策與淨值圖表，以及底部的 SMC/DRL 深度解析卡片。
* **開發與版本控制**：所有源碼、儀表板模版與操作日誌均已確實版控並上傳至 GitHub (origin/main)。
