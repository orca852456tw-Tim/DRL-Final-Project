# 🧠 DRL-SMC 智能量化交易系統

結合聰明錢概念 (SMC) 與深度強化學習 (DQN) 的多智能體協作框架

## 📖 專案簡介

本專案旨在解決傳統量化交易「缺乏市場結構解讀能力」與「純深度學習淪為黑盒子」的兩大痛點。我們首創將 **Smart Money Concept (聰明錢概念)** 的市場結構特徵（如 FVG 價值缺口、Liquidity Sweep 流動性掃蕩）進行數值化降維，並封裝為馬可夫決策過程 (MDP) 的觀察空間。

決策大腦採用 **Deep Q-Network (DQN)**，並打破靜態風控傳統，將投資人的「風險胃納（保守、穩健、積極）」映射為神經網路的離散動作空間，實現了具備極高可解釋性的「白盒化自動交易引擎」。

---

## 🏗️ 系統架構 (Agentic Workflow)

系統採用 Pipeline 多智能體協作架構，確保決策的穩定性與破產保護機制：

*   **📡 Data Module**: 串接 `yfinance` 獲取台股權值股 (如 2330, 2317, 2454) 歷史數據，進行多時框 (1D/1W) 重採樣。
*   **👁️ SMC Detection**: 感知智能體。精準捕捉 Demand/Supply Zone 與流動性掃蕩。
*   **🧠 DRL Agent**: DQN 決策大腦。於客製化 `SMCTradingEnv` 中歷經 8 年歷史數據、30 萬步多標的平行訓練 (Data Augmentation) 淬鍊而成。
*   **🛡️ Risk Filter**: 風控看門狗。依據 DQN 輸出的風險動態訊號，精確計算停損位 (ATR Buffer) 與進場部位大小。
*   **📊 Dashboard**: 機構級後端渲染儀表板，支援蒙地卡羅 (Monte Carlo) 未來 3 年績效投影。

---

## 🚀 快速上手 (Quick Start)

### 1. 安裝依賴套件

```bash
pip install -r requirements.txt
pip install "stable-baselines3[extra]"
```

### 2. 重新訓練 DQN 大腦 (選用)

系統已內建訓練完成之權重檔 `models/dqn_smc_model.zip`。若欲使用最新資料進行持續學習 (Continuous Training) 閉環重訓：

```bash
python src/train_dqn.py
```
*(註：訓練將開啟 DummyVecEnv 平行環境，耗時約數分鐘至數十分鐘，視硬體而定)*

### 3. 執行外樣本回測與生成儀表板

```bash
python main.py
```
執行完畢後，終端機將輸出各筆交易的詳細 Trade Ledger (買賣理由、部位大小、SMC 狀態)。

### 4. 開啟視覺化互動儀表板

回測完成後，系統將自動於根目錄產生 `drl_dashboard.html`。
請直接使用瀏覽器 (Chrome/Edge/Safari) 開啟該檔案，即可體驗具備 Glassmorphism 美學的 DRL 未來績效投影分析！

---

## 📈 測試集績效表現 (Out-of-Sample: 2024 - Present)

*   **回測標的**: 台積電 (2330.TW)
*   **動態交易勝率**: 66.67%
*   **總報酬率 (Total Return)**: +46.44%
*   **最大回撤 (MDD)**: -5.95%

> [!TIP]
> 註：在嚴格的 SMC 紀律懲罰機制下，AI Agent 展現出極具耐心的狙擊手特質，有效避開無效震盪區間。

*Developed for Quantitative Trading Final Project.*
