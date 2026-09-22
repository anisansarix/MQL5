import pandas as pd
import numpy as np
import ta
import logging
import MetaTrader5 as mt5
from stable_baselines3 import PPO

class FinRLStrategy:
    """
    Live trading strategy that uses a pre-trained FinRL (Stable Baselines 3) model
    with Continuous Action Space.
    """
    def __init__(self, model_path: str):
        self.model_path = model_path
        try:
            self.model = PPO.load(model_path, device='cpu')
            logging.info(f"Successfully loaded RL model from {model_path}")
        except Exception as e:
            logging.error(f"Failed to load RL model: {e}")
            self.model = None

    def _prepare_state(self, df: pd.DataFrame, current_position: float) -> np.ndarray:
        df_calc = df.copy()
        df_calc['ema_fast'] = ta.trend.ema_indicator(df_calc['close'], window=50)
        df_calc['ema_slow'] = ta.trend.ema_indicator(df_calc['close'], window=200)
        df_calc['rsi'] = ta.momentum.rsi(df_calc['close'], window=14)
        df_calc['atr'] = ta.volatility.average_true_range(df_calc['high'], df_calc['low'], df_calc['close'], window=14)
        
        df_calc['close_norm'] = df_calc['close'].pct_change()
        df_calc['ema_fast_norm'] = (df_calc['ema_fast'] / df_calc['close']) - 1.0
        df_calc['ema_slow_norm'] = (df_calc['ema_slow'] / df_calc['close']) - 1.0
        df_calc['rsi_norm'] = df_calc['rsi'] / 100.0
        df_calc['atr_norm'] = df_calc['atr'] / df_calc['close']
        
        features = ['close_norm', 'ema_fast_norm', 'ema_slow_norm', 'rsi_norm', 'atr_norm']
        last_row = df_calc.iloc[-1]
        
        if last_row.isna().any():
            return None
            
        obs = list(last_row[features].values)
        obs.append(current_position)
        return np.array(obs, dtype=np.float32)

    def analyze_symbol(self, symbol: str, fetcher, current_position: float = 0.0) -> tuple:
        """
        Analyzes the dataframe and returns a tuple: (action, confidence_scale, sl_price, tp_price)
        """
        action = 'HOLD'
        confidence_scale = 0.0
        sl_price = 0.0
        tp_price = 0.0
        
        if self.model is None:
            return action, confidence_scale, sl_price, tp_price
            
        df = fetcher.fetch_historical_data(symbol, timeframe=mt5.TIMEFRAME_M5, num_candles=250)
        if df.empty or len(df) < 200:
            return action, confidence_scale, sl_price, tp_price
            
        state = self._prepare_state(df, current_position)
        if state is None:
            return action, confidence_scale, sl_price, tp_price
            
        # Predict the action using the trained continuous model
        rl_action, _states = self.model.predict(state, deterministic=True)
        target_pos = float(np.clip(rl_action[0], -1.0, 1.0))
        
        # Calculate SL / TP using ATR
        df_calc = df.copy()
        df_calc['atr'] = ta.volatility.average_true_range(df_calc['high'], df_calc['low'], df_calc['close'], window=14)
        last_close = df_calc.iloc[-1]['close']
        last_atr = df_calc.iloc[-1]['atr']
        atr_multiplier = 1.5
        
        # Determine the action string and confidence scale based on the target position
        if target_pos > 0.05:
            action = 'BUY'
            confidence_scale = target_pos
            sl_price = last_close - (last_atr * atr_multiplier)
            tp_price = last_close + (last_atr * atr_multiplier * 2)
        elif target_pos < -0.05:
            action = 'SELL'
            confidence_scale = abs(target_pos)
            sl_price = last_close + (last_atr * atr_multiplier)
            tp_price = last_close - (last_atr * atr_multiplier * 2)
        else:
            action = 'HOLD'
            confidence_scale = 0.0
            
        return action, confidence_scale, sl_price, tp_price
