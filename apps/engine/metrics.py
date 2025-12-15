# apps/engine/metrics.py
import numpy as np
import pandas as pd

def total_return_from_equity(equity: pd.Series) -> float:
    return float(equity.iloc[-1] - 1.0)

def win_rate(trades: pd.DataFrame) -> float:
    if trades is None or len(trades) == 0:
        return float("nan")
    return float((trades["return"] > 0).mean())

def trade_count(trades: pd.DataFrame) -> int:
    return 0 if trades is None else int(len(trades))

def max_drawdown(equity: pd.Series) -> float:
    if equity is None or len(equity) < 2:
        return float("nan")
    peak = equity.cummax()
    dd = (peak - equity) / peak
    return float(dd.max())

def max_consecutive_losses(trades: pd.DataFrame) -> int:
    if trades is None or len(trades) == 0:
        return 0
    is_loss = (trades["return"] <= 0).to_numpy()
    max_run = run = 0
    for x in is_loss:
        if x:
            run += 1
            max_run = max(max_run, run)
        else:
            run = 0
    return int(max_run)
