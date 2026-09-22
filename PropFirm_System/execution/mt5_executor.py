import MetaTrader5 as mt5
import logging
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.notifier import send_alert
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
        
        if result is None:
            logging.error(f"Order send failed (IPC or connection error), error code: {mt5.last_error()}")
            return False
            
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

    def place_market_order(self, symbol: str, action: str, lot_size: float, sl_price: float = 0.0, tp_price: float = 0.0, magic: int = 234000):
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
            "symbol": symbol,
            "volume": float(lot_size),
            "type": order_type,
            "price": price,
            "sl": float(sl_price),
            "tp": float(tp_price),
            "deviation": 20,
            "magic": magic,
            "comment": "Prop Firm Bot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
        }
        
        return self._execute_order(request)

    def modify_position(self, ticket: int, symbol: str, sl_price: float, tp_price: float) -> bool:
        """Modifies the Stop Loss and Take Profit of an existing position."""
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": symbol,
            "position": ticket,
            "sl": float(sl_price),
            "tp": float(tp_price)
        }
        result = mt5.order_send(request)
        if result is None:
            logging.error(f"Failed to modify position {ticket} (IPC error): {mt5.last_error()}")
            return False
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logging.error(f"Failed to modify position {ticket}, retcode={result.retcode}")
            return False
        
        logging.info(f"Position {ticket} modified successfully. New SL: {sl_price:.4f}, TP: {tp_price:.4f}")
        return True

    def close_position(self, ticket: int, symbol: str) -> bool:
        """Closes a specific position by ticket."""
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return False
        pos = positions[0]
        
        tick = mt5.symbol_info_tick(symbol)
        symbol_info = mt5.symbol_info(symbol)
        
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
            "symbol": symbol,
            "volume": pos.volume,
            "type": order_type,
            "position": pos.ticket,
            "price": price,
            "deviation": 20,
            "magic": pos.magic,
            "comment": "Bot Close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
        }
        
        result = mt5.order_send(request)
        if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
            logging.info(f"Successfully closed position {pos.ticket} on {symbol}")
            return True
        else:
            err_code = mt5.last_error() if result is None else result.retcode
            logging.warning(f"Failed to close {pos.ticket}, error: {err_code}")
            return False

    def close_all_positions(self):
        """Emergency method to close all open positions."""
        positions = mt5.positions_get()
        if positions is None or len(positions) == 0:
            return
            
        success_all = True
        
        for pos in positions:
            if not self.close_position(pos.ticket, pos.symbol):
                # Retry once
                import time
                time.sleep(0.5)
                if not self.close_position(pos.ticket, pos.symbol):
                    msg = f"EMERGENCY CLOSE FAILED for position {pos.ticket} on {pos.symbol}!"
                    logging.critical(msg)
                    send_alert(msg, "CRITICAL")
                    success_all = False
                
        if success_all:
            logging.info("All positions closed successfully.")
        else:
            msg = "Some positions failed to close during emergency shutdown."
            logging.critical(msg)
            send_alert(msg, "CRITICAL")
