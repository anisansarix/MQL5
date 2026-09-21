import MetaTrader5 as mt5
import logging
from datetime import datetime, timedelta, timezone
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.notifier import send_alert

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class PropFirmGuard:
    def __init__(self, initial_balance: float, max_daily_loss_pct: float = 0.05, max_trailing_dd_pct: float = 0.10, max_daily_trades: int = 10):
        self.initial_balance = initial_balance
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_trailing_dd_pct = max_trailing_dd_pct
        self.max_daily_trades = max_daily_trades
        self.max_trailing_dd_pct = max_trailing_dd_pct
        self.start_of_day_balance = initial_balance
        self.highest_equity = initial_balance
        
        self.instrument_leverage = {
            "forex": 100,
            "metals": 30,
            "crypto": 2
        }

    def update_daily_balance(self):
        """Should be called once at the start of each trading day."""
        account_info = mt5.account_info()
        if account_info:
            self.start_of_day_balance = account_info.balance
            logging.info(f"Updated start of day balance to: {self.start_of_day_balance}")

    def get_daily_trades_count(self) -> int:
        # Use server time instead of local time
        tick = mt5.symbol_info_tick("EURUSD")
        if not tick:
            tick = mt5.symbol_info_tick("XAUUSD")
            
        if tick:
            # tick.time is an epoch integer representing broker server time
            server_dt = datetime.fromtimestamp(tick.time, timezone.utc).replace(tzinfo=None)
        else:
            server_dt = datetime.utcnow()
            
        today = server_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Fetch deals from start of server today to now + 1 day
        deals = mt5.history_deals_get(today, server_dt + timedelta(days=1))
        
        if not deals:
            return 0
            
        count = 0
        for d in deals:
            if d.entry == mt5.DEAL_ENTRY_IN:
                count += 1
        return count

    def check_risk_status(self) -> bool:
        """Returns True if trading is allowed, False if a limit is breached."""
        account_info = mt5.account_info()
        if not account_info:
            logging.error("Failed to get account info from MT5.")
            return False
            
        current_equity = account_info.equity
        
        if current_equity > self.highest_equity:
            self.highest_equity = current_equity
            
        # 1. Check Max Trailing Drawdown
        total_drawdown = (self.initial_balance - current_equity) / self.initial_balance
        if total_drawdown >= self.max_trailing_dd_pct:
            msg = f"MAX DRAWDOWN REACHED: {total_drawdown:.2%}. Trading blocked."
            logging.critical(msg)
            send_alert(msg, "CRITICAL")
            return False
            
        # 2. Check Max Daily Loss
        daily_loss = (self.start_of_day_balance - current_equity) / self.start_of_day_balance
        if daily_loss >= self.max_daily_loss_pct:
            msg = f"DAILY LOSS LIMIT REACHED: {daily_loss:.2%}. Trading blocked for today."
            logging.critical(msg)
            send_alert(msg, "CRITICAL")
            return False
            
        # 3. Check Max Trades Per Day
        daily_trades = self.get_daily_trades_count()
        if daily_trades >= self.max_daily_trades:
            msg = f"MAX DAILY TRADES REACHED: {daily_trades}/{self.max_daily_trades}. Trading blocked for today."
            logging.warning(msg)
            send_alert(msg, "WARNING")
            return False
            
        return True

    def get_dynamic_risk_pct(self) -> float:
        """Calculates dynamic risk percentage per trade.
        Base: 0.50%
        If drawdown >= 1.5%: reduce to 0.25%
        """
        account_info = mt5.account_info()
        if not account_info:
            return 0.005 # Default 0.5%
            
        current_equity = account_info.equity
        total_drawdown = (self.initial_balance - current_equity) / self.initial_balance
        
        if total_drawdown >= 0.015:
            logging.warning(f"Drawdown is {total_drawdown:.2%}. Reducing risk to 0.25%.")
            return 0.0025
            
        return 0.005 # 0.5%

    def get_leverage_for_symbol(self, symbol: str) -> int:
        symbol = symbol.upper()
        if any(crypto in symbol for crypto in ["BTC", "ETH", "XRP", "LTC"]):
            return self.instrument_leverage["crypto"]
        elif any(metal in symbol for metal in ["XAU", "XAG", "GOLD", "SILVER"]):
            return self.instrument_leverage["metals"]
        else:
            return self.instrument_leverage["forex"]

    def calculate_position_size(self, symbol: str, risk_amount_usd: float, sl_distance_price: float) -> float:
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            logging.error(f"Symbol {symbol} not found.")
            return 0.0

        tick_size = symbol_info.trade_tick_size
        tick_value = symbol_info.trade_tick_value
        
        if sl_distance_price <= 0 or tick_size <= 0:
            return 0.0

        loss_per_lot = (sl_distance_price / tick_size) * tick_value
        if loss_per_lot == 0:
            return 0.0
            
        lot_size_by_risk = risk_amount_usd / loss_per_lot
        
        lot_size = max(symbol_info.volume_min, min(symbol_info.volume_max, lot_size_by_risk))
        lot_size = round(lot_size / symbol_info.volume_step) * symbol_info.volume_step
        
        logging.info(f"Calculated lot size for {symbol}: {lot_size} (Risk: ${risk_amount_usd:.2f})")
        return lot_size
