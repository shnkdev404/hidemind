"""Hindsight memory service: the agent's institutional memory.

Every Hindsight call in Munshi goes through here. Adds timeouts, a circuit breaker and a clean
"memory off" mode so the rest of the app never has to care whether Hindsight is reachable.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

from hindsight_client import Hindsight

from ..config import get_settings
from ..schemas import DECISION_SCHEMA

log = logging.getLogger("munshi.memory")

# --- Bank definition (used by scripts/setup_bank.py and the demo reset) --------------------------

BANK_NAME = "Munshi - Charminar Foods AP Desk"
MISSION = (
    "You are Munshi, the institutional memory of the Accounts Payable desk at Charminar Foods Pvt Ltd, "
    "an FMCG manufacturer in Hyderabad, India. You remember how every invoice exception was resolved, by whom "
    "and why; vendor-specific agreements and quirks; policy changes; and every fraud attempt. You reason like a "
    "careful senior AP accountant: follow the team's established precedent for the same vendor and exception "
    "type, prefer the most recent policy when precedents conflict, and never put money at risk."
)
RETAIN_MISSION = (
    "Extract: vendor names, exception types, amounts and variance percentages, the decision taken (APPROVE, "
    "APPROVE_PARTIAL, REJECT, HOLD, ESCALATE), the stated reason, who decided and their role, agreements or "
    "contracts referenced, policy changes and their effective dates, bank account and email-domain details, "
    "fraud attempts, and whether the agent's recommendation was confirmed or overridden."
)
OBSERVATIONS_MISSION = (
    "Consolidate recurring patterns per vendor and per exception type, e.g. 'Deccan Steel price variance under "
    "3% is routinely approved because of steel-index pricing'. Track when a pattern changed and why."
)
DISPOSITION = {"skepticism": 5, "literalism": 4, "empathy": 2}

DIRECTIVES = [
    ("bank-change-verification", 100,
     "Never recommend paying to a bank account that differs from the vendor's last verified account. Always "
     "recommend HOLD pending call-back verification on the phone number already on file, even if the request "
     "looks genuine."),
    ("duplicate-block", 90,
     "Never recommend approving an invoice that duplicates one already received from the same vendor (same "
     "invoice number, or same amount and PO within 30 days). Recommend REJECT for a confirmed re-send."),
    ("high-value-escalation", 80,
     "Any invoice with a total above INR 5,00,000 must be recommended for ESCALATE to the Finance Controller, "
     "regardless of precedent."),
    ("cite-evidence", 50,
     "Every recommendation must reference the specific past decisions it relies on (date, vendor, who decided). "
     "If there is no relevant precedent for this vendor and exception type, set novel_case to true, recommend "
     "HOLD and keep confidence at or below 0.4."),
]

PLAYBOOK_ID = "ap-playbook"
FRAUD_ID = "fraud-watchlist"
_REFRESH = {"refresh_after_consolidation": True, "mode": "delta", "min_refresh_interval_seconds": 120}


def dossier_id(vendor_id: str) -> str:
    return f"dossier-{vendor_id.lower()}"


def vendor_tag(vendor_id: str) -> str:
    return f"vendor:{vendor_id.lower()}"


def exc_tag(code: str) -> str:
    return f"exc:{code.lower()}"


def _plain(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    if hasattr(obj, "model_dump"):
        return _plain(obj.model_dump(mode="json"))
    if hasattr(obj, "to_dict"):
        return _plain(obj.to_dict())
    return str(obj)


class MemoryUnavailable(RuntimeError):
    pass


class MemoryService:
    FAILURE_THRESHOLD = 3
    COOLDOWN_S = 60

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: Hindsight | None = None
        self._failures = 0
        self._open_until = 0.0
        self.last_error: str | None = None

    # --- plumbing -------------------------------------------------------------------------------
    @property
    def enabled(self) -> bool:
        return self.settings.memory_enabled

    @property
    def status(self) -> str:
        if not self.enabled:
            return "off"
        return "degraded" if time.monotonic() < self._open_until else "on"

    @property
    def bank(self) -> str:
        return self.settings.bank_id

    def client(self) -> Hindsight:
        if not self.enabled:
            raise MemoryUnavailable("HINDSIGHT_URL is not configured")
        if self._client is None:
            self._client = Hindsight(base_url=self.settings.hindsight_url,
                                     api_key=self.settings.hindsight_api_key or None, timeout=120.0)
        return self._client

    async def _call(self, fn, *args, timeout: float = 90.0, **kwargs):
        if self.status == "degraded":
            raise MemoryUnavailable(f"Hindsight circuit open: {self.last_error}")
        try:
            result = await asyncio.wait_for(fn(*args, **kwargs), timeout=timeout)
        except Exception as e:  # noqa: BLE001 - any failure counts toward the breaker
            self._failures += 1
            self.last_error = f"{type(e).__name__}: {e}"[:300]
            log.warning("Hindsight call %s failed (%d): %s", getattr(fn, "__name__", fn), self._failures, e)
            if self._failures >= self.FAILURE_THRESHOLD:
                self._open_until = time.monotonic() + self.COOLDOWN_S
            raise
        self._failures = 0
        return result

    # --- bank setup -----------------------------------------------------------------------------
    async def setup_bank(self, vendors: list[dict]) -> None:
        c = self.client()
        await c.acreate_bank(
            bank_id=self.bank, name=BANK_NAME, mission=MISSION, reflect_mission=MISSION,
            retain_mission=RETAIN_MISSION, observations_mission=OBSERVATIONS_MISSION,
            disposition=DISPOSITION, enable_observations=True,
        )
        listed = _plain(await c.alist_directives(bank_id=self.bank))
        items = listed.get("items", []) if isinstance(listed, dict) else (listed or [])
        existing = {d.get("name") for d in items if isinstance(d, dict)}
        for name, priority, content in DIRECTIVES:
            if name not in existing:
                await c.acreate_directive(bank_id=self.bank, name=name, content=content, priority=priority)

        models = [
            (PLAYBOOK_ID, "AP Playbook",
             "What are the unwritten rules this AP team follows when resolving invoice exceptions? Group them by "
             "exception type (price variance, quantity mismatch, charges not on PO, duplicates, GSTIN mismatch, "
             "missing PO, GST errors, bank changes). For each rule name the vendors it applies to, the threshold "
             "or condition, the usual action, and when it last changed.", None),
            (FRAUD_ID, "Fraud Watchlist",
             "Which vendors, email domains or patterns have been associated with suspected or confirmed payment "
             "fraud, and which warning signals preceded each incident?", None),
        ] + [
            (dossier_id(v["id"]), f"Vendor Dossier - {v['name']}",
             f"Summarise everything we know about handling invoices from {v['name']}: agreements, recurring "
             f"exceptions and how we resolve them (with thresholds), policy changes, bank and contact details "
             f"history, and any risk signals.", [vendor_tag(v["id"])])
            for v in vendors
        ]
        for mm_id, name, query, tags in models:
            try:
                await c.acreate_mental_model(bank_id=self.bank, id=mm_id, name=name, source_query=query,
                                             tags=tags, max_tokens=1500,
                                             trigger={**_REFRESH, **({"tags_match": "any"} if tags else {})})
            except Exception as e:  # already exists on re-run
                log.info("mental model %s: %s", mm_id, e)

    async def delete_bank(self, bank_id: str | None = None) -> None:
        try:
            await self.client().adelete_bank(bank_id=bank_id or self.bank)
        except Exception as e:  # noqa: BLE001 - deleting a bank that doesn't exist is fine
            log.info("delete_bank %s: %s", bank_id or self.bank, e)

    async def wait_operation(self, bank_id: str, operation_id: str, timeout: float = 600) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            st = await self.client().operations.get_operation_status(bank_id, operation_id)
            status = str(st.status).lower()
            if status in ("completed", "complete", "succeeded", "success", "done"):
                return status
            if status in ("failed", "error", "cancelled", "canceled"):
                raise RuntimeError(f"operation {operation_id} {status}: {st.error_message}")
            await asyncio.sleep(2)
        raise TimeoutError(f"operation {operation_id} did not finish in {timeout}s")

    def snapshot_bank_id(self, name: str) -> str:
        return f"{self.bank}-snap-{name}"

    async def snapshot(self, name: str) -> None:
        """Server-side copy of the live bank (no LLM calls, nothing over the wire)."""
        target = self.snapshot_bank_id(name)
        await self.delete_bank(target)
        op = await self.client().aclone_bank(self.bank, target)
        await self.wait_operation(self.bank, op)

    async def restore(self, name: str) -> None:
        source = self.snapshot_bank_id(name)
        await self.delete_bank(self.bank)
        op = await self.client().aclone_bank(source, self.bank)
        await self.wait_operation(source, op)
        self._failures, self._open_until = 0, 0.0

    # --- retain -----------------------------------------------------------------------------------
    async def retain(self, content: str, *, document_id: str, context: str, tags: list[str],
                     timestamp: datetime | None = None, metadata: dict[str, str] | None = None,
                     wait: bool = False) -> str | None:
        resp = await self._call(
            self.client().aretain, bank_id=self.bank, content=content, context=context,
            document_id=document_id, tags=tags, timestamp=timestamp,
            metadata={k: str(v) for k, v in (metadata or {}).items()}, retain_async=not wait,
            timeout=180.0,
        )
        return getattr(resp, "operation_id", None)

    # --- recall + reflect -------------------------------------------------------------------------
    async def recall_precedents(self, query: str, vendor_id: str, code: str,
                                business_date: datetime | None) -> list[dict]:
        resp = await self._call(
            self.client().arecall, bank_id=self.bank, query=query,
            tags=[vendor_tag(vendor_id), exc_tag(code)], tags_match="any",
            types=["world", "experience", "observation"], budget="mid", max_tokens=2500,
            query_timestamp=business_date.isoformat() if business_date else None,
        )
        out = []
        for r in resp.results or []:
            out.append({
                "id": r.id, "text": r.text, "type": r.type,
                "date": _plain(r.occurred_start or r.mentioned_at),
                "document_id": r.document_id, "metadata": r.metadata or {}, "tags": r.tags or [],
            })
        return out

    async def reflect_decision(self, case_text: str, vendor_id: str, budget: str = "mid") -> tuple[dict | None, dict, str | None]:
        """Returns (structured_output, based_on, error)."""
        resp = await self._call(
            self.client().areflect, bank_id=self.bank, query=case_text,
            context="AP exception triage: recommend a decision for this invoice using the team's precedent.",
            budget=budget, response_schema=DECISION_SCHEMA, include_facts=True,
            tags=[vendor_tag(vendor_id)], tags_match="any", timeout=150.0,
        )
        return resp.structured_output, _plain(resp.based_on) or {}, resp.structured_output_error

    async def ask(self, question: str) -> dict:
        resp = await self._call(self.client().areflect, bank_id=self.bank, query=question,
                                budget="mid", include_facts=True, timeout=150.0)
        return {"text": resp.text, "based_on": _plain(resp.based_on) or {}}

    # --- memory inspector -------------------------------------------------------------------------
    async def overview(self) -> dict:
        """Everything Hindsight holds for this bank, for the Memory Inspector page."""
        c = self.client()

        async def safe(coro):
            try:
                return _plain(await coro)
            except Exception as e:  # noqa: BLE001 - one failing panel must not blank the page
                return {"error": str(e)[:200]}

        profile, stats, directives, models, entities = await asyncio.gather(
            safe(c.banks.get_bank_profile(self.bank)),
            safe(c.banks.get_agent_stats(self.bank)),
            safe(c.alist_directives(bank_id=self.bank)),
            safe(c.alist_mental_models(bank_id=self.bank, detail="metadata")),
            safe(c.entities.list_entities(self.bank, limit=40)),
        )
        return {"bank_id": self.bank, "profile": profile, "stats": stats, "directives": directives,
                "mental_models": models, "entities": entities}

    async def list_items(self, fact_type: str | None, query: str | None, limit: int, offset: int) -> dict:
        resp = await self._call(self.client().alist_memories, bank_id=self.bank, type=fact_type or None,
                                search_query=query or None, limit=limit, offset=offset)
        return _plain(resp)

    async def raw_recall(self, query: str, tags: list[str] | None) -> list[dict]:
        resp = await self._call(self.client().arecall, bank_id=self.bank, query=query, tags=tags or None,
                                tags_match="any", budget="mid", max_tokens=3000)
        return [_plain(r) for r in resp.results or []]

    # --- mental models ----------------------------------------------------------------------------
    async def get_model(self, mm_id: str) -> dict:
        mm = await self._call(self.client().aget_mental_model, bank_id=self.bank, mental_model_id=mm_id,
                              detail="content")
        return _plain(mm)

    async def model_history(self, mm_id: str) -> list[dict]:
        hist = _plain(await self._call(self.client().aget_mental_model_history, bank_id=self.bank,
                                       mental_model_id=mm_id))
        if isinstance(hist, dict):
            hist = hist.get("items") or hist.get("history") or []
        return hist or []

    async def refresh_model(self, mm_id: str) -> None:
        await self._call(self.client().arefresh_mental_model, bank_id=self.bank, mental_model_id=mm_id)

    async def refresh_all(self, vendor_ids: list[str]) -> None:
        for mm_id in [PLAYBOOK_ID, FRAUD_ID] + [dossier_id(v) for v in vendor_ids]:
            try:
                await self.refresh_model(mm_id)
            except Exception as e:  # noqa: BLE001
                log.warning("refresh %s failed: %s", mm_id, e)


memory = MemoryService()
