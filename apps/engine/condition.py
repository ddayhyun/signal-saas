# apps/engine/condition.py
from dataclasses import dataclass
from typing import Dict, Tuple

@dataclass
class Thresholds:
    min_trades: int = 10

    mdd_good: float = 0.10
    winrate_good: float = 0.45
    consec_loss_good: int = 3

    # 오버라이드(강등)
    mdd_override: float = 0.15
    consec_loss_override: int = 5

@dataclass
class Weights:
    w30: float = 0.5
    w60: float = 0.3
    w90: float = 0.2

def window_score(m: Dict, th: Thresholds) -> Tuple[int, list]:
    reasons = []
    s = 0
    if m["total_return"] > 0:
        s += 1
    else:
        reasons.append("TotalReturn<=0")
    if m["mdd"] < th.mdd_good:
        s += 1
    else:
        reasons.append("MDD high")
    if m["winrate"] > th.winrate_good:
        s += 1
    else:
        reasons.append("WinRate low")
    if m["consec_loss"] <= th.consec_loss_good:
        s += 1
    else:
        reasons.append("ConsecLoss high")
    return s, reasons

def grade(score: float) -> str:
    if score >= 3.0:
        return "GREEN"
    if score >= 1.5:
        return "YELLOW"
    return "RED"

def downgrade(state: str) -> str:
    return "YELLOW" if state == "GREEN" else ("RED" if state == "YELLOW" else "RED")

def decide_condition(metrics_by_window: Dict[str, Dict], th: Thresholds = Thresholds(), w: Weights = Weights()):
    """
    metrics_by_window: {"30d": {...}, "60d": {...}, "90d": {...}}
    returns: state, score, reasons(list)
    """
    reasons = []
    # 표본 부족 게이트(30d 기준)
    if metrics_by_window["30d"]["trade_count"] < th.min_trades:
        reasons.append("Insufficient trades (<10) in 30d")
        base_state = "YELLOW"
    else:
        s30, r30 = window_score(metrics_by_window["30d"], th)
        s60, r60 = window_score(metrics_by_window["60d"], th)
        s90, r90 = window_score(metrics_by_window["90d"], th)

        score = w.w30 * s30 + w.w60 * s60 + w.w90 * s90
        base_state = grade(score)
        reasons.extend([f"30d:{x}" for x in r30] + [f"60d:{x}" for x in r60] + [f"90d:{x}" for x in r90])

    # 점수 없을 수 있어 계산 안전 처리
    score_val = None
    if base_state != "YELLOW" or "Insufficient trades" not in " ".join(reasons):
        # 위에서 score 계산한 경우만
        try:
            score_val = w.w30 * window_score(metrics_by_window["30d"], th)[0] + \
                        w.w60 * window_score(metrics_by_window["60d"], th)[0] + \
                        w.w90 * window_score(metrics_by_window["90d"], th)[0]
        except Exception:
            score_val = None

    # 오버라이드 강등(30d 기준)
    m30 = metrics_by_window["30d"]
    override_hits = []
    if m30["mdd"] >= th.mdd_override:
        override_hits.append(f"MDD_30d>={th.mdd_override}")
    if m30["consec_loss"] >= th.consec_loss_override:
        override_hits.append(f"ConsecLoss_30d>={th.consec_loss_override}")

    final_state = base_state
    if override_hits:
        final_state = downgrade(final_state)
        reasons.append("Override: " + ", ".join(override_hits))

    return final_state, score_val, reasons
