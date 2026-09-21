import pandas as pd
import numpy as np
import ta
import logging
from stable_baselines3 import PPO

class FinRLStrategy:
    """
    Live trading strategy that uses a pre-trained FinRL (Stable Baselines 3) model.
    """
    def __init__(self, model_path: str):
        self.model_path = model_path
        try:
            # We force device='cpu' for live inference because the overhead of moving a tiny array 
            # (5 indicators) to the RTX 3050 is slower than just running it on the CPU.
            self.model = PPO.load(model_path, device='cpu')
            logging.info(f"Successfully loaded RL model from {model_path}")
        except Exception as e:
            logging.error(f"Failed to load RL model: {e}")
            self.model = None

    def _prepare_state(self, df: pd.DataFrame) -> np.ndarray:
        """Calculates indicators and formats the latest row exactly as the Gym Env expects."""
        df_calc = df.copy()
        df_calc['ema_fast'] = ta.trend.ema_indicator(df_calc['close'], window=50)
        df_calc['ema_slow'] = ta.trend.ema_indicator(df_calc['close'], window=200)
        df_calc['rsi'] = ta.momentum.rsi(df_calc['close'], window=14)
        df_calc['atr'] = ta.volatility.average_true_range(df_calc['high'], df_calc['low'], df_calc['close'], window=14)
        
        # Extract the last row features corresponding to self.features in ForexTradingEnv
        features = ['close', 'ema_fast', 'ema_slow', 'rsi', 'atr']
        last_row = df_calc.iloc[-1]
        
        # Check for NaNs (since EMA 200 needs 200 candles)
        if last_row.isna().any():
            return None
            
        obs = last_row[features].values
        return np.array(obs, dtype=np.float32)

    def analyze(self, df: pd.DataFrame) -> str:
        """
        Analyzes the dataframe and returns a signal: 'BUY', 'SELL', or 'HOLD'.
        """
        if self.model is None or len(df) < 200:
            return 'HOLD'
            
        state = self._prepare_state(df)
        if state is None:
            return 'HOLD'
            
        # Predict the action using the trained model
        action, _states = self.model.predict(state, deterministic=True)
        
        # Action space: 0 (Hold), 1 (Buy), 2 (Sell)
        if action == 1:
            return 'BUY'
        elif action == 2:
            return 'SELL'
        else:
            return 'HOLD'

    def calculate_sl_tp(self, df: pd.DataFrame, action: str, atr_period: int = 14, atr_multiplier: float = 1.5):
        """
        Calculates Stop Loss and Take Profit prices based on ATR.
        In advanced RL, SL/TP could also be continuous actions chosen by the agent,
        but for discrete actions, an ATR trailing setup is standard.
        """
        df_calc = df.copy()
        df_calc['atr'] = ta.volatility.average_true_range(df_calc['high'], df_calc['low'], df_calc['close'], window=atr_period)
        last_close = df_calc.iloc[-1]['close']
        last_atr = df_calc.iloc[-1]['atr']
        
        if action == 'BUY':
            sl = last_close - (last_atr * atr_multiplier)
            tp = last_close + (last_atr * atr_multiplier * 2)
            return sl, tp
        elif action == 'SELL':
            sl = last_close + (last_atr * atr_multiplier)
            tp = last_close - (last_atr * atr_multiplier * 2)
            return sl, tp
            
        return 0.0, 0.0
