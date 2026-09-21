from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader, APIKey
from pydantic import BaseModel
import json
import os
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Prop Firm Command Center API")

# Security configuration
API_KEY = os.getenv("API_KEY", "dev_secret_key_change_me_in_production")
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header == API_KEY:
        return api_key_header
    else:
        raise HTTPException(
            status_code=403, detail="Could not validate credentials"
        )

# Allow Next.js frontend to talk to FastAPI
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
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
def get_state(api_key: APIKey = Depends(get_api_key)):
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            raise HTTPException(status_code=500, detail="Error reading state")
    return {"message": "State file not yet created by bot."}

@app.get("/api/config")
def get_config(api_key: APIKey = Depends(get_api_key)):
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            raise HTTPException(status_code=500, detail="Error reading config")
    return {}

@app.post("/api/config")
def update_config(config: ConfigModel, api_key: APIKey = Depends(get_api_key)):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config.dict(), f, indent=4)
        return {"status": "success", "message": "Configuration updated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/logs")
def get_logs(lines: int = 100, api_key: APIKey = Depends(get_api_key)):
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r") as f:
                all_lines = f.readlines()
                return {"logs": "".join(all_lines[-lines:])}
        except Exception:
            return {"logs": "Error reading logs."}
    return {"logs": "No logs available yet."}

@app.delete("/api/logs")
def clear_logs(api_key: APIKey = Depends(get_api_key)):
    if os.path.exists(LOG_FILE):
        open(LOG_FILE, "w").close()
    return {"status": "success", "message": "Logs cleared"}

@app.get("/api/chart")
def get_chart_data(symbol: str = "XAUUSD", timeframe: int = 15, count: int = 100, api_key: APIKey = Depends(get_api_key)):
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
                chart_data = state.get("chart", [])
                return {"data": chart_data}
        except Exception:
            pass
    return {"data": []}
