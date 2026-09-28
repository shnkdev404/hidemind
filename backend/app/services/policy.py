"""Earned autonomy (trust ladder) + hard-rule guard. Pure logic - unit tested, no I/O."""

from dataclasses import dataclass

ACTIONS = ["APPROVE", "APPROVE_PARTIAL", "REJECT", "HOLD", "ESCALATE"]
SAFE_AUTO_ACTIONS = {"APPROVE", "APPROVE_PARTIAL", "REJECT"}
HIGH_RISK_CODES = {"BANK_CHANGE", "DUPLICATE"}

LEVEL_NAMES = {0: "Intern", 1: "Associate", 2: "Senior"}
RECENT_WINDOW = 10


@dataclass
class LadderState:
    level: int = 0
    n_decisions: int = 0
    n_agree: int = 0
    recent: list[bool] | None = None


def _recent_rate(recent: list[bool]) -> float:
    return sum(recent) / len(recent) if recent else 0.0


def update_ladder(state: LadderState, agreed: bool, high_risk: bool) -> tuple[LadderState, str | None]:
    """Record one human-vs-agent comparison. Returns the new state and a change event, if any.

    Intern -> Associate : >= 3 decisions, >= 80% agreement (last 10)
    Associate -> Senior : >= 6 decisions, >= 90% agreement (last 10), last 3 all agreed
    Disagreement        : drop one level; straight to Intern on a high-risk case
    """
    recent = (list(state.recent or []) + [agreed])[-RECENT_WINDOW:]
    new = LadderState(state.level, state.n_decisions + 1, state.n_agree + int(agreed), recent)
    rate = _recent_rate(recent)

    if not agreed:
        new.level = 0 if high_risk else max(0, state.level - 1)
    elif state.level == 0 and new.n_decisions >= 3 and rate >= 0.8:
        new.level = 1
    elif state.level == 1 and new.n_decisions >= 6 and rate >= 0.9 and all(recent[-3:]):
        new.level = 2

    event = None
    if new.level > state.level:
        event = "promoted"
    elif new.level < state.level:
        event = "demoted"
    return new, event


@dataclass
class GuardResult:
    action: str
    overrode: bool
    reason: str | None
    auto_allowed: bool


def apply_guard(action: str, codes: list[str], invoice_total: float,
                escalate_above: float, auto_max: float) -> GuardResult:
    """Code-level financial controls. These mirror the Hindsight directives (defence in depth)."""
    reasons: list[str] = []
    forced = action
    auto_allowed = True

    if "BANK_CHANGE" in codes:
        auto_allowed = False
        if forced != "HOLD":
            forced = "HOLD"
            reasons.append("Bank details differ from verified master - payment held for call-back verification.")
    if "DUPLICATE" in codes and forced in ("APPROVE", "APPROVE_PARTIAL"):
        forced = "HOLD"
        reasons.append("Possible duplicate - never approve without confirming the original was not paid.")
    if invoice_total > escalate_above:
        auto_allowed = False
        if forced in ("APPROVE", "APPROVE_PARTIAL"):
            forced = "ESCALATE"
            reasons.append(f"Invoice above ₹{escalate_above:,.0f} requires Finance Controller approval.")
    if invoice_total > auto_max:
        auto_allowed = False

    return GuardResult(forced, forced != action, " ".join(reasons) or None, auto_allowed)


def can_auto_resolve(level: int, guard: GuardResult, confidence: float, novel: bool) -> bool:
    return (level >= 2 and guard.auto_allowed and not guard.overrode and not novel
            and confidence >= 0.8 and guard.action in SAFE_AUTO_ACTIONS)
