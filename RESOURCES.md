# Munshi: Repos, Libraries and Prior Art

Every GitHub link below was checked to exist on 2026-09-28. ⭐ = must use / must read.

---

## 1. Hindsight (required technology)

| Repo | What it is | How we use it |
|---|---|---|
| ⭐ [vectorize-io/hindsight](https://github.com/vectorize-io/hindsight) | Hindsight memory engine, API, clients, docs, Docker image | Core memory layer. Read `hindsight-clients/python/hindsight_client/hindsight_client.py` for exact method signatures. |
| ⭐ [vectorize-io/hindsight-cookbook](https://github.com/vectorize-io/hindsight-cookbook) | Official example apps + notebooks | Copy patterns from the apps in §2. The notebooks `01-quickstart`, `02-per-user-memory` and `03-support-agent-shared-knowledge` are the fastest way to learn the API. |
| ⭐ [vectorize-io/self-driving-agents](https://github.com/vectorize-io/self-driving-agents) | 179 Hindsight-powered agent personas (linked from the problem statement) | Read `specialized/finance-ops/accounts-payable-agent.md` and `finance/accounting/bookkeeper-controller.md` and their `bank-template.json` for mission and directive wording. |
| `hindsight/hindsight-integrations/*` (inside the main repo) | Adapters for LangGraph, Pydantic AI, LiteLLM, CrewAI, OpenAI Agents, etc. | Optional. We call `hindsight-client` directly (simpler, more control), but `pydantic-ai` / `litellm` are fallbacks. |
| `hindsight/skills/*` (inside the main repo) | Claude Code / agent skills for Hindsight (cloud, local, architect) | Useful while coding with an AI assistant. |

**Packages:** `pip install hindsight-client` (on PyPI). Docker image: `ghcr.io/vectorize-io/hindsight:latest`.
**Docs:** https://hindsight.vectorize.io · **Cloud:** https://ui.hindsight.vectorize.io (promo code `MEMHACK99`)

---

## 2. Closest existing projects: study these, then differentiate

These are in the official cookbook, so **judges have likely seen them**. We borrow their patterns and make sure Munshi clearly goes further.

| Project | What it does | What we borrow | How Munshi is different |
|---|---|---|---|
| ⭐ [ClaimsIQ](https://github.com/vectorize-io/hindsight-cookbook/tree/main/applications/claims-iq) | Insurance-claims triage agent that goes from "confused rookie" to "seasoned expert" as memories accumulate. FastAPI + Vite/React + `hindsight-litellm`. | Rookie→expert framing; pipeline dashboard; backend/frontend layout. **Closest analogue to Munshi.** | Munshi has **earned autonomy per vendor × exception type** (it actually acts, not just gets smarter), **receipts** from `reflect.based_on`, **fraud memory**, deterministic money math, directives as financial controls, and a self-writing playbook with version history. |
| ⭐ [CableConnect](https://github.com/vectorize-io/hindsight-cookbook/tree/main/applications/cable-co) | Customer-service copilot. The rep approves or rejects suggestions with feedback, and the copilot learns from corrections. Uses `hindsight-client`. Includes an `article.md`. | The approve/reject → retain feedback loop (same as our decision panel). Their `article.md` is a template for our content deliverable. | Ours is finance-specific, with an autonomy ladder driven by agreement stats and hard-rule guards in code. |
| [hindsight-tool-learning-demo](https://github.com/vectorize-io/hindsight-cookbook/tree/main/applications/hindsight-tool-learning-demo) | Shows an LLM learning which ambiguous tool to use | A clean before/after (with vs without memory) comparison | Our Amnesia toggle is the same idea on a real business workflow |
| [stancetracker](https://github.com/vectorize-io/hindsight-cookbook/tree/main/applications/stancetracker) · [deliveryman-demo](https://github.com/vectorize-io/hindsight-cookbook/tree/main/applications/deliveryman-demo) | Other cookbook apps that track changing state over time | Temporal recall patterns | – |

> **Action:** spend 30 minutes running ClaimsIQ locally before building. It is the fastest proof that your Hindsight + Groq setup works, and it shows exactly the bar we need to beat.

---

## 3. Backend (Python)

| Repo | Purpose in Munshi |
|---|---|
| ⭐ [fastapi/fastapi](https://github.com/fastapi/fastapi) | REST API |
| ⭐ [fastapi/sqlmodel](https://github.com/fastapi/sqlmodel) | SQLite ORM (vendors, POs, GRNs, invoices, decisions, trust cells) |
| ⭐ [groq/groq-python](https://github.com/groq/groq-python) | Groq LLM client for the Amnesia baseline and invoice-field extraction |
| ⭐ [jd/tenacity](https://github.com/jd/tenacity) | Retry/backoff on Groq 429s and Hindsight timeouts |
| [pydantic/pydantic-settings](https://github.com/pydantic/pydantic-settings) | `.env` config |
| [sysid/sse-starlette](https://github.com/sysid/sse-starlette) | Server-Sent Events for live toasts ("memorised", "promoted") |
| [BerriAI/litellm](https://github.com/BerriAI/litellm) | *Optional:* provider-agnostic LLM calls; Hindsight has a LiteLLM integration (used by ClaimsIQ) |
| [astral-sh/uv](https://github.com/astral-sh/uv) | Fast Python env/dependency manager |

## 4. Invoice documents (generation + parsing)

| Repo / package | Purpose |
|---|---|
| ⭐ `reportlab` ([PyPI](https://pypi.org/project/reportlab/); the source lives on reportlab.com, not GitHub) | Generate realistic GST invoice PDFs |
| ⭐ [joke2k/faker](https://github.com/joke2k/faker) | Realistic Indian names and addresses (`Faker("en_IN")`) |
| ⭐ [jsvine/pdfplumber](https://github.com/jsvine/pdfplumber) | Extract text and tables from invoice PDFs |
| [py-pdf/pypdf](https://github.com/py-pdf/pypdf) | Lightweight PDF text fallback |
| [invoice-x/invoice2data](https://github.com/invoice-x/invoice2data) | Template-based invoice field extraction (a regex fallback if LLM extraction fails) |
| [docling-project/docling](https://github.com/docling-project/docling) · [microsoft/markitdown](https://github.com/microsoft/markitdown) | *Stretch:* convert arbitrary uploaded invoices to structured text |
| [mindee/doctr](https://github.com/mindee/doctr) · [katanaml/sparrow](https://github.com/katanaml/sparrow) | *Stretch:* OCR for scanned invoices (out of MVP scope) |

## 5. Frontend

| Repo | Purpose |
|---|---|
| ⭐ [vitejs/vite](https://github.com/vitejs/vite) | React + TS build tool |
| ⭐ [tailwindlabs/tailwindcss](https://github.com/tailwindlabs/tailwindcss) | Styling |
| ⭐ [shadcn-ui/ui](https://github.com/shadcn-ui/ui) | Cards, tables, dialogs, badges, toasts (sonner), slider for the playbook history |
| ⭐ [recharts/recharts](https://github.com/recharts/recharts) | Learning curve and metrics charts |
| [TanStack/query](https://github.com/TanStack/query) | API data fetching and caching |
| [mermaid-js/mermaid](https://github.com/mermaid-js/mermaid) | Architecture diagrams in the README (GitHub renders them natively) |

## 6. Realistic data sources (the brief rewards realism)

| Source | Use |
|---|---|
| [katanaml-org/invoices-donut-data-v1](https://huggingface.co/datasets/katanaml-org/invoices-donut-data-v1) (HuggingFace) | Real invoice layouts and field examples for inspiration and extraction testing |
| [mychen76/invoices-and-receipts_ocr_v1](https://huggingface.co/datasets/mychen76/invoices-and-receipts_ocr_v1) (HuggingFace) | Invoice/receipt OCR samples |
| Kaggle: search "invoice", "procurement" or "purchase orders" | Price and quantity distributions for synthetic POs |
| GST HSN code list (cbic-gst.gov.in) | Real HSN codes and GST rates for line items |
| Groq LLM (`gpt-oss-120b`) | Vendor emails, agreement notes, decision reasons in a realistic voice |

## 7. Open-source ERPs (reference for data models, and a future integration story)

| Repo | Why it's relevant |
|---|---|
| [frappe/erpnext](https://github.com/frappe/erpnext) | Indian-built ERP with full **India GST compliance**. Copy its Purchase Invoice / Purchase Receipt / PO field names so our schema looks real. The best "path to adoption" integration target. |
| [frappe/books](https://github.com/frappe/books) | Lightweight accounting app with a simpler AP model |
| [odoo/odoo](https://github.com/odoo/odoo) | 3-way match logic in its `purchase` + `account` modules |
| [akaunting/akaunting](https://github.com/akaunting/akaunting) · [invoiceninja/invoiceninja](https://github.com/invoiceninja/invoiceninja) | Invoice data structures |

Adoption story for the pitch: **Tally Prime, Zoho Books, SAP B1, ERPNext** connectors. Tally and Zoho dominate Indian SMB accounting, but they are closed source, so mention them without building connectors.

## 8. Commercial competitors (know them for Q&A; not repos)

| Product | What they do | Munshi's angle |
|---|---|---|
| Vic.ai, Stampli, AppZen, Tipalti, Ramp AP, Bill.com | AI invoice capture, coding and approval routing | They are mostly extraction + routing. Munshi *learns team-specific exception judgment*, shows receipts, and earns autonomy gradually. It is also built for Indian GST/MSME realities. |
| Zoho Books / Tally AP modules | Rules-based matching | Static rules; nothing learned |

---

## 9. Minimal install list

```bash
pip install hindsight-client fastapi "uvicorn[standard]" sqlmodel pydantic-settings groq tenacity sse-starlette pdfplumber reportlab faker
```

```bash
npm create vite@latest frontend -- --template react-ts
```

```bash
npx shadcn@latest init
```

```bash
npm install recharts @tanstack/react-query
```
