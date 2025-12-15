# apps/engine/strategy_v1.py
import pandas as pd
from .indicators import sma, rsi

def apply_indicators(df: pd.DataFrame, fast: int = 20, slow: int = 50, rsi_period: int = 14) -> pd.DataFrame:
    out = df.copy()
    out["sma_fast"] = sma(out["close"], fast)
    out["sma_slow"] = sma(out["close"], slow)
    out["rsi"] = rsi(out["close"], rsi_period)
    return out

def entry_condition(row) -> bool:
    return (row["sma_fast"] > row["sma_slow"]) and (row["rsi"] < 40)

def exit_condition(row) -> bool:
    return (row["rsi"] > 60)
