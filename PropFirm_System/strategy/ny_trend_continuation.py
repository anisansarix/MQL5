import pandas as pd
import ta
import logging
import MetaTrader5 as mt5
import pytz
from datetime import datetime, time

logging.basicConfig(level=logging.INFO)

class NYTrendContinuation:
    def __init__(self):
        self.ny_tz = pytz.timezone('America/New_York')

    def _get_ny_time(self, server_timestamp, offset_hours: int):
        utc_time = server_timestamp - pd.Timedelta(hours=offset_hours)
        utc_time = pytz.utc.localize(utc_time)
        return utc_time.astimezone(self.ny_tz)

    def _is_ny_session(self, current_server_time: datetime, offset_hours: int) -> bool:
        ny_time = self._get_ny_time(current_server_time, offset_hours)
        start_time = time(8, 40)
        end_time = time(11, 30)
        return start_time <= ny_time.time() <= end_time

    def _check_market_structure(self, df: pd.DataFrame, trend: str) -> bool:
        highs = df['high']
        lows = df['low']
        swing_highs = []
        swing_lows = []
        
        for i in range(2, len(df)-2):
            if highs.iloc[i] > highs.iloc[i-1] and highs.iloc[i] > highs.iloc[i-2] and \
               highs.iloc[i] > highs.iloc[i+1] and highs.iloc[i] > highs.iloc[i+2]:
                swing_highs.append(highs.iloc[i])
                
            if lows.iloc[i] < lows.iloc[i-1] and lows.iloc[i] < lows.iloc[i-2] and \
               lows.iloc[i] < lows.iloc[i+1] and lows.iloc[i] < lows.iloc[i+2]:
                swing_lows.append(lows.iloc[i])
                
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            if trend == 'UP':
                return swing_highs[-1] > swing_highs[-2] and swing_lows[-1] > swing_lows[-2]
            elif trend == 'DOWN':
                return swing_highs[-1] < swing_highs[-2] and swing_lows[-1] < swing_lows[-2]
        return False

    def analyze_symbol(self, symbol: str, fetcher):
        df_h1 = fetcher.fetch_historical_data(symbol, mt5.TIMEFRAME_H1, num_candles=100)
        df_m15 = fetcher.fetch_historical_data(symbol, mt5.TIMEFRAME_M15, num_candles=100)
        df_m5 = fetcher.fetch_historical_data(symbol, mt5.TIMEFRAME_M5, num_candles=100)
        
        if df_h1.empty or df_m15.empty or df_m5.empty:
            return 'HOLD', 0.0, 0.0

        last_candle_time = df_m5.index[-1]
        utc_now = datetime.utcnow()
        # Offset calculation: server time - UTC time
        offset_hours = round((last_candle_time - utc_now).total_seconds() / 3600)

        # 1. Trading Session Check
        if not self._is_ny_session(last_candle_time, offset_hours):
            return 'HOLD', 0.0, 0.0

        # 2. H1 Trend Filter
        df_h1['ema20'] = ta.trend.ema_indicator(df_h1['close'], window=20)
        df_h1['ema50'] = ta.trend.ema_indicator(df_h1['close'], window=50)
        h1_last = df_h1.iloc[-1]

        long_trend = h1_last['close'] > h1_last['ema20'] > h1_last['ema50'] and self._check_market_structure(df_h1, 'UP')
        short_trend = h1_last['close'] < h1_last['ema20'] < h1_last['ema50'] and self._check_market_structure(df_h1, 'DOWN')

        if not long_trend and not short_trend:
            return 'HOLD', 0.0, 0.0

        # 3. NY Opening Range (08:20 to 08:40 NY Time)
        df_m5['ny_time'] = [self._get_ny_time(ts, offset_hours) for ts in df_m5.index]
        today = df_m5['ny_time'].iloc[-1].date()
        
        or_mask = (df_m5['ny_time'].dt.date == today) & \
                  (df_m5['ny_time'].dt.time >= time(8, 20)) & \
                  (df_m5['ny_time'].dt.time < time(8, 40))
        
        or_data = df_m5[or_mask]
        if or_data.empty:
            return 'HOLD', 0.0, 0.0

        orh = or_data['high'].max()
        orl = or_data['low'].min()

        # 4. Check 15M Breakout
        df_m15['atr'] = ta.volatility.average_true_range(df_m15['high'], df_m15['low'], df_m15['close'], window=14)
        # 5. Check 5M Pullback & Rejection
        df_m5['atr'] = ta.volatility.average_true_range(df_m5['high'], df_m5['low'], df_m5['close'], window=14)
        m5_last = df_m5.iloc[-1]
        m5_atr = m5_last['atr']

        if long_trend:
            # Check 15M breakout (did it close above ORH without being abnormally large?)
            valid_breakout = False
            for i in range(-5, -1):
                candle = df_m15.iloc[i]
                if candle['close'] > orh and (candle['high'] - candle['low']) <= 1.5 * candle['atr']:
                    valid_breakout = True
                    break
            
            if not valid_breakout:
                return 'HOLD', 0.0, 0.0

            # Wait for price to pull back toward ORH and reject bullishly
            if m5_last['low'] <= orh + (m5_atr * 0.5) and m5_last['close'] > m5_last['open']:
                # Bullish 5M confirmation candle
                sl = df_m5['low'].iloc[-3:].min() - (0.15 * m5_atr)
                tp = m5_last['close'] + 1.5 * (m5_last['close'] - sl)
                return 'BUY', sl, tp

        elif short_trend:
            # Check 15M breakout (did it close below ORL without being abnormally large?)
            valid_breakout = False
            for i in range(-5, -1):
                candle = df_m15.iloc[i]
                if candle['close'] < orl and (candle['high'] - candle['low']) <= 1.5 * candle['atr']:
                    valid_breakout = True
                    break
            
            if not valid_breakout:
                return 'HOLD', 0.0, 0.0

            # Wait for price to pull back toward ORL and reject bearishly
            if m5_last['high'] >= orl - (m5_atr * 0.5) and m5_last['close'] < m5_last['open']:
                # Bearish 5M confirmation candle
                sl = df_m5['high'].iloc[-3:].max() + (0.15 * m5_atr)
                tp = m5_last['close'] - 1.5 * (sl - m5_last['close'])
                return 'SELL', sl, tp

        return 'HOLD', 0.0, 0.0
