import json
import os
import logging

CONFIG_FILE = "config.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        logging.warning(f"{CONFIG_FILE} not found. Returning empty dict.")
        return {}
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            
        if config.get("max_daily_loss_pct", 0) <= 0:
            logging.error("Invalid max_daily_loss_pct (must be > 0). Defaulting to 0.04")
            config["max_daily_loss_pct"] = 0.04
            
        if config.get("max_trailing_dd_pct", 0) <= 0:
            logging.error("Invalid max_trailing_dd_pct (must be > 0). Defaulting to 0.12")
            config["max_trailing_dd_pct"] = 0.12
            
        if not config.get("symbols_to_trade"):
            logging.error("symbols_to_trade is empty. Defaulting to ['XAUUSD']")
            config["symbols_to_trade"] = ["XAUUSD"]
            
        return config
    except Exception as e:
        logging.error(f"Failed to load config: {e}")
        return {}

def save_config(config_dict):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_dict, f, indent=4)
        return True
    except Exception as e:
        logging.error(f"Failed to save config: {e}")
        return False
