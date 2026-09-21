from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import os
from typing import List, Optional

app = FastAPI(title="Prop Firm Command Center API")

# Allow Next.js frontend to talk to FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, lock this down
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIG_FILE = "config.json"
STATE_FILE = "state.json"
LOG_FILE = "bot.log"

class ConfigModel(BaseModel):
    bot_status: str
    symbols_to_trade: List[str]
    timeframe: int
    initial_account_balance: float
    risk_per_trade_usd: float
    strategy: str
    model_path: str
    max_daily_loss_pct: float
    max_trailing_dd_pct: float

@app.get("/api/state")
def get_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            raise HTTPException(status_code=500, detail="Error reading state")
    return {"message": "State file not yet created by bot."}

@app.get("/api/config")
def get_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            raise HTTPException(status_code=500, detail="Error reading config")
    return {}

@app.post("/api/config")
def update_config(config: ConfigModel):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config.dict(), f, indent=4)
        return {"status": "success", "message": "Configuration updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/logs")
def get_logs(lines: int = 100):
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                all_lines = f.readlines()
                return {"logs": "".join(all_lines[-lines:])}
        except Exception:
            return {"logs": "Error reading logs."}
    return {"logs": "No logs available yet."}

@app.delete("/api/logs")
def clear_logs():
    if os.path.exists(LOG_FILE):
        open(LOG_FILE, "w").close()
    return {"status": "success", "message": "Logs cleared"}

@app.get("/api/chart")
def get_chart_data(symbol: str = "XAUUSD", timeframe: int = 15, count: int = 100):
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
                chart_data = state.get("chart", [])
                return {"data": chart_data}
        except Exception:
            pass
    return {"data": []}
