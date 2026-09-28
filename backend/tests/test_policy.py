from app.schemas import DecisionOut
from app.services.narratives import inr
from app.services.policy import LadderState, apply_guard, can_auto_resolve, update_ladder


def run(seq, high_risk=False):
    st, events = LadderState(), []
    for agreed in seq:
        st, ev = update_ladder(st, agreed, high_risk)
        events.append(ev)
    return st, events


def test_intern_promoted_to_associate_after_three_agreements():
    st, ev = run([True, True, True])
    assert st.level == 1 and ev[-1] == "promoted"


def test_senior_needs_six_decisions_and_last_three_agreed():
    st, _ = run([True] * 5)
    assert st.level == 1
    st, _ = run([True] * 6)
    assert st.level == 2


def test_disagreement_drops_one_level():
    st, _ = run([True] * 6 + [False])
    assert st.level == 1


def test_high_risk_disagreement_resets_to_intern():
    st, _ = run([True] * 6)
    st, ev = update_ladder(st, False, high_risk=True)
    assert st.level == 0 and ev == "demoted"


def test_guard_forces_hold_on_bank_change():
    g = apply_guard("APPROVE", ["BANK_CHANGE"], 50_000, 500_000, 200_000)
    assert g.action == "HOLD" and g.overrode and not g.auto_allowed


def test_guard_blocks_duplicate_approval_but_allows_reject():
    assert apply_guard("APPROVE", ["DUPLICATE"], 1000, 500_000, 200_000).action == "HOLD"
    g = apply_guard("REJECT", ["DUPLICATE"], 1000, 500_000, 200_000)
    assert g.action == "REJECT" and not g.overrode and g.auto_allowed


def test_guard_escalates_high_value():
    g = apply_guard("APPROVE", ["PRICE_VAR"], 600_000, 500_000, 200_000)
    assert g.action == "ESCALATE" and not g.auto_allowed


def test_auto_resolve_requires_senior_and_confidence():
    g = apply_guard("APPROVE", ["UNPO_CHARGE"], 50_000, 500_000, 200_000)
    assert can_auto_resolve(2, g, 0.9, False)
    assert not can_auto_resolve(1, g, 0.9, False)
    assert not can_auto_resolve(2, g, 0.6, False)
    assert not can_auto_resolve(2, g, 0.9, True)


def test_decision_schema_normalises_llm_quirks():
    d = DecisionOut.model_validate({"action": "approve partial", "confidence": 85, "rationale": "x"})
    assert d.action == "APPROVE_PARTIAL" and d.confidence == 0.85


def test_inr_indian_grouping():
    assert inr(500000) == "₹5,00,000"
    assert inr(1234567.5) == "₹12,34,567.50"
    assert inr(999) == "₹999"
