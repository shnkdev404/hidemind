from app.services.matching import detect, expected_gst

VENDOR = {"id": "V01", "gstin": "36AADCD3812M1ZX", "bank_account": "123456789012", "bank_ifsc": "HDFC0000521",
          "email_domain": "deccansteel.in", "bank_verified_on": "2025-05-01"}
PO = {"id": "PO-1", "lines": [{"sku": "A", "unit_price": 100.0, "qty": 10, "gst_rate": 18}]}
GRN = {"id": "GRN-1", "lines": [{"sku": "A", "qty_received": 10}]}


def invoice(**kw):
    lines = kw.pop("lines", [{"sku": "A", "description": "Widget", "qty": 10, "unit_price": 100.0, "gst_rate": 18}])
    charges = kw.pop("charges", [])
    sub = sum(l["qty"] * l["unit_price"] for l in lines) + sum(c["amount"] for c in charges)
    gst = expected_gst(lines, charges) + kw.pop("gst_delta", 0)
    base = {"id": "I1", "vendor_id": "V01", "invoice_no": "X/1", "invoice_date": "2026-07-06", "po_ref": "PO-1",
            "gstin": VENDOR["gstin"], "bank_account": VENDOR["bank_account"], "bank_ifsc": VENDOR["bank_ifsc"],
            "sender_email": "accounts@deccansteel.in", "lines": lines, "charges": charges, "subtotal": sub,
            "gst_amount": round(gst, 2), "total": round(sub + gst, 2)}
    return base | kw


def codes(inv, po=PO, grn=GRN, prior=()):
    return [f.code for f in detect(inv, VENDOR, po, grn, list(prior))]


def test_clean_invoice_has_no_exceptions():
    assert codes(invoice()) == []


def test_price_variance_detected_with_amount():
    inv = invoice(lines=[{"sku": "A", "description": "Widget", "qty": 10, "unit_price": 102.5, "gst_rate": 18}])
    f = detect(inv, VENDOR, PO, GRN, [])
    assert [x.code for x in f] == ["PRICE_VAR"]
    assert f[0].variance_pct == 2.5 and f[0].amount_at_stake == 25.0


def test_price_within_tolerance_ignored():
    inv = invoice(lines=[{"sku": "A", "description": "Widget", "qty": 10, "unit_price": 100.4, "gst_rate": 18}])
    assert codes(inv) == []


def test_qty_over_received():
    assert codes(invoice(), grn={"id": "G", "lines": [{"sku": "A", "qty_received": 9}]}) == ["QTY_VAR"]


def test_charge_not_on_po():
    assert codes(invoice(charges=[{"description": "Freight", "amount": 1200, "gst_rate": 18}])) == ["UNPO_CHARGE"]


def test_tax_rounding_detected():
    assert codes(invoice(gst_delta=0.5)) == ["TAX_CALC"]


def test_bank_change_is_most_severe():
    inv = invoice(bank_account="999999999999", gst_delta=0.5)
    assert codes(inv) == ["BANK_CHANGE", "TAX_CALC"]


def test_duplicate_by_invoice_number():
    prior = invoice(id="I0")
    assert codes(invoice(id="I2"), prior=[prior]) == ["DUPLICATE"]


def test_no_po_reports_vendor_average():
    prior = [invoice(id="P1", invoice_no="A", total=1000.0), invoice(id="P2", invoice_no="B", total=1200.0)]
    f = detect(invoice(po_ref=None, invoice_no="C"), VENDOR, None, None, prior)
    assert f[0].code == "NO_PO" and f[0].detail["vendor_avg_total"] == 1100.0


def test_gstin_mismatch_same_pan():
    f = detect(invoice(gstin="36AADCD3812M2ZY"), VENDOR, PO, GRN, [])
    assert f[0].code == "GSTIN_MISMATCH" and f[0].detail["same_pan"] is True
