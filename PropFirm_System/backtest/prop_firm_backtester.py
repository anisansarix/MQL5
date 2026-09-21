import sys
import os
import pandas as pd
import numpy as np
import ta
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from risk_manager.prop_firm_guard import PropFirmGuard
from data_pipeline.mt5_data_fetcher import MT5DataFetcher
import MetaTrader5 as mt5

logging.basicConfig(level=logging.INFO, format='%(message)s')

class PropFirmBacktester:
    def __init__(self, initial_balance=100000.0, risk_per_trade_usd=500.0):
        self.initial_balance = initial_balance
        self.risk_per_trade_usd = risk_per_trade_usd
        self.guard = PropFirmGuard(initial_balance=initial_balance)
        self.balance = initial_balance
        self.equity_curve = []
        self.trades = []

    def prepare_data(self, df: pd.DataFrame):
        """Pre-calculates all indicators for the entire dataset for fast backtesting."""
        df['ema_fast'] = ta.trend.ema_indicator(df['close'], window=50)
        df['ema_slow'] = ta.trend.ema_indicator(df['close'], window=200)
        df['rsi'] = ta.momentum.rsi(df['close'], window=14)
        df['atr'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14)
        return df.dropna()

    def run(self, symbol: str, timeframe, num_candles: int = 10000):
        print(f"--- Starting Prop Firm Backtest for {symbol} ---")
        fetcher = MT5DataFetcher()
        df = fetcher.fetch_historical_data(symbol, timeframe, num_candles)
        fetcher.shutdown()

        if df.empty:
            print("Failed to get historical data.")
            return

        df = self.prepare_data(df)
        
        open_position = None
        current_day = None

        for index, row in df.iterrows():
            # Update Daily Balance for Prop Firm Rule at the start of a new day
            day_str = index.strftime('%Y-%m-%d')
            if day_str != current_day:
                self.guard.start_of_day_balance = self.balance
                current_day = day_str

            # Check if we hit SL or TP if we have an open position
            if open_position:
                if open_position['type'] == 'BUY':
                    if row['low'] <= open_position['sl']:
                        self._close_trade(index, open_position['sl'], open_position, "Stop Loss")
                        open_position = None
                    elif row['high'] >= open_position['tp']:
                        self._close_trade(index, open_position['tp'], open_position, "Take Profit")
                        open_position = None
                elif open_position['type'] == 'SELL':
                    if row['high'] >= open_position['sl']:
                        self._close_trade(index, open_position['sl'], open_position, "Stop Loss")
                        open_position = None
                    elif row['low'] <= open_position['tp']:
                        self._close_trade(index, open_position['tp'], open_position, "Take Profit")
                        open_position = None
                continue # Skip opening new trades while in a position

            # Prop firm checks (simulated)
            # If our balance ever drops below rules, we fail the challenge.
            daily_dd = (self.guard.start_of_day_balance - self.balance) / self.guard.start_of_day_balance
            total_dd = (self.initial_balance - self.balance) / self.initial_balance
            if daily_dd >= self.guard.max_daily_loss_pct or total_dd >= self.guard.max_total_loss_pct:
                print(f"FAILED PROP FIRM CHALLENGE at {index}. Balance: {self.balance}")
                break

            # Strategy Logic (Replicating base_strategy)
            prev_row = df.shift(1).loc[index]
            
            golden_cross = prev_row['ema_fast'] <= prev_row['ema_slow'] and row['ema_fast'] > row['ema_slow']
            death_cross = prev_row['ema_fast'] >= prev_row['ema_slow'] and row['ema_fast'] < row['ema_slow']

            if golden_cross and row['rsi'] < 70:
                sl = row['close'] - (row['atr'] * 1.5)
                tp = row['close'] + (row['atr'] * 3.0) # 1:2 RR
                open_position = {'type': 'BUY', 'entry_price': row['close'], 'sl': sl, 'tp': tp, 'entry_time': index}
                
            elif death_cross and row['rsi'] > 30:
                sl = row['close'] + (row['atr'] * 1.5)
                tp = row['close'] - (row['atr'] * 3.0)
                open_position = {'type': 'SELL', 'entry_price': row['close'], 'sl': sl, 'tp': tp, 'entry_time': index}

        self.print_results()

    def _close_trade(self, exit_time, exit_price, pos, reason):
        # Simplified PnL calculation (ignoring exact lot sizes and point values for this fast sim)
        # We assume we risk exactly $500 per trade, so a SL is -$500, and a 1:2 TP is +$1000
        if reason == "Stop Loss":
            pnl = -self.risk_per_trade_usd
        elif reason == "Take Profit":
            pnl = self.risk_per_trade_usd * 2.0
            
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
    tester.run("EURUSD", mt5.TIMEFRAME_M15, num_candles=20000)
