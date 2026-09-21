import os
import sys
import pandas as pd
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv
import MetaTrader5 as mt5
import ta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from strategy.finrl_env import ForexTradingEnv
from data_pipeline.mt5_data_fetcher import MT5DataFetcher

def prepare_data(df: pd.DataFrame):
    df['ema_fast'] = ta.trend.ema_indicator(df['close'], window=50)
    df['ema_slow'] = ta.trend.ema_indicator(df['close'], window=200)
    df['rsi'] = ta.momentum.rsi(df['close'], window=14)
    df['atr'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14)
    return df.dropna()

def backtest_ml_model(symbol, timeframe=mt5.TIMEFRAME_M15, num_candles=10000):
    model_path = f"strategy/models/ppo_{symbol}_m15.zip"
    if not os.path.exists(model_path):
        print(f"Model {model_path} not found!")
        return

    print(f"--- Fetching Backtest Data for {symbol} ---")
    fetcher = MT5DataFetcher()
    df = fetcher.fetch_historical_data(symbol, timeframe, num_candles)
    fetcher.shutdown()

    if df.empty:
        print("Failed to get historical data.")
        return

    df = prepare_data(df)
    
    split_idx = int(len(df) * 0.8)
    test_df = df.iloc[split_idx:]
    test_df = test_df.reset_index(drop=True)

    print(f"--- Loading ML Model for {symbol} ---")
    model = PPO.load(model_path)
    env = DummyVecEnv([lambda: ForexTradingEnv(test_df)])

    obs = env.reset()
    dones = [False]
    
    print(f"--- Starting ML Backtest on Unseen Data (Size: {len(test_df)} candles) ---")
    
    underlying_env = env.envs[0]
    
    steps = 0
    while not dones[0]:
        action, _states = model.predict(obs, deterministic=True)
        obs, rewards, dones, info = env.step(action)
        steps += 1
    
    print(f"Total steps simulated: {steps}")
    final_balance = underlying_env.balance
    initial_balance = underlying_env.initial_balance
    return_pct = ((final_balance - initial_balance) / initial_balance) * 100
    
    print("\n--- ML Backtest Results ---")
    print(f"Symbol Tested: {symbol}")
    print(f"Initial Balance: ${initial_balance}")
    print(f"Final Balance: ${final_balance:.2f}")
    print(f"Total Return (on Test Set): {return_pct:.2f}%")
    print("---------------------------\n")

if __name__ == "__main__":
    backtest_ml_model(sys.argv[1] if len(sys.argv) > 1 else "XAUUSD")
