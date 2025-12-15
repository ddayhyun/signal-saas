# apps/engine/simulator.py
import pandas as pd
from dataclasses import dataclass
from .strategy_v1 import entry_condition, exit_condition

@dataclass
class SimConfig:
    fee_roundtrip: float = 0.002  # 0.2% (매수+매도 합산)
    stop_loss: float = 0.02       # -2%
    take_profit: float = 0.04     # +4%

def simulate_spot(df: pd.DataFrame, cfg: SimConfig = SimConfig()) -> dict:
    """
    df must contain: ['timestamp','open','high','low','close','volume','sma_fast','sma_slow','rsi']
    """
    in_pos = False
    entry_price = None
    trades = []

    for i in range(len(df)):
        row = df.iloc[i]

        # 지표가 NaN인 구간 스킵
        if pd.isna(row["sma_fast"]) or pd.isna(row["sma_slow"]) or pd.isna(row["rsi"]):
            continue

        price = float(row["close"])

        if not in_pos:
            if entry_condition(row):
                in_pos = True
                entry_price = price
                entry_time = row["timestamp"]
        else:
            # 손절/익절 먼저 체크(종가 기준 단순화)
            ret = (price - entry_price) / entry_price
            hit_sl = ret <= -cfg.stop_loss
            hit_tp = ret >= cfg.take_profit
            hit_exit = exit_condition(row)

            if hit_sl or hit_tp or hit_exit:
                exit_price = price
                exit_time = row["timestamp"]
                trade_ret = (exit_price - entry_price) / entry_price - cfg.fee_roundtrip
                trades.append({
                    "entry_time": entry_time,
                    "entry_price": entry_price,
                    "exit_time": exit_time,
                    "exit_price": exit_price,
                    "return": trade_ret,
                    "reason": "SL" if hit_sl else ("TP" if hit_tp else "RSI")
                })
                in_pos = False
                entry_price = None

    # 누적 자본곡선
    equity = [1.0]
    for t in trades:
        equity.append(equity[-1] * (1.0 + t["return"]))

    return {
        "trades": pd.DataFrame(trades),
        "equity": pd.Series(equity)
    }
