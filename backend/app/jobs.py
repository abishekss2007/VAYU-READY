"""ISO 13374 block: Advisory Generation. Checks that warn people before a problem grounds an aircraft.

These run on a timer in the worker (APScheduler) and after relevant writes.
They only create alerts, indents and audit entries. They never change an aircraft's status.
"""
from datetime import timedelta

from . import audit, state
from .config import settings
from .db import utcnow
from .models import Aircraft, Alert, Defect, Engine, Indent, Part, SystemLog

REMINDER_HOURS = (10, 25, 50)


def next_id(db, model, prefix: str) -> str:
    nums = [int(r[0].split("-")[1]) for r in db.query(model.id).all()]
    return f"{prefix}-{(max(nums) if nums else 0) + 1:03d}"


def rul_check(db) -> list[str]:
    """RUL under 25 cycles -> Critical alert. If the needed part is out of stock -> auto-raise an indent."""
    created = []
    engines = db.query(Engine).all()
    preds = state.latest_predictions(db, [e.id for e in engines])
    week_ago = utcnow() - timedelta(days=7)
    for e in engines:
        p = preds.get(e.id)
        if not p or p.rul_cycles >= settings.critical_rul:
            continue
        exists = db.query(Alert).filter(Alert.engine_id == e.id, Alert.kind == "RUL", Alert.created_at > week_ago).first()
        if not exists:
            reason = (p.shap_top3 or [{}])[0].get("text", "sensor trend")
            a = Alert(id=next_id(db, Alert, "ALT"), tail_no=e.tail_no, engine_id=e.id, kind="RUL", severity="Critical",
                      message=f"Engine {e.position} RUL {p.rul_cycles:.0f} cycles (under 25). Top reason: {reason}.",
                      created_at=utcnow(), model_version=p.model_version)
            db.add(a)
            db.flush()
            audit.write(db, "system", "SYSTEM", "ALERT_CREATED", f"Critical alert {a.id} created for {e.tail_no} Engine {e.position} (RUL {p.rul_cycles:.0f} cycles)")
            created.append(a.id)
        part = db.get(Part, state.part_for_prediction(p))
        if part and part.stock < 1:
            open_indent = db.query(Indent).filter(Indent.tail_no == e.tail_no, Indent.part_no == part.part_no, Indent.fitted.is_(False)).first()
            if not open_indent:
                fail_day = int(p.rul_cycles // settings.sorties_per_day)
                ind = Indent(id=next_id(db, Indent, "IND"), part_no=part.part_no, tail_no=e.tail_no, qty=1,
                             reason=f"Predicted failure: Engine {e.position} RUL {p.rul_cycles:.0f} cycles. Raised automatically.",
                             needed_by=state.today() + timedelta(days=max(fail_day - settings.safety_margin_days, 0)),
                             raised_by="system", status="Raised", created_at=utcnow())
                db.add(ind)
                db.flush()
                audit.write(db, "system", "SYSTEM", "INDENT_RAISED", f"Indent {ind.id} auto-raised for {part.part_no} ({e.tail_no})")
                created.append(ind.id)
    db.commit()
    return created


def overhaul_check(db) -> list[str]:
    """Reminders at 50, 25 and 10 hours before an engine's overhaul limit; Critical if past the limit."""
    created = []
    for e in db.query(Engine).all():
        left = state.hours_left(e)
        if left <= 0:
            tag, sev, msg = "(past limit)", "Critical", f"Engine {e.position} is past its overhaul limit. Aircraft locked as not mission-capable (past limit)."
        else:
            thr = next((t for t in REMINDER_HOURS if left <= t), None)
            if thr is None:
                continue
            tag, sev = f"({thr} hours reminder)", "Warning"
            msg = f"Engine {e.position}: {left:.0f} hours left before the overhaul limit {tag}."
        if db.query(Alert).filter(Alert.engine_id == e.id, Alert.kind == "OVERHAUL", Alert.message.contains(tag)).first():
            continue
        a = Alert(id=next_id(db, Alert, "ALT"), tail_no=e.tail_no, engine_id=e.id, kind="OVERHAUL", severity=sev, message=msg, created_at=utcnow())
        db.add(a)
        db.flush()
        audit.write(db, "system", "SYSTEM", "ALERT_CREATED", f"Overhaul alert {a.id} created for {e.id}")
        created.append(a.id)
    db.commit()
    return created


def spares_check(db) -> list[str]:
    """Stock below the reorder point with nothing on order -> raise a reorder indent."""
    created = []
    for part in db.query(Part).filter(Part.stock < Part.reorder_point).all():
        if db.query(Indent).filter(Indent.part_no == part.part_no, Indent.status != "Received").first():
            continue
        ind = Indent(id=next_id(db, Indent, "IND"), part_no=part.part_no, tail_no=None, qty=part.reorder_point - part.stock,
                     reason=f"Stock {part.stock} is below the reorder point {part.reorder_point}. Raised automatically.",
                     needed_by=state.today() + timedelta(days=part.lead_time_days), raised_by="system", status="Raised", created_at=utcnow())
        db.add(ind)
        db.flush()
        audit.write(db, "system", "SYSTEM", "INDENT_RAISED", f"Indent {ind.id} auto-raised for {part.part_no} (below reorder point)")
        created.append(ind.id)
    db.commit()
    return created


def escalate(db) -> list[str]:
    """A critical alert not reviewed within 12 hours is escalated to the Squadron Commander."""
    cutoff = utcnow() - timedelta(hours=settings.review_hours)
    rows = db.query(Alert).filter(Alert.severity == "Critical", Alert.reviewed_at.is_(None), Alert.created_at < cutoff,
                                  Alert.escalated.is_(False)).all()
    for a in rows:
        a.escalated = True
        audit.write(db, "system", "SYSTEM", "ALERT_ESCALATED", f"Alert {a.id} on {a.tail_no} not reviewed within 12 hours: escalated to the Commander")
    db.commit()
    return [a.id for a in rows]


def recurring_check(db, tail_no: str) -> str | None:
    """Same defect system 3 or more times in 30 days on one aircraft -> RECURRING alert."""
    since = utcnow() - timedelta(days=30)
    counts = {}
    for d in db.query(Defect).filter(Defect.tail_no == tail_no, Defect.logged_at > since):
        sys_ = d.confirmed_category or d.suggested_category
        counts[sys_] = counts.get(sys_, 0) + 1
    for sys_, n in counts.items():
        if n >= 3 and not db.query(Alert).filter(Alert.tail_no == tail_no, Alert.kind == "RECURRING", Alert.created_at > since,
                                                 Alert.message.contains(sys_)).first():
            a = Alert(id=next_id(db, Alert, "ALT"), tail_no=tail_no, kind="RECURRING", severity="Warning",
                      message=f"Recurring defect: {sys_} logged {n} times in 30 days.", created_at=utcnow())
            db.add(a)
            db.flush()
            audit.write(db, "system", "SYSTEM", "ALERT_CREATED", f"Recurring-defect alert {a.id} created for {tail_no} ({sys_})")
            return a.id
    return None


def purge_logs(db) -> int:
    """CERT-In Directions 2022: system logs are kept for 180 days. Only older entries are removed."""
    cutoff = utcnow() - timedelta(days=settings.log_retention_days)
    n = db.query(SystemLog).filter(SystemLog.ts < cutoff).delete()
    db.commit()
    return n


def lock_check(db, ac: Aircraft) -> str | None:
    """Returns the reason an aircraft cannot be marked Mission-capable, or None."""
    for e in db.query(Engine).filter(Engine.tail_no == ac.tail_no):
        if state.past_overhaul(e):
            return f"Cannot mark {ac.tail_no} Mission-capable: engine {e.id} is past its overhaul limit. Record the overhaul first."
    pending = db.query(Indent).filter(Indent.tail_no == ac.tail_no, Indent.status != "Received").all()
    if ac.status == "AOG" and pending:
        return f"Cannot release aircraft: required part {pending[0].part_no} has not been received."
    return None


def run_all(db):
    return {"rul": rul_check(db), "overhaul": overhaul_check(db), "spares": spares_check(db), "escalated": escalate(db),
            "logs_purged": purge_logs(db)}
