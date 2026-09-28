import json
from datetime import date

from sqlmodel import Session, SQLModel, create_engine, delete, select

from .config import SEED_DIR, get_settings
from . import models as m

_settings = get_settings()
_settings.db_path.parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(
    f"sqlite:///{_settings.db_path}", connect_args={"check_same_thread": False}
)


def get_session():
    with Session(engine) as session:
        yield session


def _d(s: str) -> date:
    return date.fromisoformat(s)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        if s.get(m.SimState, 1) is None:
            s.add(m.SimState(id=1, current_week=0))
            s.commit()
        if s.exec(select(m.Vendor)).first() is None:
            load_reference_data(s)


def load_reference_data(s: Session) -> None:
    """Vendors, POs and GRNs are reference data - loaded once from the seed files."""
    vendors_file = SEED_DIR / "vendors.json"
    if not vendors_file.exists():
        return  # run scripts/generate_data.py first
    for v in json.loads(vendors_file.read_text(encoding="utf-8")):
        s.add(m.Vendor(**{**v, "bank_verified_on": _d(v["bank_verified_on"])}))
    for po in json.loads((SEED_DIR / "purchase_orders.json").read_text(encoding="utf-8")):
        s.add(m.PurchaseOrder(**{**po, "po_date": _d(po["po_date"])}))
    for g in json.loads((SEED_DIR / "grns.json").read_text(encoding="utf-8")):
        s.add(m.GoodsReceipt(**{**g, "received_date": _d(g["received_date"])}))
    s.commit()


def reset_db() -> None:
    """Wipe all transactional data and reload reference data (demo reset to week 0)."""
    with Session(engine) as s:
        for table in (m.Decision, m.Proposal, m.ExceptionCase, m.Invoice, m.TrustCell,
                      m.MemoryOp, m.GoodsReceipt, m.PurchaseOrder, m.Vendor, m.SimState):
            s.exec(delete(table))
        s.add(m.SimState(id=1, current_week=0))
        s.commit()
        load_reference_data(s)
