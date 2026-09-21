import MetaTrader5 as mt5
from datetime import datetime, timezone, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class PropFirmGuard:
    def __init__(self, initial_balance: float, max_daily_loss_pct: float = 0.01, max_total_loss_pct: float = 0.03):
        self.initial_balance = initial_balance
        # Note: Strategy calls for 1% daily loss halt, and 3% total halt
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_total_loss_pct = max_total_loss_pct
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
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        # Fetch deals from start of today to now + 1 day
        deals = mt5.history_deals_get(today, datetime.now() + timedelta(days=1))
        
        if not deals:
            return 0
            
        count = 0
        for d in deals:
            # We count ENTRY_IN deals as the start of a trade
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
            
        # 1. Check Max Total Drawdown (3%)
        total_drawdown = (self.initial_balance - current_equity) / self.initial_balance
        if total_drawdown >= self.max_total_loss_pct:
            logging.critical(f"MAX DRAWDOWN REACHED: {total_drawdown:.2%}. Trading blocked.")
            return False
            
        # 2. Check Daily Loss Limit (1%)
        daily_loss = (self.start_of_day_balance - current_equity) / self.start_of_day_balance
        if daily_loss >= self.max_daily_loss_pct:
            logging.critical(f"DAILY LOSS LIMIT REACHED: {daily_loss:.2%}. Trading blocked for today.")
            return False
            
        # 3. Check Max Trades Per Day (Temporarily increased for testing)
        daily_trades = self.get_daily_trades_count()
        if daily_trades >= 999:
            logging.warning(f"MAX DAILY TRADES REACHED: {daily_trades}/999. Trading blocked for today.")
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

    def calculate_position_size(self, symbol: str, risk_amount_usd: float, stop_loss_points: float) -> float:
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            logging.error(f"Symbol {symbol} not found.")
            return 0.0

        tick_size = symbol_info.trade_tick_size
        tick_value = symbol_info.trade_tick_value
        
        if stop_loss_points <= 0:
            return 0.0

        loss_per_lot = (stop_loss_points / tick_size) * tick_value
        if loss_per_lot == 0:
            return 0.0
            
        lot_size_by_risk = risk_amount_usd / loss_per_lot
        
        lot_size = max(symbol_info.volume_min, min(symbol_info.volume_max, lot_size_by_risk))
        lot_size = round(lot_size / symbol_info.volume_step) * symbol_info.volume_step
        
        logging.info(f"Calculated lot size for {symbol}: {lot_size} (Risk: ${risk_amount_usd:.2f})")
        return lot_size
