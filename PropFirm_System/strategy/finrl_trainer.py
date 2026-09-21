import sys
import os
import pandas as pd
import ta
import logging
from stable_baselines3 import PPO
from stable_baselines3.common.vec_env import DummyVecEnv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from strategy.finrl_env import ForexTradingEnv
from data_pipeline.mt5_data_fetcher import MT5DataFetcher
import MetaTrader5 as mt5

logging.basicConfig(level=logging.INFO, format='%(message)s')

def prepare_data(df: pd.DataFrame):
    """Pre-calculates technical indicators for the RL state space."""
    df['ema_fast'] = ta.trend.ema_indicator(df['close'], window=50)
    df['ema_slow'] = ta.trend.ema_indicator(df['close'], window=200)
    df['rsi'] = ta.momentum.rsi(df['close'], window=14)
    df['atr'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14)
    return df.dropna()

def train_agent(symbol="EURUSD", timeframe=mt5.TIMEFRAME_M15, num_candles=50000):
    print(f"--- Fetching Data for Training ({symbol}) ---")
    fetcher = MT5DataFetcher()
    df = fetcher.fetch_historical_data(symbol, timeframe, num_candles)
    fetcher.shutdown()

    if df.empty:
        print("Failed to get historical data.")
        return

    df = prepare_data(df)
    
    # Split data into train and test
    split_idx = int(len(df) * 0.8)
    train_df = df.iloc[:split_idx]
    
    print(f"--- Creating Environment ---")
    env = DummyVecEnv([lambda: ForexTradingEnv(train_df)])
    
    print(f"--- Training PPO Agent (This may take a while) ---")
    # Using PPO (Proximal Policy Optimization)
    model = PPO("MlpPolicy", env, verbose=1)
    
    # Train for 100,000 timesteps
    model.learn(total_timesteps=100000)
    
    tf_str = {mt5.TIMEFRAME_M5: "m5", mt5.TIMEFRAME_M15: "m15", mt5.TIMEFRAME_H1: "h1"}.get(timeframe, "unknown")
    
    os.makedirs('strategy/models', exist_ok=True)
    model_path = f"strategy/models/ppo_{symbol}_{tf_str}"
    model.save(model_path)
    
    print(f"--- Training Complete! Model saved to {model_path}.zip ---")

if __name__ == "__main__":
    train_agent(symbol="XAUUSD", num_candles=20000)
