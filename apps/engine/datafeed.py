# apps/engine/datafeed.py
import ccxt
import pandas as pd

def fetch_ohlcv_binance(symbol: str = "BTC/USDT", timeframe: str = "1h", limit: int = 1000) -> pd.DataFrame:
    ex = ccxt.binance({"enableRateLimit": True})
    ohlcv = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df
