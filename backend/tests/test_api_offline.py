"""End-to-end plumbing with Hindsight and Groq switched off: the app must degrade, never break."""

from fastapi.testclient import TestClient

from app.main import app


def test_full_offline_flow():
    with TestClient(app) as c:
        h = c.get("/api/health").json()
        assert h["memory"] == "off" and h["llm"] == "off" and h["week"] == 0

        r = c.post("/api/simulate/next-week?wait=true").json()
        assert r["week"] == 1 and r["exceptions"] > 0 and not r["errors"]

        # History week: every case got a (fallback) proposal and the scripted human decision.
        resolved = c.get("/api/queue?status=resolved").json()
        assert len(resolved) == r["exceptions"]
        assert all(x["proposal"]["mode"] == "FALLBACK" and x["decision"] for x in resolved)

        detail = c.get(f"/api/cases/{resolved[0]['id']}").json()
        assert "ground_truth" not in detail["invoice"]
        assert detail["invoice"]["bank_account"].startswith("••••")

        m = c.get("/api/metrics").json()
        assert m["weeks"][0]["exceptions"] == r["exceptions"]
        assert c.get("/api/trust").json()["cells"]

        # Memory-only endpoints report 503 cleanly instead of crashing.
        assert c.post("/api/ask", json={"question": "hi"}).status_code == 503


def test_live_decision_updates_trust():
    with TestClient(app) as c:
        c.post("/api/demo/reset?to=week0")
        for _ in range(13):
            c.post("/api/simulate/next-week?wait=true")
        open_cases = c.get("/api/queue?status=open").json()
        assert open_cases, "week 13 is a live week - cases should wait for a human"
        case = open_cases[0]
        d = c.post(f"/api/cases/{case['id']}/decide",
                   json={"action": "APPROVE", "reason": "test", "decided_by": "Tester"}).json()
        assert d["action"] == "APPROVE"
        assert c.post(f"/api/cases/{case['id']}/decide", json={"action": "APPROVE"}).status_code == 409
