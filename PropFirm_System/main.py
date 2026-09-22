import time
import logging
import schedule
import MetaTrader5 as mt5

from data_pipeline.mt5_data_fetcher import MT5DataFetcher
from risk_manager.prop_firm_guard import PropFirmGuard
from execution.mt5_executor import MT5Executor
from strategy.base_strategy import TrendFollowingStrategy
from strategy.finrl_strategy import FinRLStrategy
from strategy.ny_trend_continuation import NYTrendContinuation

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ],
    force=True
)

# Configuration is now handled dynamically via config.json

import json
from datetime import datetime, timedelta, timezone

def save_state(guard: PropFirmGuard, next_run_time: float = 0):
    account_info = mt5.account_info()
    if not account_info:
        return

    # Fetch live positions
    positions = mt5.positions_get()
    pos_list = []
    if positions:
        for p in positions:
            pos_list.append({
                "ticket": p.ticket,
                "symbol": p.symbol,
                "type": "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
                "volume": p.volume,
                "price_open": p.price_open,
                "price_current": p.price_current,
                "sl": p.sl,
                "tp": p.tp,
                "profit": p.profit
            })
            
    # Fetch today's closed trades history
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    history = mt5.history_deals_get(today, datetime.now() + timedelta(days=1))
    history_list = []
    daily_pnl = 0.0
    if history:
        for h in history:
            # Only count actual trade closures (where profit != 0 or it's a realized deal)
            if h.entry == mt5.DEAL_ENTRY_OUT:
                history_list.append({
                    "symbol": h.symbol,
                    "type": "BUY" if h.type == mt5.DEAL_TYPE_BUY else "SELL",
                    "volume": h.volume,
                    "profit": h.profit,
                    "time": datetime.fromtimestamp(h.time).strftime('%H:%M:%S')
                })
                daily_pnl += h.profit
            
    # Fetch chart data for frontend to avoid FastAPI multi-process IPC collisions
    chart_data = []
    current_config = load_config()
    tf_val = current_config.get("timeframe", 15)
    tf_map = {1: mt5.TIMEFRAME_M1, 5: mt5.TIMEFRAME_M5, 15: mt5.TIMEFRAME_M15, 60: mt5.TIMEFRAME_H1}
    mt5_tf = tf_map.get(tf_val, mt5.TIMEFRAME_M15)
    
    rates = mt5.copy_rates_from_pos(current_config.get("symbols_to_trade", ["XAUUSD"])[0], mt5_tf, 0, 200)
    if rates is not None and len(rates) > 0:
        for r in rates:
            chart_data.append({
                "time": int(r['time']),
                "open": float(r['open']),
                "high": float(r['high']),
                "low": float(r['low']),
                "close": float(r['close']),
                "volume": float(r['tick_volume'])
            })

    state = {
        "balance": account_info.balance,
        "equity": account_info.equity,
        "margin": account_info.margin,
        "free_margin": account_info.margin_free,
        "margin_level": account_info.margin_level,
        "start_of_day_balance": guard.start_of_day_balance,
        "highest_equity": guard.highest_equity,
        "daily_pnl": daily_pnl,
        "positions": pos_list,
        "history": history_list[-10:], # Keep last 10 trades for UI
        "chart": chart_data,
        "next_run_time": next_run_time,
        "last_update": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    with open("state.json", "w") as f:
        json.dump(state, f)

from config_manager import load_config

def main():
    try:
        # Initial load to setup objects
        config = load_config()
        fetcher = MT5DataFetcher()
        guard = PropFirmGuard(initial_balance=config.get("initial_account_balance", 100000.0))
        executor = MT5Executor(guard)
        
        # Determine initial strategy
        strat_name = config.get("strategy", "FinRLStrategy")
        if strat_name == "FinRLStrategy":
            strategy = FinRLStrategy(model_path=config.get("model_path", "strategy/models/ppo_XAUUSD_m15.zip"))
        elif strat_name == "NYTrendContinuation":
            strategy = NYTrendContinuation()
        else:
            strategy = TrendFollowingStrategy()

        # Update balance initially
        guard.update_daily_balance()
        save_state(guard)

        logging.info("System initialized. Starting main loop...")

        # We will track the last run time to manually handle intervals so we can dynamically adapt to timeframe changes
        last_run_time = 0
        last_recorded_day = None

        while True:
            try:
                # Reconnect logic: ensure MT5 IPC is still alive
                if mt5.terminal_info() is None:
                    logging.error("Lost connection to MT5 terminal! Attempting to re-initialize...")
                    if not mt5.initialize():
                        logging.critical("Failed to reconnect to MT5. Retrying in 10s...")
                        time.sleep(10)
                        continue
                    logging.info("Successfully reconnected to MT5.")
                    
                config = load_config()
                status = config.get("bot_status", "stopped")
                
                # Check for server day rollover
                tick = mt5.symbol_info_tick(config.get("symbols_to_trade", ["XAUUSD"])[0])
                if tick:
                    server_day = datetime.fromtimestamp(tick.time, timezone.utc).day
                    if last_recorded_day is None:
                        last_recorded_day = server_day
                    elif server_day != last_recorded_day:
                        logging.info("Server day rollover detected. Updating daily balance.")
                        guard.update_daily_balance()
                        last_recorded_day = server_day
                
                # Calculate next run time
                tf_minutes = config.get("timeframe", 15)
                current_time = time.time()
                next_run_time = last_run_time + (tf_minutes * 60)
                
                # Save state so dashboard always has fresh data even if stopped
                save_state(guard, next_run_time=next_run_time)
                
                if status == "stopped":
                    time.sleep(5)
                    continue
                
                schedule.run_pending()
                
                # Dynamic execution based on timeframe
                tf_minutes = config.get("timeframe", 15)
                current_time = time.time()
                if (current_time - last_run_time) >= (tf_minutes * 60):
                    # We need to run the trading job
                    # Re-instantiate strategy if config changed
                    new_strat = config.get("strategy", "FinRLStrategy")
                    
                    # Check if we need to switch strategy
                    current_strat_class = strategy.__class__.__name__
                    if new_strat != current_strat_class:
                        if new_strat == "FinRLStrategy":
                            strategy = FinRLStrategy(model_path=config.get("model_path"))
                        elif new_strat == "NYTrendContinuation":
                            strategy = NYTrendContinuation()
                        else:
                            strategy = TrendFollowingStrategy()
                    elif new_strat == "FinRLStrategy" and strategy.model_path != config.get("model_path"):
                        # Same class but model path changed
                        strategy = FinRLStrategy(model_path=config.get("model_path"))
                    
                    # Execute logic
                    guard.max_daily_loss_pct = config.get("max_daily_loss_pct", 0.01)
                    guard.max_trailing_dd_pct = config.get("max_trailing_dd_pct", 0.03)
                    guard.max_daily_trades = config.get("max_daily_trades", 10)
                    
                    logging.info(f"--- Running Trading Cycle (Config: {config.get('symbols_to_trade')} | {new_strat}) ---")
                    
                    # 1. Check Global Risk
                    if not guard.check_risk_status():
                        logging.warning("Global risk limits breached. Halting trading.")
                        executor.close_all_positions()
                    else:
                        for symbol in config.get("symbols_to_trade", ["XAUUSD"]):
                            logging.info(f"Analyzing {symbol}...")
                            
                            tf_map = {1: mt5.TIMEFRAME_M1, 5: mt5.TIMEFRAME_M5, 15: mt5.TIMEFRAME_M15, 60: mt5.TIMEFRAME_H1}
                            mt5_tf = tf_map.get(tf_minutes, mt5.TIMEFRAME_M15)
                            
                            action, sl_price, tp_price = 'HOLD', 0.0, 0.0
                            
                            # Execute Strategy Analysis
                            if hasattr(strategy, "analyze_symbol"):
                                action, sl_price, tp_price = strategy.analyze_symbol(symbol, fetcher)
                            else:
                                df = fetcher.fetch_historical_data(symbol, mt5_tf, num_candles=250)
                                if not df.empty:
                                    action = strategy.analyze(df)
                                    if action in ['BUY', 'SELL']:
                                        sl_price, tp_price = strategy.calculate_sl_tp(df, action)

                            # Dynamic position management
                            positions = mt5.positions_get(symbol=symbol)
                            has_open_position = positions is not None and len(positions) > 0

                            if has_open_position:
                                for pos in positions:
                                    pos_type = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
                                    # If action is HOLD (0 in RL) or OPPOSITE of our position, we CLOSE it
                                    if action == 'HOLD' or (action == 'BUY' and pos_type == 'SELL') or (action == 'SELL' and pos_type == 'BUY'):
                                        logging.info(f"Dynamic Exit: Strategy signaled {action}, closing existing {pos_type} position {pos.ticket} on {symbol}")
                                        executor.close_all_positions() # Simple catch-all to flatten
                                    elif action == pos_type and sl_price > 0 and tp_price > 0:
                                        # Strategy agrees with our current position. Check for Trailing Stop logic.
                                        tick = mt5.symbol_info_tick(symbol)
                                        modify = False
                                        if pos_type == 'BUY':
                                            # For BUY, tighter SL is HIGHER than old SL
                                            if sl_price > pos.sl and sl_price < tick.bid:
                                                modify = True
                                        elif pos_type == 'SELL':
                                            # For SELL, tighter SL is LOWER than old SL
                                            if (pos.sl == 0.0 or sl_price < pos.sl) and sl_price > tick.ask:
                                                modify = True
                                        
                                        if modify:
                                            logging.info(f"Smart Target Update: Trailing {pos_type} stops for {pos.ticket} to SL: {sl_price:.4f}")
                                            executor.modify_position(pos.ticket, symbol, sl_price, tp_price)
                                        else:
                                            logging.info(f"Monitoring active {pos_type} position {pos.ticket}. Strategy maintained {action} conviction.")
                            
                            # Re-check open positions after potential closures
                            positions = mt5.positions_get(symbol=symbol)
                            has_open_position = positions is not None and len(positions) > 0

                            if action in ['BUY', 'SELL'] and not has_open_position and sl_price > 0 and tp_price > 0:
                                tick_info = mt5.symbol_info(symbol)
                                if not tick_info: continue
                                    
                                # Calculate SL distance in raw price units
                                if action == 'BUY':
                                    sl_distance_price = abs(tick_info.ask - sl_price)
                                else:
                                    sl_distance_price = abs(tick_info.bid - sl_price)
                                    
                                # Dynamic risk based on drawdown
                                risk_pct = guard.get_dynamic_risk_pct()
                                account_info = mt5.account_info()
                                risk_amount_usd = account_info.equity * risk_pct if account_info else 100.0
                                
                                lot_size = guard.calculate_position_size(symbol, risk_amount_usd, sl_distance_price)
                                
                                if lot_size > 0:
                                    logging.info(f"Executing {action} on {symbol}. Vol: {lot_size}, SL: {sl_price:.4f}, TP: {tp_price:.4f}")
                                    executor.place_market_order(symbol, action, lot_size, sl_price, tp_price)
    
                    last_run_time = current_time

            except Exception as e:
                logging.error(f"Error in main loop cycle: {e}")
                
            time.sleep(5)

    except Exception as e:
        logging.critical(f"System crashed: {e}")
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    main()
