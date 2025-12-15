
import time
import pandas as pd

from .datafeed import fetch_ohlcv_binance
from .strategy_v1 import apply_indicators
from .simulator import simulate_spot, SimConfig
from .metrics import (
    total_return_from_equity,
    win_rate,
    max_drawdown,
    max_consecutive_losses,
    trade_count,
)
from .condition import decide_condition
from .audit_sqlite import AuditSQLite
from .notifier_telegram import send_telegram


def human_message(state: str, metrics_by_window: dict) -> str:
    m = metrics_by_window["30d"]
    trade_cnt = m["trade_count"]
    winrate = int(m["winrate"] * 100) if m["winrate"] == m["winrate"] else 0  # NaN 방어
    mdd = int(m["mdd"] * 100) if m["mdd"] == m["mdd"] else 0

    if state == "GREEN":
        return f"""📈 트레이드가드 시장 상태 알림

현재 비트코인 시장 상태는
🟢 안정적인 편입니다.

✔ 최근 30일 기준
- 거래 기회가 충분했고
- 큰 손실 없이 비교적 안정적이었습니다.

📊 요약
- 거래 횟수: {trade_cnt}회
- 이긴 비율: 약 {winrate}%
- 최대 손실폭: 약 {mdd}%

👉 단기 매매를 고려해볼 수 있는 구간입니다.
(매수/매도 신호는 제공하지 않습니다)
"""

    if state == "YELLOW":
        return f"""⚠️ 트레이드가드 시장 상태 알림

현재 비트코인 시장은
🟡 애매한 상태입니다.

✔ 최근 거래는 있었지만
성과가 뚜렷하지 않습니다.

👉 지금은 관망이 유리한 구간입니다.
"""

    return f"""🚨 트레이드가드 시장 상태 알림

현재 비트코인 시장은
🔴 위험한 상태입니다.

❗ 최근 손실 위험이 커졌습니다.

👉 신규 진입은 피하고
리스크 관리가 필요한 구간입니다.
"""


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


def _meta_to_ts(v: str | None) -> float | None:
    """
    notify_meta.value를 epoch(문자열)로 저장하는 걸 기본으로 하고,
    혹시 과거에 ISO 문자열이 들어가 있어도 호환 처리.
    """
    if not v:
        return None
    v = str(v).strip()

    # ISO 형식 호환(예: 2025-12-16T10:00:00+00:00)
    if "T" in v:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()

    # epoch 문자열(예: "1734321234.123")
    try:
        return float(v)
    except ValueError:
        return None


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

    # 직전 상태 조회
    last = audit.get_last_state(symbol=symbol, timeframe=timeframe, strategy=strategy_name)
    last_state = last[0] if last else None

    # 현재 상태 저장
    audit.insert(
        symbol=symbol,
        timeframe=timeframe,
        strategy=strategy_name,
        state=state,
        score=score,
        payload={"metrics": metrics_by_window, "reasons": reasons},
    )
    print("Audit saved to audit.db")

    # 12시간 요약 알림(Heartbeat) - timezone 이슈 방지용 epoch 비교
    HEARTBEAT_HOURS = 12
    now_ts = time.time()

    last_hb_raw = audit.get_meta("last_heartbeat_ts")  # 문자열
    last_hb_ts = _meta_to_ts(last_hb_raw)

    state_changed = (last_state != state)
    should_heartbeat = (last_hb_ts is None) or ((now_ts - last_hb_ts) >= HEARTBEAT_HOURS * 3600)

    if state_changed:
        msg = human_message(state, metrics_by_window)
        send_telegram(msg)
        audit.set_meta("last_heartbeat_ts", str(now_ts))
        print("Telegram notified (state changed).")

    elif should_heartbeat:
        msg = "⏰ 12시간 요약 알림\n\n" + human_message(state, metrics_by_window)
        send_telegram(msg)
        audit.set_meta("last_heartbeat_ts", str(now_ts))
        print("Telegram notified (12h heartbeat).")

    else:
        print("No telegram (state unchanged, heartbeat not due).")


if __name__ == "__main__":
    main()
