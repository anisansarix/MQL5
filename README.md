# Prop Firm Quantitative Trading System & MT5 Integration

## Executive Summary
This is an end-to-end quantitative trading workstation designed for Proprietary Trading Firms (FTMO, FundedNext, etc.). It leverages MetaTrader 5 strictly as an execution gateway and data broker.

The backend is built in Python (FastAPI + MetaTrader5) and the frontend is a modern Next.js dashboard. The system features strict risk management to prevent breaking prop firm rules.

## Architecture

- **Backend Daemon (`main.py`)**: Continuously monitors the market, executes the `DynamicRLStrategy`, enforces risk guardrails, and maintains `state.json` and `bot.log`.
- **FastAPI Server (`api/server.py`)**: Exposes REST endpoints for the frontend to query state, update config, and fetch logs.
- **Next.js Dashboard (`frontend/`)**: Modern UI to configure symbols, risk, view live positions, trade history, and real-time market data.

## Features
- **Dynamic Position Sizing**: The continuous RL agent outputs a confidence scale `[-1.0, 1.0]`. The `PropFirmGuard` scales standard lot sizes up or down strictly based on this confidence and your Max Daily Loss / Drawdown rules.
- **Risk Management Guard (`PropFirmGuard`)**: Tracks high-water mark equity and daily balance to prevent you from ever breaching Max Daily Loss (e.g. 4%) and Max Trailing Drawdown (e.g. 12%). Includes circuit breakers to auto-flatten positions.
- **Strategies**:
  - `DynamicRLStrategy`: PyTorch / Stable-Baselines3 Deep Reinforcement Learning (PPO) integration using a continuous action space to dynamically manage exposure.
- **Automated Backups**: Backs up `config.json`, logs, and AI models daily.

## Getting Started

1. **Setup MT5**: Log into your MT5 terminal and enable algorithmic trading.
2. **Environment Variables**: Copy `PropFirm_System/.env.example` to `PropFirm_System/.env` and update API keys/Telegram Webhooks.
3. **Install Dependencies**:
```bash
cd PropFirm_System
pip install -r requirements.txt
```
4. **Run Backend Daemon**:
```bash
python main.py
```
5. **Run API Server**:
```bash
uvicorn api.server:app --port 8000
```
6. **Run Next.js Dashboard**:
```bash
cd frontend
npm install
npm run dev
```

## Configuration
Configuration is stored in `config.json` and updated via the Next.js UI.
- `symbols_to_trade`: Array of symbols (e.g. `["XAUUSD"]`)
- `strategy`: Strategy class name (`DynamicRLStrategy`)
- `max_daily_loss_pct`: Auto-kill threshold for daily drawdown (e.g. 0.04)
- `max_trailing_dd_pct`: Auto-kill threshold for total drawdown (e.g. 0.12)
