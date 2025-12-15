# apps/engine/run_condition.py
import pandas as pd

from .datafeed import fetch_ohlcv_binance
from .strategy_v1 import apply_indicators
from .simulator import simulate_spot, SimConfig
from .metrics import total_return_from_equity, win_rate, max_drawdown, max_consecutive_losses, trade_count
from .condition import decide_condition
from .audit_sqlite import AuditSQLite

def slice_last_days(df: pd.DataFrame, days: int) -> pd.DataFrame:
    end = df["timestamp"].max()
    start = end - pd.Timedelta(days=days)
    return df[df["timestamp"] >= start].copy()

def compute_window_metrics(df_window: pd.DataFrame) -> dict:
    res = simulate_spot(df_window, SimConfig(fee_roundtrip=0.002, stop_loss=0.02, take_profit=0.04))
    trades = res["trades"]
    equity = res["equity"]
    return {
        "total_return": total_return_from_equity(equity),
        "winrate": win_rate(trades),
        "mdd": max_drawdown(equity),
        "consec_loss": max_consecutive_losses(trades),
        "trade_count": trade_count(trades),
    }

def main():
    symbol = "BTC/USDT"
    timeframe = "15m"
    strategy_name = "MA20/50 + RSI14"

    df = fetch_ohlcv_binance(symbol=symbol, timeframe=timeframe, limit=10000)
    df = apply_indicators(df, fast=20, slow=50, rsi_period=14)

    m30 = compute_window_metrics(slice_last_days(df, 30))
    m60 = compute_window_metrics(slice_last_days(df, 60))
    m90 = compute_window_metrics(slice_last_days(df, 90))

    metrics_by_window = {"30d": m30, "60d": m60, "90d": m90}
    state, score, reasons = decide_condition(metrics_by_window)

    print("STATE:", state)
    print("SCORE:", score)
    print("METRICS:", metrics_by_window)
    print("REASONS:", reasons[:8], ("..." if len(reasons) > 8 else ""))

    audit = AuditSQLite(path="audit.db")
    audit.insert(
        symbol=symbol,
        timeframe=timeframe,
        strategy=strategy_name,
        state=state,
        score=score,
        payload={"metrics": metrics_by_window, "reasons": reasons},
    )
    print("Audit saved to audit.db")

if __name__ == "__main__":
    main()
