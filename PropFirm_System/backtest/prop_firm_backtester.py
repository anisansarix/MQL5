import sys
import os
import pandas as pd
import numpy as np
import logging
import pytz
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from risk_manager.prop_firm_guard import PropFirmGuard
from data_pipeline.mt5_data_fetcher import MT5DataFetcher
from strategy.finrl_strategy import FinRLStrategy
import MetaTrader5 as mt5

logging.basicConfig(level=logging.INFO, format='%(message)s')

class MockFetcher:
    def __init__(self, df_h1, df_m15, df_m5):
        self.data = {
            mt5.TIMEFRAME_H1: df_h1,
            mt5.TIMEFRAME_M15: df_m15,
            mt5.TIMEFRAME_M5: df_m5
        }
        self.current_time = None
        
    def fetch_historical_data(self, symbol, timeframe, num_candles):
        df = self.data.get(timeframe, self.data[mt5.TIMEFRAME_M5])
        sliced_df = df[df.index <= self.current_time]
        if sliced_df.empty:
            return pd.DataFrame()
        return sliced_df.iloc[-num_candles:]

class PropFirmBacktester:
    def __init__(self, initial_balance=25000.0, risk_per_trade_usd=125.0):
        self.initial_balance = initial_balance
        self.risk_per_trade_usd = risk_per_trade_usd
        self.guard = PropFirmGuard(initial_balance=initial_balance)
        self.guard.max_daily_loss_pct = 0.04
        self.guard.max_trailing_dd_pct = 0.12
        self.balance = initial_balance
        self.equity_curve = []
        self.trades = []
        self.strategy = FinRLStrategy('strategy/models/ppo_XAUUSD_m5.zip')
        self.spread_points = 20 # Simulate 20 ticks (2.0 pips) spread + slippage
        
    def run(self, symbol: str, num_candles: int = 10000):
        print(f"--- Starting Prop Firm Backtest for {symbol} ---")
        fetcher = MT5DataFetcher()
        df_m5 = fetcher.fetch_historical_data(symbol, mt5.TIMEFRAME_M5, num_candles)
        
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            print("Failed to get symbol info.")
            fetcher.shutdown()
            return
            
        tick_size = symbol_info.trade_tick_size
        tick_value = symbol_info.trade_tick_value
        fetcher.shutdown()

        if df_m5.empty:
            print("Failed to get historical data.")
            return

        # Dummy dfs for other timeframes since FinRL currently relies heavily on the primary timeframe passed via mock fetcher fallback
        mock_fetcher = MockFetcher(df_m5, df_m5, df_m5) 
        
        open_position = None
        current_day = None

        for index in df_m5.index[250:]:
            row = df_m5.loc[index]
            
            day_str = index.strftime('%Y-%m-%d')
            if day_str != current_day:
                self.guard.start_of_day_balance = self.balance
                current_day = day_str

            current_position_float = 0.0
            if open_position:
                current_position_float = 1.0 if open_position['type'] == 'BUY' else -1.0
                
                if open_position['type'] == 'BUY':
                    if row['low'] <= open_position['sl']:
                        self._close_trade(index, open_position['sl'], open_position, "Stop Loss", tick_size, tick_value)
                        open_position = None
                    elif row['high'] >= open_position['tp']:
                        self._close_trade(index, open_position['tp'], open_position, "Take Profit", tick_size, tick_value)
                        open_position = None
                elif open_position['type'] == 'SELL':
                    if row['high'] >= open_position['sl']:
                        self._close_trade(index, open_position['sl'], open_position, "Stop Loss", tick_size, tick_value)
                        open_position = None
                    elif row['low'] <= open_position['tp']:
                        self._close_trade(index, open_position['tp'], open_position, "Take Profit", tick_size, tick_value)
                        open_position = None
                        
                if not open_position:
                    current_position_float = 0.0

            daily_dd = (self.guard.start_of_day_balance - self.balance) / self.guard.start_of_day_balance
            total_dd = (self.initial_balance - self.balance) / self.initial_balance
            if daily_dd >= self.guard.max_daily_loss_pct or total_dd >= self.guard.max_trailing_dd_pct:
                print(f"FAILED PROP FIRM CHALLENGE at {index}. Balance: {self.balance}")
                break

            mock_fetcher.current_time = index
            action, confidence_scale, sl, tp = self.strategy.analyze_symbol(symbol, mock_fetcher, current_position_float)
            
            if open_position:
                if action == 'HOLD' or (action == 'BUY' and open_position['type'] == 'SELL') or (action == 'SELL' and open_position['type'] == 'BUY'):
                    self._close_trade(index, row['close'], open_position, "Strategy Exit", tick_size, tick_value)
                    open_position = None
            
            if action in ['BUY', 'SELL'] and not open_position and sl > 0 and tp > 0 and confidence_scale > 0.05:
                sl_distance_price = abs(row['close'] - sl)
                risk_pct = self.guard.get_dynamic_risk_pct() * confidence_scale
                risk_amount_usd = self.balance * risk_pct
                
                lot_size = self.guard.calculate_position_size(symbol, risk_amount_usd, sl_distance_price)
                if lot_size > 0:
                    open_position = {'type': action, 'entry_price': row['close'], 'sl': sl, 'tp': tp, 'entry_time': index, 'lot_size': lot_size}

        self.print_results()

    def _close_trade(self, exit_time, exit_price, pos, reason, tick_size, tick_value):
        price_diff = abs(exit_price - pos['entry_price'])
        
        # Spread/Slippage Penalty
        price_diff -= (self.spread_points * tick_size)
        
        if price_diff < 0 and reason != "Stop Loss": 
            # If spread ate the profit on a take profit / strategy exit, we can lose money or just break even.
            # But for simplicity, we let price_diff be negative here if spread was bigger than the move.
            pass
            
        ticks_won_lost = price_diff / tick_size
        pnl = ticks_won_lost * tick_value * (pos['lot_size'] / 1.0)
        
        if reason == "Stop Loss":
            # For Stop Loss, the price_diff is distance to SL. We ADD slippage to our loss, so we lost MORE ticks.
            price_diff_sl = abs(exit_price - pos['entry_price']) + (self.spread_points * tick_size)
            ticks_lost = price_diff_sl / tick_size
            pnl = -(ticks_lost * tick_value * (pos['lot_size'] / 1.0))
        elif price_diff < 0 and reason != "Stop Loss":
            # If spread ate profit, it's a loss
            pnl = -(abs(price_diff) / tick_size * tick_value * (pos['lot_size'] / 1.0))
            
        self.balance += pnl
        self.equity_curve.append({'time': exit_time, 'balance': self.balance})
        self.trades.append({
            'entry_time': pos['entry_time'],
            'exit_time': exit_time,
            'type': pos['type'],
            'pnl': pnl,
            'reason': reason
        })

    def print_results(self):
        if not self.trades:
            print("No trades taken.")
            return
            
        wins = [t for t in self.trades if t['pnl'] > 0]
        losses = [t for t in self.trades if t['pnl'] < 0]
        
        print("\n--- Backtest Results ---")
        print(f"Initial Balance: ${self.initial_balance}")
        print(f"Final Balance: ${self.balance}")
        print(f"Total Return: {((self.balance - self.initial_balance) / self.initial_balance) * 100:.2f}%")
        print(f"Total Trades: {len(self.trades)}")
        print(f"Win Rate: {(len(wins) / len(self.trades)) * 100:.2f}%")
        print(f"Prop Firm Status: {'PASSED (Assuming +8% Target)' if self.balance >= self.initial_balance * 1.08 else 'DID NOT PASS YET'}")
        print("------------------------\n")

if __name__ == "__main__":
    tester = PropFirmBacktester()
    tester.run("XAUUSD", num_candles=20000)
