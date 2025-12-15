# apps/engine/condition.py
from dataclasses import dataclass
from typing import Dict, Tuple, List, Optional

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


def grade(score: float) -> str:
    if score >= 3.0:
        return "GREEN"
    if score >= 1.5:
        return "YELLOW"
    return "RED"


def downgrade(state: str) -> str:
    if state == "GREEN":
        return "YELLOW"
    if state == "YELLOW":
        return "RED"
    return "RED"


def window_score(m: Dict, th: Thresholds) -> Tuple[int, List[str]]:
    """
    0~4점. reasons에는 각 항목 pass/fail을 명시적으로 남긴다(설명 가능성 확보).
    """
    s = 0
    reasons: List[str] = []

    # TotalReturn
    if m["total_return"] > 0:
        s += 1
        reasons.append("TotalReturn>0 (pass)")
    else:
        reasons.append("TotalReturn<=0 (fail)")

    # MDD
    if m["mdd"] < th.mdd_good:
        s += 1
        reasons.append(f"MDD<{th.mdd_good:.2f} (pass)")
    else:
        reasons.append(f"MDD>={th.mdd_good:.2f} (fail)")

    # WinRate
    if m["winrate"] > th.winrate_good:
        s += 1
        reasons.append(f"WinRate>{th.winrate_good:.2f} (pass)")
    else:
        reasons.append(f"WinRate<={th.winrate_good:.2f} (fail)")

    # ConsecLoss
    if m["consec_loss"] <= th.consec_loss_good:
        s += 1
        reasons.append(f"ConsecLoss<={th.consec_loss_good} (pass)")
    else:
        reasons.append(f"ConsecLoss>{th.consec_loss_good} (fail)")

    return s, reasons


def decide_condition(
    metrics_by_window: Dict[str, Dict],
    th: Thresholds = Thresholds(),
    w: Weights = Weights(),
) -> Tuple[str, float, List[str]]:
    """
    metrics_by_window: {"30d": {...}, "60d": {...}, "90d": {...}}

    반환:
      - state: GREEN/YELLOW/RED
      - score: float (항상 계산됨)
      - reasons: list[str] (항상 설명 포함)
    """
    reasons: List[str] = []

    # 1) 윈도우별 점수 계산(항상)
    s30, r30 = window_score(metrics_by_window["30d"], th)
    s60, r60 = window_score(metrics_by_window["60d"], th)
    s90, r90 = window_score(metrics_by_window["90d"], th)

    score = w.w30 * s30 + w.w60 * s60 + w.w90 * s90

    reasons.append(f"[30d] score={s30}/4, trades={metrics_by_window['30d']['trade_count']}")
    reasons.extend([f"[30d] {x}" for x in r30])

    reasons.append(f"[60d] score={s60}/4, trades={metrics_by_window['60d']['trade_count']}")
    reasons.extend([f"[60d] {x}" for x in r60])

    reasons.append(f"[90d] score={s90}/4, trades={metrics_by_window['90d']['trade_count']}")
    reasons.extend([f"[90d] {x}" for x in r90])

    # 2) 기본 상태(점수 기반)
    base_state = grade(score)

    # 3) 표본 부족 게이트(상태만 YELLOW로 제한, score/reasons는 유지)
    if metrics_by_window["30d"]["trade_count"] < th.min_trades:
        reasons.append(f"Gate: Insufficient trades in 30d (<{th.min_trades}) -> force YELLOW")
        base_state = "YELLOW"

    # 4) 오버라이드 강등(30d 기준)
    m30 = metrics_by_window["30d"]
    override_hits: List[str] = []

    if m30["mdd"] >= th.mdd_override:
        override_hits.append(f"MDD_30d>={th.mdd_override:.2f}")
    if m30["consec_loss"] >= th.consec_loss_override:
        override_hits.append(f"ConsecLoss_30d>={th.consec_loss_override}")

    final_state = base_state
    if override_hits:
        final_state = downgrade(final_state)
        reasons.append("Override downgrade: " + ", ".join(override_hits))

    reasons.append(f"Decision: state={final_state}, score={score:.2f} (base={base_state})")
    return final_state, float(score), reasons
