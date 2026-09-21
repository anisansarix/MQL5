import MetaTrader5 as mt5
import logging
from risk_manager.prop_firm_guard import PropFirmGuard

logging.basicConfig(level=logging.INFO)

class MT5Executor:
    def __init__(self, risk_guard: PropFirmGuard):
        self.risk_guard = risk_guard
        
    def _execute_order(self, request: dict) -> bool:
        """Internal method to send an order to MT5 and handle the result."""
        # Check risk limits before ANY order is sent
        if not self.risk_guard.check_risk_status():
            logging.warning("Risk guard triggered. Order execution blocked.")
            return False
            
        result = mt5.order_send(request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logging.error(f"Order failed, retcode={result.retcode}")
            # Dictionary of common error codes
            if result.retcode == mt5.TRADE_RETCODE_NO_MONEY:
                logging.error("Not enough money for trade.")
            elif result.retcode == mt5.TRADE_RETCODE_INVALID_VOLUME:
                logging.error("Invalid volume.")
            return False
            
        logging.info(f"Order successful. Ticket: {result.order}")
        return True

    def place_market_order(self, symbol: str, action: str, lot_size: float, sl_price: float = 0.0, tp_price: float = 0.0):
        """Places a market buy or sell order."""
        if not mt5.symbol_select(symbol, True):
            logging.error(f"Failed to select symbol {symbol}")
            return False
            
        tick = mt5.symbol_info_tick(symbol)
        symbol_info = mt5.symbol_info(symbol)
        
        if action.upper() == 'BUY':
            order_type = mt5.ORDER_TYPE_BUY
            price = tick.ask
        elif action.upper() == 'SELL':
            order_type = mt5.ORDER_TYPE_SELL
            price = tick.bid
        else:
            logging.error(f"Invalid action: {action}")
            return False
            
        # Determine correct filling mode dynamically
        filling_mode = mt5.ORDER_FILLING_FOK
        if symbol_info is not None:
            if symbol_info.filling_mode & 1: # FOK
                filling_mode = mt5.ORDER_FILLING_FOK
            elif symbol_info.filling_mode & 2: # IOC
                filling_mode = mt5.ORDER_FILLING_IOC
            else:
                filling_mode = mt5.ORDER_FILLING_RETURN
            
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot_size),
            "type": order_type,
            "price": price,
            "sl": float(sl_price),
            "tp": float(tp_price),
            "deviation": 20,
            "magic": 234000,
            "comment": "Prop Firm Bot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
        }
        
        return self._execute_order(request)

    def close_all_positions(self):
        """Emergency method to close all open positions."""
        positions = mt5.positions_get()
        if positions is None or len(positions) == 0:
            return
            
        for pos in positions:
            tick = mt5.symbol_info_tick(pos.symbol)
            symbol_info = mt5.symbol_info(pos.symbol)
            
            if pos.type == mt5.ORDER_TYPE_BUY:
                order_type = mt5.ORDER_TYPE_SELL
                price = tick.bid
            else:
                order_type = mt5.ORDER_TYPE_BUY
                price = tick.ask
                
            filling_mode = mt5.ORDER_FILLING_FOK
            if symbol_info is not None:
                if symbol_info.filling_mode & 1:
                    filling_mode = mt5.ORDER_FILLING_FOK
                elif symbol_info.filling_mode & 2:
                    filling_mode = mt5.ORDER_FILLING_IOC
                else:
                    filling_mode = mt5.ORDER_FILLING_RETURN
                
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": order_type,
                "position": pos.ticket,
                "price": price,
                "deviation": 20,
                "magic": 234000,
                "comment": "Emergency Close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": filling_mode,
            }
            mt5.order_send(request)
        logging.info("All positions closed.")
