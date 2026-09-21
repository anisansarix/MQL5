import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)

class MT5DataFetcher:
    def __init__(self):
        # Initialize MT5 connection
        if not mt5.initialize():
            logging.error(f"MT5 initialization failed, error code: {mt5.last_error()}")
            raise Exception("Failed to connect to MT5")
        else:
            logging.info(f"Connected to MT5. Terminal version: {mt5.version()}")

    def shutdown(self):
        mt5.shutdown()

    def fetch_historical_data(self, symbol: str, timeframe, num_candles: int = 1000) -> pd.DataFrame:
        """
        Fetches historical OHLCV data for a given symbol and timeframe.
        """
        if not mt5.symbol_select(symbol, True):
            logging.error(f"Failed to select symbol {symbol}")
            return pd.DataFrame()

        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, num_candles)
        
        if rates is None or len(rates) == 0:
            logging.warning(f"No rates retrieved for {symbol}")
            return pd.DataFrame()

        # Convert to pandas DataFrame
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        return df

    def get_current_tick(self, symbol: str):
        """Gets the latest tick (bid/ask) for a symbol."""
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logging.error(f"Failed to get tick for {symbol}")
            return None
        return tick

if __name__ == "__main__":
    # Simple test
    fetcher = MT5DataFetcher()
    df = fetcher.fetch_historical_data("EURUSD", mt5.TIMEFRAME_H1, 10)
    print(df)
    fetcher.shutdown()
