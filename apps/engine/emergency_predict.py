# apps/engine/emergency_predict.py
import pandas as pd


def bollinger_bandwidth(close: pd.Series, period: int = 20, k: float = 2.0) -> pd.Series:
    ma = close.rolling(period).mean()
    sd = close.rolling(period).std(ddof=0)
    upper = ma + k * sd
    lower = ma - k * sd
    bw = (upper - lower) / ma.replace(0, pd.NA)
    return bw


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)

    tr1 = (high - low).abs()
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    return tr.rolling(period).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0).rolling(period).mean()
    down = (-delta.clip(upper=0)).rolling(period).mean()
    rs = up / down.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))


def compute_emergency_risk(df: pd.DataFrame, cfg: dict) -> dict:
    """
    급변 '가능성' 경보용 위험 점수(0~100).
    - squeeze(변동성 수축) + bw_expand(팽창 시작) + atr_expand(변동성 증가) + vol_spike(거래량 급증)

    반환:
      {
        "score": int,
        "signals": {...},
        "direction_hint": "UP"/"DOWN"/"UNKNOWN"   # 추측
      }
    """
    close = df["close"]
    vol = df["volume"]

    boll_cfg = cfg.get("boll", {})
    atr_cfg = cfg.get("atr", {})
    vol_cfg = cfg.get("volume", {})

    bw = bollinger_bandwidth(
        close,
        period=int(boll_cfg.get("period", 20)),
        k=float(boll_cfg.get("k", 2.0)),
    )
    atrv = atr(df, period=int(atr_cfg.get("period", 14)))
    rsi_v = rsi(close, period=14)

    lookback = int(atr_cfg.get("lookback", 200))
    bw_recent = bw.dropna().tail(lookback)
    atr_recent = atrv.dropna().tail(lookback)

    if len(bw_recent) < 60 or len(atr_recent) < 60:
        return {"score": 0, "signals": {"insufficient": True}, "direction_hint": "UNKNOWN"}

    squeeze_q = float(boll_cfg.get("squeeze_quantile", 0.20))
    bw_thresh = float(bw_recent.quantile(squeeze_q))

    # 직전 캔들이 스퀴즈인지(수축 구간인지)
    is_squeeze = bool(bw.iloc[-2] <= bw_thresh)

    # 현재 밴드폭이 수축 기준 대비 늘기 시작했는지(팽창 시작)
    breakout_mult = float(boll_cfg.get("breakout_mult", 1.5))
    is_bw_expand = bool(bw.iloc[-1] >= bw_thresh * breakout_mult)

    # ATR 팽창
    atr_mean = float(atr_recent.mean())
    expand_mult = float(atr_cfg.get("expand_mult", 1.3))
    is_atr_expand = bool(atrv.iloc[-1] >= atr_mean * expand_mult)

    # 거래량 스파이크
    ma_p = int(vol_cfg.get("ma_period", 20))
    vol_ma = vol.rolling(ma_p).mean()
    spike_mult = float(vol_cfg.get("spike_mult", 1.8))
    is_vol_spike = bool(vol.iloc[-1] >= vol_ma.iloc[-1] * spike_mult) if pd.notna(vol_ma.iloc[-1]) else False

    # 점수(0~100)
    score = 0
    score += 35 if is_squeeze else 0
    score += 35 if is_bw_expand else 0
    score += 20 if is_atr_expand else 0
    score += 10 if is_vol_spike else 0

    # 방향 힌트(추측): 단기 모멘텀 + RSI
    ret_3 = (close.iloc[-1] / close.iloc[-4] - 1.0) if len(close) >= 4 else 0.0
    if ret_3 > 0 and (rsi_v.iloc[-1] >= 55):
        direction = "UP"
    elif ret_3 < 0 and (rsi_v.iloc[-1] <= 45):
        direction = "DOWN"
    else:
        direction = "UNKNOWN"

    return {
        "score": int(score),
        "signals": {
            "squeeze": is_squeeze,
            "bw_expand": is_bw_expand,
            "atr_expand": is_atr_expand,
            "vol_spike": is_vol_spike,
            "bw_thresh": bw_thresh,
        },
        "direction_hint": direction,
    }
