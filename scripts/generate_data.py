"""Generate Munshi's synthetic-but-realistic AP world (deterministic, seed=42).

Outputs (data/seed/):
  meta.json, vendors.json, purchase_orders.json, grns.json, background.json,
  invoices/week_XX.json (+ invoices/pdf/<id>.pdf)

Each vendor has a hidden "personality" - a rule the AP team applies that Munshi must learn from decisions.
Weeks 1-12 are history (scripted human decisions); weeks 13-14 are live/eval weeks (ground truth only).

Usage: python scripts/generate_data.py [--no-pdf]
"""

import argparse
import json
import random
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from faker import Faker  # noqa: E402

from app.services.matching import expected_gst  # noqa: E402

SEED_DIR = ROOT / "data" / "seed"
WEEK1 = date(2026, 7, 6)  # Monday. Week 13 = 28 Sep 2026.
N_WEEKS = 14

rng = random.Random(42)
fake = Faker("en_IN")
Faker.seed(42)

PRIYA = ("Priya Reddy", "AP Lead")
RAVI = ("Ravi Kumar", "Senior AP Accountant")
ANJALI = ("Anjali Rao", "AP Associate")
SURESH = ("Suresh Iyer", "Finance Controller")

COMPANY = {
    "name": "Charminar Foods Pvt Ltd",
    "address": "Plot 42, IDA Cherlapally Phase II, Hyderabad, Telangana 500051",
    "state_code": "36",
    "pan": "AAHCC4521K",
}


# --- GSTIN with a valid checksum ---------------------------------------------------------------

_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def gstin(state: str, pan: str, entity: str = "1") -> str:
    body = f"{state}{pan}{entity}Z"
    total = 0
    for i, ch in enumerate(body):
        prod = _CHARS.index(ch) * (1 if i % 2 == 0 else 2)
        total += prod // 36 + prod % 36
    return body + _CHARS[(36 - total % 36) % 36]


COMPANY["gstin"] = gstin(COMPANY["state_code"], COMPANY["pan"])


def week_day(week: int, offset: int | None = None) -> date:
    return WEEK1 + timedelta(weeks=week - 1, days=rng.randint(0, 4) if offset is None else offset)


# --- Vendor master -------------------------------------------------------------------------------

VENDORS = [
    dict(id="V01", code="DSA", name="Deccan Steel & Alloys Pvt Ltd", city="Hyderabad", state="36", pan="AADCD3812M",
         msme=False, email_domain="deccansteel.in", ifsc="HDFC0000521", category="Raw material - steel",
         catalog=[("STL-CRCA-08", "CRCA Steel Coil 0.8mm", "7209", "MT", 68500, 18),
                  ("STL-HRS-20", "HR Steel Sheet 2.0mm", "7208", "MT", 61200, 18)]),
    dict(id="V02", code="SLP", name="Sri Lakshmi Packaging Industries", city="Secunderabad", state="36",
         pan="ABPFS7721Q", msme=False, email_domain="srilakshmipack.com", ifsc="SBIN0020417",
         category="Packaging",
         catalog=[("PKG-BOX-5P", "Corrugated Box 5-Ply (450x300x250)", "4819", "PCS", 38, 18),
                  ("PKG-POUCH-1K", "Laminated Pouch 1kg (printed)", "3923", "PCS", 2.4, 18)]),
    dict(id="V03", code="NCS", name="Nimbus Cloud Services Pvt Ltd", city="Bengaluru", state="29", pan="AAFCN5530H",
         msme=False, email_domain="nimbuscloud.io", ifsc="ICIC0000104", category="IT - SaaS",
         catalog=[("SAAS-ERP-M", "ERP Cloud Subscription - 45 users (monthly)", "998315", "MON", 84000, 18),
                  ("SAAS-STO-500", "Additional Storage 500 GB (monthly)", "998315", "MON", 6500, 18)]),
    dict(id="V04", code="GAP", name="Godavari Agro Produce", city="Rajahmundry", state="37", pan="AGKPG1964L",
         msme=True, email_domain="godavariagro.co.in", ifsc="ANDB0001190", category="Raw material - pulses",
         catalog=[("AGR-CHANA", "Chana Dal (bulk, 50kg bags)", "0713", "KG", 92, 5),
                  ("AGR-TOOR", "Toor Dal (bulk, 50kg bags)", "0713", "KG", 118, 5)]),
    dict(id="V05", code="APX", name="Apex Logistics", city="Hyderabad", state="36", pan="ACOFA2287D",
         msme=False, email_domain="apexlogistics.in", ifsc="UTIB0000733", category="Logistics",
         catalog=[("LOG-FTL-VJA", "FTL Freight Hyderabad -> Vijayawada (32ft)", "996511", "TRIP", 28000, 12)]),
    dict(id="V06", code="HCL", name="Hyderabad Chemicals Ltd", city="Patancheru", state="36", pan="AAACH6120P",
         msme=False, email_domain="hydchem.com", ifsc="KKBK0007712", category="Food additives",
         catalog=[("CHM-CITRIC", "Citric Acid Monohydrate (food grade)", "2918", "KG", 165, 18),
                  ("CHM-BENZ", "Sodium Benzoate (food grade)", "2916", "KG", 210, 18)]),
    dict(id="V07", code="TSP", name="TSSPDCL (Southern Power Distribution Co. of Telangana)", city="Hyderabad",
         state="36", pan="AAFCT4130N", msme=False, email_domain="tssouthernpower.com", ifsc="SBIN0005943",
         category="Utilities",
         catalog=[("UTL-HT-POWER", "HT Electricity Charges - Service No. CHP-11-4471", "2716", "BILL", 0, 0)]),
    dict(id="V08", code="KCC", name="Krishna Cold Chain Logistics", city="Vijayawada", state="37", pan="AAKFK9102E",
         msme=False, email_domain="kccl.in", ifsc="HDFC0001866", category="Logistics - reefer",
         catalog=[("LOG-REEFER", "Reefer Transport Hyderabad -> Vijayawada (temp-controlled)", "996511", "TRIP",
                   42000, 12)]),
    dict(id="V09", code="BJP", name="Banjara Printers", city="Hyderabad", state="36", pan="BXQPB4471R", msme=True,
         email_domain="banjaraprinters.com", ifsc="CNRB0003321", category="Printing",
         catalog=[("PRN-LBL-4C", "Printed Labels 4-colour (100x70mm)", "4821", "PCS", 1.85, 18),
                  ("PRN-PLATE", "Carton Printing Plates (set)", "8442", "SET", 4500, 12)]),
    dict(id="V10", code="TOS", name="Telangana Office Supplies", city="Hyderabad", state="36", pan="ADVPT3390F",
         msme=True, email_domain="tosupplies.in", ifsc="SBIN0011204", category="Stationery",
         catalog=[("OFF-A4-75", "A4 Copier Paper 75 GSM (ream)", "4802", "REAM", 245, 12),
                  ("OFF-TONER", "Toner Cartridge HP 88A", "8443", "PCS", 2150, 18)]),
    dict(id="V11", code="GIT", name="Golconda IT Services", city="Hyderabad", state="36", pan="AAGCG8814B",
         msme=False, email_domain="golcondait.com", ifsc="ICIC0001432", category="IT - AMC",
         catalog=[("IT-AMC-Q", "Desktop & Network AMC (monthly)", "998713", "MON", 38000, 18)]),
    dict(id="V12", code="HSW", name="Hussain Sagar Aqua Pvt Ltd", city="Hyderabad", state="36", pan="AAHCH2256K",
         msme=False, email_domain="hsaqua.in", ifsc="HDFC0002215", category="Canteen supplies",
         catalog=[("CAN-WATER-20", "Packaged Drinking Water 20L Jar", "2201", "JAR", 65, 18)]),
]
V = {v["id"]: v for v in VENDORS}

for v in VENDORS:
    v["gstin"] = gstin(v["state"], v["pan"])
    v["bank_account"] = str(rng.randint(10**11, 10**12 - 1))
    v["address"] = f"{fake.building_number()}, {fake.street_name()}, {v['city']}"
    v["bank_verified_on"] = str(date(2025, rng.randint(1, 12), rng.randint(1, 28)))

# --- Builders ------------------------------------------------------------------------------------

POS, GRNS, INVOICES, BACKGROUND = [], [], {w: [] for w in range(1, N_WEEKS + 1)}, []
_seq = {"po": 7700, "grn": 5100, "inv": {}}


def _sku(vendor: dict, sku: str):
    return next(c for c in vendor["catalog"] if c[0] == sku)


def make_invoice(vid: str, week: int, items: list[tuple[str, float]], *, price_pct: dict | None = None,
                 unit_price: dict | None = None, received: dict | None = None, charges: list | None = None,
                 gst_delta: float = 0.0, bank: tuple | None = None, sender: str | None = None,
                 gstin_override: str | None = None, invoice_no: str | None = None, po: str | None = "new",
                 day: int | None = None, truth: tuple | None = None, gt_amount: float | None = None) -> dict:
    """items: [(sku, qty)]. Creates PO + GRN (unless po=None) and the invoice. Returns the invoice dict."""
    v = V[vid]
    inv_date = week_day(week, day)
    po_id = None
    if po == "new":
        _seq["po"] += 1
        po_id = f"PO-26{_seq['po']:04d}"
        po_lines = []
        for sku, qty in items:
            c = _sku(v, sku)
            price = unit_price.get(sku, c[4]) if unit_price else c[4]
            po_lines.append({"sku": sku, "description": c[1], "hsn": c[2], "unit": c[3], "qty": qty,
                             "unit_price": price, "gst_rate": c[5]})
        POS.append({"id": po_id, "vendor_id": vid, "po_date": str(inv_date - timedelta(days=rng.randint(6, 12))),
                    "lines": po_lines})
        _seq["grn"] += 1
        GRNS.append({"id": f"GRN-{_seq['grn']}", "po_id": po_id,
                     "received_date": str(inv_date - timedelta(days=rng.randint(0, 2))),
                     "lines": [{"sku": sku, "qty_received": (received or {}).get(sku, qty)} for sku, qty in items]})
    elif po:
        po_id = po

    lines = []
    for sku, qty in items:
        c = _sku(v, sku)
        base = unit_price.get(sku, c[4]) if unit_price else c[4]
        price = round(base * (1 + (price_pct or {}).get(sku, 0) / 100), 2)
        lines.append({"sku": sku, "description": c[1], "hsn": c[2], "unit": c[3], "qty": qty,
                      "unit_price": price, "gst_rate": c[5]})
    charges = charges or []
    subtotal = round(sum(l["qty"] * l["unit_price"] for l in lines) + sum(c["amount"] for c in charges), 2)
    gst_amt = round(expected_gst(lines, charges) + gst_delta, 2)

    n = _seq["inv"].get(vid, 400 + rng.randint(0, 80)) + 1
    _seq["inv"][vid] = n
    inv_id = f"INV-{v['code']}-{n:04d}-W{week:02d}"
    inv = {
        "id": inv_id, "vendor_id": vid,
        "invoice_no": invoice_no or f"{v['code']}/26-27/{n:04d}",
        "invoice_date": str(inv_date), "po_ref": po_id,
        "gstin": gstin_override or v["gstin"],
        "bank_account": bank[0] if bank else v["bank_account"], "bank_ifsc": bank[1] if bank else v["ifsc"],
        "sender_email": sender or f"accounts@{v['email_domain']}",
        "lines": lines, "charges": charges, "subtotal": subtotal, "gst_amount": gst_amt,
        "total": round(subtotal + gst_amt, 2), "week": week,
        "pdf_path": f"data/seed/invoices/pdf/{inv_id}.pdf",
        "ground_truth": None,
    }
    if truth:
        action, (who, role), reason = truth
        inv["ground_truth"] = {"action": action, "decided_by": who, "role": role, "reason": reason,
                               "approved_amount": gt_amount}
    INVOICES[week].append(inv)
    return inv


def background(bid: str, d: date, context: str, content: str, tags: list[str]):
    BACKGROUND.append({"id": bid, "date": str(d), "context": context, "content": content, "tags": tags})


def vt(vid: str) -> str:
    return f"vendor:{vid.lower()}"


# --- Scenario ------------------------------------------------------------------------------------

def build():
    # Deccan Steel - index pricing. <3% approve; >3% escalate. From week 8, Controller lowers the limit to 2%.
    policy_date = WEEK1 + timedelta(weeks=7)
    deccan = {
        1: (2.1, "APPROVE", PRIYA, "Deccan Steel is on steel-index pricing (JPC monthly index). A variance under 3% of PO is expected - approve."),
        2: (1.4, "APPROVE", RAVI, "Within the 3% index band for Deccan Steel - approved."),
        3: (2.6, "HOLD", ANJALI, "Not sure why the price is higher than the PO - holding to check with the purchase team."),
        4: (1.8, "APPROVE", PRIYA, "Reminder for the team: Deccan Steel prices follow the steel index; anything within 3% of PO is approved without holding."),
        5: (4.6, "ESCALATE", PRIYA, "4.6% is outside the 3% index band - escalated to Suresh (Finance Controller)."),
        6: (2.3, "APPROVE", RAVI, "Index-linked variance under 3% - approved as usual for Deccan."),
        7: (1.2, "APPROVE", RAVI, "Small index variance - approved."),
        8: (1.7, "APPROVE", PRIYA, f"Within the new 2% limit Suresh set on {policy_date:%d %b} - approved."),
        9: (2.4, "ESCALATE", PRIYA, "2.4% is above the 2% limit from Suresh's policy - escalated to the Controller."),
        10: (1.6, "APPROVE", RAVI, "Under 2% - approved per the Controller's policy."),
        11: (2.8, "ESCALATE", RAVI, "Over 2% - per the Controller's policy this goes to Suresh."),
        12: (1.1, "ESCALATE", PRIYA, "Variance is fine but this is a large order above Rs 5 lakh - needs Controller approval."),
        13: (1.9, "APPROVE", PRIYA, "Within the 2% limit - approve."),
        14: (2.5, "ESCALATE", PRIYA, "Above 2% - escalate to the Controller."),
    }
    for w, (pct, action, who, reason) in deccan.items():
        qty = (4, 4) if w == 12 else (round(rng.uniform(0.8, 1.2), 2), round(rng.uniform(0.6, 1.0), 2))
        make_invoice("V01", w, [("STL-CRCA-08", qty[0]), ("STL-HRS-20", qty[1])],
                     price_pct={"STL-CRCA-08": pct, "STL-HRS-20": pct}, truth=(action, who, reason))
    background("bg-deccan-policy", policy_date, "Email from Suresh Iyer, Finance Controller",
               f"Email from Suresh Iyer (Finance Controller) to the AP team on {policy_date:%d %b %Y}: "
               "\"Steel index volatility has gone up. Effective today, any Deccan Steel & Alloys invoice with a price "
               "variance above 2% over PO must be escalated to me. AP can continue to approve variances up to 2%. "
               "This replaces the earlier 3% band.\"",
               [vt("V01"), "exc:price_var", "policy"])

    # Sri Lakshmi Packaging - Rs 1,200 freight per delivery is agreed. More than that -> hold.
    for w in range(1, N_WEEKS + 1):
        freight = 3500 if w == 10 else 2800 if w == 14 else 1200
        if freight == 1200:
            who = rng.choice([PRIYA, RAVI, ANJALI])
            truth = ("APPROVE", who, rng.choice([
                "Freight of Rs 1,200 per delivery is billed separately under our 2024 packaging agreement - approve.",
                "Standard Rs 1,200 freight for Sri Lakshmi - approved.",
                "Agreed freight charge, not on PO by design - approve."]))
        else:
            truth = ("HOLD", PRIYA, f"Freight of Rs {freight:,} exceeds the agreed Rs 1,200 per delivery - asked "
                                    "Sri Lakshmi to justify or revise.")
        make_invoice("V02", w, [("PKG-BOX-5P", rng.choice([1500, 2000, 2500])),
                                ("PKG-POUCH-1K", rng.choice([8000, 10000, 12000]))],
                     charges=[{"description": "Freight & handling", "amount": freight, "gst_rate": 18}],
                     truth=truth)

    # Nimbus Cloud - their billing portal re-sends unpaid invoices after ~7 days -> duplicates, reject.
    for w in (1, 5, 9, 13):
        original = make_invoice("V03", w, [("SAAS-ERP-M", 1), ("SAAS-STO-500", 1)], day=0)
        if w + 1 <= N_WEEKS:
            make_invoice("V03", w + 1, [("SAAS-ERP-M", 1), ("SAAS-STO-500", 1)], po=original["po_ref"],
                         invoice_no=original["invoice_no"], day=2,
                         truth=("REJECT", RAVI, f"Duplicate re-send of {original['invoice_no']} - the original is "
                                                "already booked. Nimbus's portal auto re-sends unpaid invoices."))

    # Godavari Agro (MSME) - partial deliveries are normal; pay for GRN quantity. MSME 45-day clock matters.
    for w in range(1, N_WEEKS + 1):
        chana, toor = rng.choice([1500, 2000]), rng.choice([1000, 1500])
        if w % 2 == 0:
            rc, rt = int(chana * rng.uniform(0.93, 0.98)), toor
            amount = round((rc * 92 + rt * 118) * 1.05, 2)
            make_invoice("V04", w, [("AGR-CHANA", chana), ("AGR-TOOR", toor)], received={"AGR-CHANA": rc},
                         truth=("APPROVE_PARTIAL", rng.choice([RAVI, ANJALI]),
                                f"Pay only for the GRN quantity ({rc} kg chana dal); the shortfall comes in the next "
                                "dispatch. Godavari is an MSME - release within 45 days."),
                         gt_amount=amount)
        else:
            make_invoice("V04", w, [("AGR-CHANA", chana), ("AGR-TOOR", toor)])

    # Apex Logistics - never changes bank details. Week 9: look-alike domain fraud attempt.
    for w in range(1, N_WEEKS + 1):
        for _ in range(2):
            make_invoice("V05", w, [("LOG-FTL-VJA", rng.randint(3, 5))])
    fraud_acct = str(rng.randint(10**11, 10**12 - 1))
    make_invoice("V05", 9, [("LOG-FTL-VJA", 4)], bank=(fraud_acct, "ICIC0006789"),
                 sender="accounts@apex-logistics.co", day=3,
                 truth=("HOLD", PRIYA, "Call-back to Apex on the number in our vendor master: they never asked for a "
                                       "bank change. The email came from the look-alike domain apex-logistics.co "
                                       "(real one is apexlogistics.in). Fraud attempt - reported to IT security."))
    background("bg-apex-fraud-outcome", WEEK1 + timedelta(weeks=8, days=4), "Outcome confirmation - IT security",
               "Outcome: the Apex Logistics bank-change request (email from apex-logistics.co, new ICICI account) was "
               "confirmed as a business email compromise attempt. Apex's real domain is apexlogistics.in and their "
               "bank details have not changed since onboarding. The look-alike domain was blocked.",
               [vt("V05"), "risk", "exc:bank_change", "outcome"])

    # Hyderabad Chemicals - new Unit-II GSTIN from week 5. Hold once, verified in week 6, approve after.
    hcl_unit2 = gstin("36", V["V06"]["pan"], "2")
    for w in range(1, N_WEEKS + 1):
        items = [("CHM-CITRIC", rng.choice([300, 400, 500])), ("CHM-BENZ", rng.choice([100, 150]))]
        if w >= 5 and w % 2 == 1:
            truth = (("HOLD", RAVI, "GSTIN on the invoice (entity code 2) differs from our vendor master. Asked "
                                    "Hyderabad Chemicals for the GST registration certificate of the new unit before "
                                    "we book input tax credit.") if w == 5 else
                     ("APPROVE", RAVI, f"Invoice from Unit-II; GSTIN {hcl_unit2} verified on the GST portal "
                                       "(certificate on file) - approve."))
            make_invoice("V06", w, items, gstin_override=hcl_unit2, truth=truth)
        else:
            make_invoice("V06", w, items)
    background("bg-hcl-unit2", WEEK1 + timedelta(weeks=5, days=1), "Email from Hyderabad Chemicals + GST portal check",
               f"Hyderabad Chemicals Ltd sent the GST registration certificate for their new Unit-II at Patancheru "
               f"Phase 2 (GSTIN {hcl_unit2}, same PAN, active since 01 Jun 2026). Ravi Kumar verified it on the GST "
               f"portal. Invoices from Unit-II will carry this GSTIN and are valid; the master record keeps the "
               f"head-office GSTIN.",
               [vt("V06"), "exc:gstin_mismatch"])

    # TSSPDCL - electricity, never has a PO. Approve if in line with the monthly average; spikes -> hold.
    base = 172000
    for w in (1, 5, 9, 13):
        amt = round(base * (1.42 if w == 9 else rng.uniform(0.94, 1.06)), 2)
        month = (WEEK1 + timedelta(weeks=w - 1) - timedelta(days=20)).strftime("%b %Y")
        truth = (("HOLD", PRIYA, "Bill is ~42% above our usual monthly power bill - asked plant maintenance to verify "
                                 "the meter reading before paying.") if w == 9 else
                 ("APPROVE", rng.choice([PRIYA, ANJALI]), "Electricity bill - utilities never have a PO. Amount is in "
                                                          "line with the monthly average - approve."))
        make_invoice("V07", w, [("UTL-HT-POWER", 1)], unit_price={"UTL-HT-POWER": amt}, po=None, day=1, truth=truth)
        INVOICES[w][-1]["lines"][0]["description"] += f" ({month})"

    # Krishna Cold Chain - fuel surcharge up to 5% is contractual. Week 14: genuine bank change -> still HOLD.
    background("bg-kccl-contract", date(2026, 4, 2), "Rate contract - Krishna Cold Chain Logistics",
               "Rate contract FY 2026-27 with Krishna Cold Chain Logistics (signed 02 Apr 2026): reefer trips "
               "Hyderabad-Vijayawada at Rs 42,000 per trip. A diesel-linked fuel surcharge of up to 5% of the freight "
               "value may be billed as a separate line; anything above 5% needs a revised quote approved by "
               "procurement.",
               [vt("V08"), "exc:unpo_charge", "contract"])
    for w, pct in {1: 2.1, 3: 3.4, 5: 4.2, 7: 2.8, 9: 3.9, 11: 7.5, 13: 3.2}.items():
        trips = rng.randint(2, 3)
        amt = round(trips * 42000 * pct / 100, 2)
        truth = (("HOLD", RAVI, f"Fuel surcharge of {pct}% is above the 5% cap in the rate contract - asked Krishna "
                                "Cold Chain for a revised invoice.") if pct > 5 else
                 ("APPROVE", rng.choice([RAVI, ANJALI]), f"Fuel surcharge {pct}% is within the 5% contractual cap - "
                                                         "approve."))
        make_invoice("V08", w, [("LOG-REEFER", trips)],
                     charges=[{"description": f"Fuel surcharge ({pct}%)", "amount": amt, "gst_rate": 12}], truth=truth)
    make_invoice("V08", 14, [("LOG-REEFER", 2)], bank=(str(rng.randint(10**11, 10**12 - 1)), "SBIN0000813"),
                 truth=("HOLD", PRIYA, "Bank change letter came from their real domain, but policy is call-back "
                                       "verification before any bank change - holding until verified."))

    # Banjara Printers (MSME) - GST rounding differences under Rs 1 are accepted.
    for w in range(1, N_WEEKS + 1):
        items = [("PRN-LBL-4C", rng.choice([15000, 20000, 25000])), ("PRN-PLATE", rng.choice([1, 2]))]
        if w % 2 == 0:
            delta = {2: 0.42, 4: 0.66, 6: -0.38, 8: 145.0, 10: 0.71, 12: -0.55, 14: 0.61}[w]
            truth = (("REJECT", RAVI, "GST charged at 18% on printing plates instead of 12% - returned the invoice "
                                      "for correction.") if w == 8 else
                     ("APPROVE", rng.choice([ANJALI, RAVI]), f"GST rounding difference of Rs {abs(delta):.2f} (under "
                                                             "Re 1) - accept, not worth a credit note."))
            make_invoice("V09", w, items, gst_delta=delta, truth=truth)
        else:
            make_invoice("V09", w, items)

    # Clean vendors (noise) + one price-variance rejection.
    for w in range(1, N_WEEKS + 1):
        make_invoice("V12", w, [("CAN-WATER-20", rng.choice([250, 300, 350]))])
        if w % 2 == 1:
            if w == 7:
                make_invoice("V10", w, [("OFF-A4-75", 60), ("OFF-TONER", 4)], price_pct={"OFF-A4-75": 8.2},
                             truth=("REJECT", PRIYA, "Copier paper billed 8% above the rate contract (Rs 245/ream) - "
                                                     "rejected, asked for a corrected invoice."))
            else:
                make_invoice("V10", w, [("OFF-A4-75", rng.choice([40, 50, 60])), ("OFF-TONER", rng.choice([2, 3, 4]))])
        if w in (3, 7, 11):
            make_invoice("V11", w, [("IT-AMC-Q", 1)], day=0)

    background("bg-deccan-fraud-march", date(2026, 3, 18), "Incident report - AP / IT security",
               "Incident (18 Mar 2026): an email from deccan-steels.in (look-alike of Deccan Steel & Alloys' real "
               "domain deccansteel.in) asked AP to update Deccan's bank account to a new Axis Bank account before "
               "month-end. Priya Reddy did a call-back on the number in the vendor master; Deccan confirmed they had "
               "not requested any change. Confirmed business email compromise attempt - no payment was made.",
               [vt("V01"), "risk", "exc:bank_change", "outcome"])
    background("bg-nimbus-billing", date(2026, 2, 10), "Note from Nimbus Cloud account manager",
               "Nimbus Cloud Services account manager note: their billing portal automatically re-sends any invoice "
               "that is unpaid after 7 days, with the same invoice number.",
               [vt("V03"), "exc:duplicate"])


# --- PDF rendering -------------------------------------------------------------------------------

def render_pdf(inv: dict, path: Path):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    v = V[inv["vendor_id"]]
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm, topMargin=14 * mm)
    rs = lambda x: f"Rs {x:,.2f}"  # noqa: E731 - base fonts have no rupee glyph
    story = [
        Paragraph(f"<b>{v['name']}</b>", styles["Title"]),
        Paragraph(f"{v['address']} | GSTIN: {inv['gstin']} | {inv['sender_email']}", styles["Normal"]),
        Spacer(1, 6),
        Paragraph("<b>TAX INVOICE</b>", styles["Heading2"]),
        Table([
            ["Invoice No.", inv["invoice_no"], "Bill To", COMPANY["name"]],
            ["Invoice Date", inv["invoice_date"], "", COMPANY["address"]],
            ["PO Reference", inv["po_ref"] or "-", "Buyer GSTIN", COMPANY["gstin"]],
        ], colWidths=[28 * mm, 45 * mm, 24 * mm, 80 * mm],
            style=[("FONTSIZE", (0, 0), (-1, -1), 8), ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                   ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"), ("VALIGN", (0, 0), (-1, -1), "TOP")]),
        Spacer(1, 8),
    ]
    rows = [["#", "Description", "HSN/SAC", "Qty", "Unit", "Rate", "GST %", "Taxable Value"]]
    for i, l in enumerate(inv["lines"], 1):
        rows.append([i, Paragraph(l["description"], styles["BodyText"]), l["hsn"], f"{l['qty']:g}", l["unit"],
                     f"{l['unit_price']:,.2f}", f"{l['gst_rate']:g}", f"{l['qty'] * l['unit_price']:,.2f}"])
    for c in inv["charges"]:
        rows.append(["", c["description"], "996511", "", "", "", f"{c.get('gst_rate', 18):g}", f"{c['amount']:,.2f}"])
    intra = inv["gstin"][:2] == COMPANY["state_code"]
    tax_rows = ([["", "", "", "", "", "", "CGST", f"{inv['gst_amount'] / 2:,.2f}"],
                 ["", "", "", "", "", "", "SGST", f"{inv['gst_amount'] / 2:,.2f}"]] if intra else
                [["", "", "", "", "", "", "IGST", f"{inv['gst_amount']:,.2f}"]])
    rows += [["", "", "", "", "", "", "Taxable", f"{inv['subtotal']:,.2f}"], *tax_rows,
             ["", "", "", "", "", "", "TOTAL", rs(inv["total"])]]
    t = Table(rows, colWidths=[8 * mm, 62 * mm, 18 * mm, 14 * mm, 12 * mm, 20 * mm, 16 * mm, 28 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, len(rows) - len(tax_rows) - 3), 0.3, colors.grey),
        ("ALIGN", (3, 1), (-1, -1), "RIGHT"), ("FONTNAME", (6, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    story += [t, Spacer(1, 12),
              Paragraph(f"<b>Bank details for payment:</b> A/c No. {inv['bank_account']} | IFSC {inv['bank_ifsc']}",
                        styles["Normal"]),
              Spacer(1, 4),
              Paragraph("This is a computer-generated invoice. Subject to Hyderabad jurisdiction.", styles["Italic"])]
    doc.build(story)


# --- main ----------------------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-pdf", action="store_true", help="skip PDF rendering (faster)")
    args = ap.parse_args()

    build()
    inv_dir = SEED_DIR / "invoices"
    if inv_dir.exists():
        shutil.rmtree(inv_dir)
    (inv_dir / "pdf").mkdir(parents=True)

    vendors_out = [{k: v[k] for k in ("id", "name", "city", "gstin", "msme", "email_domain", "bank_account",
                                      "bank_verified_on", "category")} | {"bank_ifsc": v["ifsc"]} for v in VENDORS]
    (SEED_DIR / "vendors.json").write_text(json.dumps(vendors_out, indent=2), encoding="utf-8")
    (SEED_DIR / "purchase_orders.json").write_text(json.dumps(POS, indent=2), encoding="utf-8")
    (SEED_DIR / "grns.json").write_text(json.dumps(GRNS, indent=2), encoding="utf-8")
    (SEED_DIR / "background.json").write_text(json.dumps(sorted(BACKGROUND, key=lambda b: b["date"]), indent=2),
                                              encoding="utf-8")
    (SEED_DIR / "meta.json").write_text(json.dumps({"week1_start": str(WEEK1), "weeks": N_WEEKS, "history_weeks": 12,
                                                    "company": COMPANY}, indent=2), encoding="utf-8")
    n_inv = n_exc = 0
    for w, invs in INVOICES.items():
        invs.sort(key=lambda i: i["invoice_date"])
        (inv_dir / f"week_{w:02d}.json").write_text(json.dumps(invs, indent=2), encoding="utf-8")
        n_inv += len(invs)
        n_exc += sum(1 for i in invs if i["ground_truth"])
        if not args.no_pdf:
            for inv in invs:
                render_pdf(inv, ROOT / inv["pdf_path"])
    print(f"Generated {len(VENDORS)} vendors, {len(POS)} POs, {n_inv} invoices ({n_exc} scripted exceptions), "
          f"{len(BACKGROUND)} background memories -> {SEED_DIR}")


if __name__ == "__main__":
    main()
