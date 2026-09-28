from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

Action = Literal["APPROVE", "APPROVE_PARTIAL", "REJECT", "HOLD", "ESCALATE"]


class DecisionOut(BaseModel):
    """What the agent must return. Validated after every LLM / reflect call."""

    action: Action
    approved_amount_inr: Optional[float] = None
    confidence: float = Field(ge=0, le=1)
    rationale: str
    precedents_used: list[str] = []
    risk_flags: list[str] = []
    novel_case: bool = False

    @field_validator("action", mode="before")
    @classmethod
    def _upper(cls, v):
        return str(v).strip().upper().replace(" ", "_")

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp(cls, v):
        v = float(v)
        return v / 100 if v > 1 else max(0.0, v)


DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["APPROVE", "APPROVE_PARTIAL", "REJECT", "HOLD", "ESCALATE"]},
        "approved_amount_inr": {"type": "number"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "rationale": {"type": "string"},
        "precedents_used": {"type": "array", "items": {"type": "string"}},
        "risk_flags": {"type": "array", "items": {"type": "string"}},
        "novel_case": {"type": "boolean"},
    },
    "required": ["action", "confidence", "rationale", "novel_case"],
}

ACTION_GUIDE = """Actions:
- APPROVE: pay the invoice as billed.
- APPROVE_PARTIAL: pay only the justified amount (e.g. received quantity); give approved_amount_inr.
- REJECT: do not pay; return to vendor (e.g. duplicate, unjustified charge).
- HOLD: park the invoice pending verification or vendor clarification.
- ESCALATE: send to the Finance Controller."""


class DecideIn(BaseModel):
    action: Action
    reason: str = ""
    decided_by: str = "Priya Reddy"
    role: str = "AP Lead"
    approved_amount: Optional[float] = None


class AskIn(BaseModel):
    question: str
