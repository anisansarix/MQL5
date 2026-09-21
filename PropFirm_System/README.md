# Prop Firm Quant System

An end-to-end, AI-powered algorithmic trading environment built in Python, designed to connect to MetaTrader 5 (MT5) and strictly adhere to Prop Firm trading rules.

## 🌟 What We Built

We transformed a standard MT5 installation into a modern quantitative finance workstation. Instead of writing complex logic in MQL5, this system uses Python to handle data science, deep learning (FinRL), and strict risk management, while treating MT5 purely as a broker execution gateway.

### Core Components

*   **`risk_manager/prop_firm_guard.py`**: The "Guardian" of your account. It continuously tracks your equity, high-water marks, and start-of-day balances. If a trade would breach your Daily Loss Limit (5%) or Max Trailing Drawdown (10%), it blocks the trade and flattens all positions. It also dynamically calculates position sizes based on instrument leverage (Forex 1:100, Metals 1:30, Crypto 1:2).
*   **`data_pipeline/mt5_data_fetcher.py`**: A robust bridge that pulls years of historical OHLCV candles and live tick data directly from your MT5 terminal.
*   **`execution/mt5_executor.py`**: The execution engine that sends market orders back to MT5, handling error codes and fail-safes.
*   **`backtest/prop_firm_backtester.py`**: A custom, vectorized offline backtesting simulator. Unlike standard backtesters, this one explicitly simulates Prop Firm daily equity resets to see if a strategy would "Pass" or "Fail" a challenge before risking live money.

### The Brains (AI Integration)
*   **`strategy/finrl_env.py`**: A custom OpenAI `Gymnasium` environment. This allows deep learning models to treat the Forex market like a video game, learning to buy/sell based on technical indicators while being heavily penalized for hitting drawdowns.
*   **`strategy/finrl_trainer.py`**: The training script. It utilizes your **NVIDIA RTX 3050 GPU** (via PyTorch CUDA) and the `Stable-Baselines3` library to train a Proximal Policy Optimization (PPO) neural network on thousands of historical candles.
*   **`strategy/finrl_strategy.py`**: The live wrapper that loads your trained `.zip` AI models and feeds them live market data for instantaneous trading decisions.

### The Beautiful UI
*   **`dashboard.py`**: A local web application built with **Streamlit**. It reads the bot's live state and provides a beautiful interface to monitor your Account Balance, Current Equity, Drawdown Percentages, and active positions in real-time.

---

## 🚀 How to Use the System

### 1. Prerequisites
*   Ensure **MetaTrader 5** is open, logged into a demo account, and has **"Allow automated trading"** enabled in the options.

### 2. Train an AI Model (Optional)
If you want to create a new brain from scratch for a specific pair:
```bash
python strategy\finrl_trainer.py
```
*This will leverage your RTX 3050 to process historical data and will output a new model file into `strategy/models/`.*

### 3. Start the Live Trading Bot
This is the core engine that runs in the background, analyzing the market every 15 minutes.
```bash
python main.py
```

### 4. Monitor the Dashboard
Open a **second** terminal window and run:
```bash
python -m streamlit run dashboard.py
```
This will open a web browser at `http://localhost:8501`. Check the "Auto-Refresh" box in the sidebar to watch your bot trade live!

---

## 🛠️ Modifying the Bot
*   **Change Symbols**: Edit the `SYMBOLS_TO_TRADE` list inside `main.py`. *(Make sure the symbols exactly match what is available in your MT5 Market Watch).*
*   **Change Risk**: Edit `RISK_PER_TRADE_USD` in `main.py` to change how much capital is risked per trade.
*   **Change Timeframe**: The bot defaults to the 15-Minute chart (`mt5.TIMEFRAME_M15`). Change this in `main.py` if you prefer H1 or M5 trading.
