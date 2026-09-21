import pandas as pd
import ta
import logging

class TrendFollowingStrategy:
    """
    A foundational strategy template using technical analysis (ta library).
    Can be replaced later with FinRL / OpenBB complex logic.
    """
    def __init__(self, ema_fast: int = 50, ema_slow: int = 200, rsi_period: int = 14):
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.rsi_period = rsi_period

    def analyze(self, df: pd.DataFrame) -> str:
        """
        Analyzes the dataframe and returns a signal: 'BUY', 'SELL', or 'HOLD'.
        """
        if len(df) < self.ema_slow:
            return 'HOLD'
            
        # Calculate Indicators
        df['ema_fast'] = ta.trend.ema_indicator(df['close'], window=self.ema_fast)
        df['ema_slow'] = ta.trend.ema_indicator(df['close'], window=self.ema_slow)
        df['rsi'] = ta.momentum.rsi(df['close'], window=self.rsi_period)
        
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]
        
        # Simple Golden Cross / Death Cross logic with RSI filter
        
        # BUY Condition: Fast EMA crosses above Slow EMA and RSI is not overbought (< 70)
        golden_cross = prev_row['ema_fast'] <= prev_row['ema_slow'] and last_row['ema_fast'] > last_row['ema_slow']
        if golden_cross and last_row['rsi'] < 70:
            logging.info(f"Buy Signal generated. RSI: {last_row['rsi']}")
            return 'BUY'
            
        # SELL Condition: Fast EMA crosses below Slow EMA and RSI is not oversold (> 30)
        death_cross = prev_row['ema_fast'] >= prev_row['ema_slow'] and last_row['ema_fast'] < last_row['ema_slow']
        if death_cross and last_row['rsi'] > 30:
            logging.info(f"Sell Signal generated. RSI: {last_row['rsi']}")
            return 'SELL'
            
        return 'HOLD'

    def calculate_sl_tp(self, df: pd.DataFrame, action: str, atr_period: int = 14, atr_multiplier: float = 1.5):
        """
        Calculates Stop Loss and Take Profit prices based on ATR.
        """
        df['atr'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=atr_period)
        last_close = df.iloc[-1]['close']
        last_atr = df.iloc[-1]['atr']
        
        if action == 'BUY':
            sl = last_close - (last_atr * atr_multiplier)
            tp = last_close + (last_atr * atr_multiplier * 2) # 1:2 Risk Reward
            return sl, tp
        elif action == 'SELL':
            sl = last_close + (last_atr * atr_multiplier)
            tp = last_close - (last_atr * atr_multiplier * 2) # 1:2 Risk Reward
            return sl, tp
            
        return 0.0, 0.0
