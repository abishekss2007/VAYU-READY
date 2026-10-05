"""ISO 13374 block: Health Assessment. Digital twin, health score, Fleet Health Score and forecast inputs.

Everything a write endpoint must refresh lives here, so a defect, a review or a spare
received is entered once and shows up everywhere.
"""
import math
from datetime import date, timedelta

from sqlalchemy import func

from optimiser.forecast import AircraftState, Need, fleet_forecast

from .config import settings
from .db import iso, utcnow
from .models import (Aircraft, Alert, BaseStation, Defect, Engine, HangarSlot, Indent, Part, Prediction, SensorReading,
                     Squadron, Task)

STATUS_LABEL = {"MC": "Mission-capable", "PMC": "Partially capable", "AOG": "AOG", "MAINT": "In maintenance"}
HEALTH_FORMULA = ("health = 100 x the lowest engine RUL / 125, minus 10 if the anomaly flag is on, "
                  "minus 5 for each open defect (never below 0)")
# Which module a predicted failure needs, from the sensor that drives the prediction most
SENSOR_PART = {"s3": "HPC-MOD-07", "s7": "HPC-MOD-07", "s11": "HPC-MOD-07", "s12": "HPC-MOD-07",
               "s4": "LPT-MOD-04", "s20": "LPT-MOD-04", "s21": "LPT-MOD-04",
               "s2": "FAN-MOD-02", "s8": "FAN-MOD-02", "s13": "FAN-MOD-02", "s15": "FAN-MOD-02",
               "s9": "CORE-BRG-09", "s14": "CORE-BRG-09", "s17": "CORE-BRG-09"}
RESOLVING_KINDS = ("engine_change", "overhaul", "defect_fix")


def today() -> date:
    return utcnow().date()


def latest_predictions(db, engine_ids) -> dict:
    if not engine_ids:
        return {}
    sub = (db.query(Prediction.engine_id, func.max(Prediction.id).label("mid"))
           .filter(Prediction.engine_id.in_(engine_ids)).group_by(Prediction.engine_id).subquery())
    rows = db.query(Prediction).join(sub, Prediction.id == sub.c.mid).all()
    return {p.engine_id: p for p in rows}


def part_for_prediction(pred) -> str:
    top = (pred.shap_top3 or [{}])[0].get("sensor") if pred else None
    return SENSOR_PART.get(top, "HPC-MOD-07")


def hours_left(e: Engine) -> float:
    return round(e.overhaul_limit_hours - e.hours_since_overhaul, 1)


def past_overhaul(e: Engine) -> bool:
    return e.hours_since_overhaul >= e.overhaul_limit_hours


def indent_arrival_day(ind: Indent, part: Part, expedite=()) -> int:
    """Days from today until the part is on the shelf."""
    if ind.status == "Received":
        return 0
    eta = ind.created_at + timedelta(days=part.lead_time_days)
    days = max(math.ceil((eta - utcnow()).total_seconds() / 86400), 0)
    return min(days, 2) if part.part_no in expedite else days


def refresh_health(db, tails) -> None:
    """Recompute the health score (0-100) of the given aircraft."""
    for tail in set(tails):
        ac = db.get(Aircraft, tail)
        if not ac:
            continue
        engines = db.query(Engine).filter(Engine.tail_no == tail).all()
        preds = latest_predictions(db, [e.id for e in engines])
        ac.health_score = health_breakdown(db, ac, preds)["score"]
    db.flush()


def health_breakdown(db, ac, preds) -> dict:
    ruls = [p.rul_cycles for p in preds.values()]
    base = round(100 * min(min(ruls) / 125, 1)) if ruls else 100
    anomaly = any(p.anomaly_score >= 0.5 for p in preds.values())
    open_defects = db.query(Defect).filter(Defect.tail_no == ac.tail_no, Defect.status == "Open").count()
    score = max(base - (10 if anomaly else 0) - 5 * open_defects, 0)
    return {"score": score, "formula": HEALTH_FORMULA,
            "lines": [{"label": "Lowest engine RUL", "points": base},
                      {"label": "Anomaly flag", "points": -10 if anomaly else 0},
                      {"label": f"Open defects ({open_defects})", "points": -5 * open_defects}]}


# ---------- forecast inputs ----------

def squadron_aircraft(db, squadron_code):
    return (db.query(Aircraft).filter(Aircraft.squadron_code == squadron_code, Aircraft.archived.is_(False))
            .order_by(Aircraft.tail_no).all())


def build_states(db, squadron_code, sorties_per_day=None, expedite=(), only_tails=None) -> list[AircraftState]:
    """Turn database rows into the plain objects the forecast and optimiser work on."""
    spd = sorties_per_day or settings.sorties_per_day
    H, margin = settings.horizon_days, settings.safety_margin_days
    t0 = today()
    acs = squadron_aircraft(db, squadron_code)
    tails = [a.tail_no for a in acs]
    engines = db.query(Engine).filter(Engine.tail_no.in_(tails)).all() if tails else []
    preds = latest_predictions(db, [e.id for e in engines])
    parts = {p.part_no: p for p in db.query(Part).all()}
    indents = db.query(Indent).filter(Indent.tail_no.in_(tails), Indent.fitted.is_(False)).all() if tails else []
    tasks = db.query(Task).filter(Task.tail_no.in_(tails), Task.status.in_(["Scheduled", "Done"])).all() if tails else []
    states = []
    for ac in acs:
        st = AircraftState(tail=ac.tail_no, status=ac.status, combat_ready=ac.combat_ready, transport_ready=ac.transport_ready)
        my_tasks = [t for t in tasks if t.tail_no == ac.tail_no]
        for t in my_tasks:
            start, end = max((t.slot_start - t0).days, 0), (t.slot_end - t0).days + 1
            if end > start:
                st.committed.append((start, end - start))
        causes = []  # (kind, title, duration, earliest, deadline, hard, part_no, engine_id, risk_day)
        for e in [e for e in engines if e.tail_no == ac.tail_no]:
            p = preds.get(e.id)
            if p:
                fd = int(p.rul_cycles // spd)
                if fd <= H:
                    st.fail_day = fd if st.fail_day is None else min(st.fail_day, fd)
                    part_no = part_for_prediction(p)
                    arrival = _part_arrival(parts.get(part_no), [i for i in indents if i.tail_no == ac.tail_no and i.part_no == part_no], expedite)
                    causes.append(("engine_change", f"Engine {e.position} change (RUL {p.rul_cycles:.0f} cycles)", 3, arrival,
                                   max(fd - margin, 0), False, part_no, e.id, fd))
            od = int(max(hours_left(e), 0) // settings.flying_hours_per_day)
            if od <= H:
                st.overhaul_day = od if st.overhaul_day is None else min(st.overhaul_day, od)
                causes.append(("overhaul", f"Engine {e.position} overhaul ({max(hours_left(e), 0):.0f} h left)", 3, 0, od, True, None, e.id, od))
        if ac.status == "AOG":
            for i in [i for i in indents if i.tail_no == ac.tail_no]:
                part = parts[i.part_no]
                causes.append(("defect_fix", f"Fit {part.name} ({part.part_no})", 1, indent_arrival_day(i, part, expedite), None, False, part.part_no, None, 0))
        has_fix_task = any(t.kind in RESOLVING_KINDS for t in my_tasks)
        if causes and not has_fix_task and ac.status != "MAINT" and (only_tails is None or ac.tail_no in only_tails):
            deadlines = [c[4] for c in causes if c[4] is not None]
            main = max(causes, key=lambda c: c[2])
            st.need = Need(
                tail=ac.tail_no, kind=main[0], title="; ".join(c[1] for c in causes), duration=max(c[2] for c in causes),
                earliest=max(c[3] for c in causes), deadline=min(deadlines) if deadlines else None,
                hard=any(c[5] for c in causes), part_no=next((c[6] for c in causes if c[6]), None),
                engine_ids=[c[7] for c in causes if c[7]], risk_day=min(c[8] for c in causes))
        states.append(st)
    return states


def _part_arrival(part, open_indents, expedite) -> int:
    if part is None or part.stock > 0:
        return 0
    if open_indents:
        return min(indent_arrival_day(i, part, expedite) for i in open_indents)
    return min(part.lead_time_days, 2) if part.part_no in expedite else part.lead_time_days


def capacity(db, squadron_code) -> tuple[list[int], list[int]]:
    """Hangar slots and technician hours still free on each day of the horizon at the squadron's base."""
    H, t0 = settings.horizon_days, today()
    sq = db.get(Squadron, squadron_code)
    slots = {s.day: s.capacity for s in db.query(HangarSlot).filter(HangarSlot.base_code == sq.base_code)}
    free = [slots.get(t0 + timedelta(days=d), 2) for d in range(H)]
    hours = [settings.tech_hours_per_day] * H
    base_tails = [a.tail_no for a in db.query(Aircraft).join(Squadron, Aircraft.squadron_code == Squadron.code)
                  .filter(Squadron.base_code == sq.base_code)]
    for t in db.query(Task).filter(Task.tail_no.in_(base_tails), Task.status.in_(["Scheduled", "Done"]), Task.hangar.like("Hangar%")):
        for d in range(max((t.slot_start - t0).days, 0), min((t.slot_end - t0).days + 1, H)):
            free[d] -= 1
            hours[d] -= settings.task_tech_hours
    return free, hours


# ---------- Fleet Health Score ----------

def overdue_critical(db, tails):
    """Critical alerts not reviewed by an Engineering Officer within 12 hours."""
    cutoff = utcnow() - timedelta(hours=settings.review_hours)
    return (db.query(Alert).filter(Alert.tail_no.in_(tails), Alert.severity == "Critical", Alert.reviewed_at.is_(None),
                                   Alert.created_at < cutoff).all()) if tails else []


def awaiting_spares(db, tails) -> dict:
    """{tail: [part_no]} for AOG aircraft whose part has not been received."""
    if not tails:
        return {}
    rows = (db.query(Indent).join(Aircraft, Aircraft.tail_no == Indent.tail_no)
            .filter(Indent.tail_no.in_(tails), Indent.status != "Received", Aircraft.status == "AOG").all())
    out = {}
    for i in rows:
        out.setdefault(i.tail_no, []).append(i.part_no)
    return out


def fleet_score(db, squadron_code) -> dict:
    """Fleet Health Score (0-100) from 5 explainable rules. Every lost point has a reason."""
    sq = db.get(Squadron, squadron_code)
    acs = squadron_aircraft(db, squadron_code)
    tails = [a.tail_no for a in acs]
    total = len(acs) or 1
    states = build_states(db, squadron_code)
    fc = fleet_forecast(states, None, settings.horizon_days, settings.safety_margin_days)
    day = settings.forecast_day
    fc_mc = fc["mission_capable"][day]
    avail = fc_mc / total
    shortfall = max(sq.availability_target - avail, 0) * 100
    p1 = min(round(shortfall / 1.4), 20)

    engines = db.query(Engine).filter(Engine.tail_no.in_(tails)).all() if tails else []
    preds = latest_predictions(db, [e.id for e in engines])
    crit = sorted({e.tail_no for e in engines if e.id in preds and preds[e.id].rul_cycles < settings.critical_rul})
    p2 = min(4 * len(crit), 16)
    spares = awaiting_spares(db, tails)
    p3 = min(3 * len(spares), 12)
    overdue = overdue_critical(db, tails)
    p4 = 5 if overdue else 0
    breach = sorted({e.tail_no for e in engines if past_overhaul(e)})
    p5 = 10 * len(breach)

    rules = [
        {"key": "forecast", "label": f"Forecast availability (next {day} days)", "points": -p1, "link": "/schedule",
         "detail": f"{fc_mc}/{total} = {avail * 100:.0f}% against the {sq.availability_target * 100:.0f}% target"},
        {"key": "rul", "label": "Critical RUL (under 25 cycles)", "points": -p2, "link": "/aircraft",
         "detail": f"{len(crit)} aircraft: {', '.join(crit)}" if crit else "No engine under 25 cycles"},
        {"key": "aog", "label": "AOG awaiting spares", "points": -p3, "link": "/spares",
         "detail": f"{len(spares)} aircraft: {', '.join(sorted(spares))}" if spares else "No aircraft waiting for a part"},
        {"key": "review", "label": "Critical alert not reviewed within 12 hours", "points": -p4, "link": "/alerts",
         "detail": f"{', '.join(a.id for a in overdue)} waiting for an Engineering Officer" if overdue else "All critical alerts reviewed in time"},
        {"key": "overhaul", "label": "Aircraft past overhaul limit (safety flag)", "points": -p5, "link": "/overhaul",
         "detail": f"{len(breach)} aircraft: {', '.join(breach)}" if breach else "No aircraft past its limit"},
    ]
    mc = sum(1 for a in acs if a.status == "MC")
    down = [a for a in acs if a.status in ("AOG", "MAINT")]
    critical_alerts = (db.query(Alert).filter(Alert.tail_no.in_(tails), Alert.severity == "Critical").all()) if tails else []
    active_crit = [a for a in critical_alerts if a.decision != "FalseAlarm"]
    kpis = {
        "total": len(acs), "mission_capable": mc, "forecast_day": day, "forecast_mission_capable": fc_mc,
        "aog": len(down), "aog_awaiting_spares": len(spares), "in_maintenance": sum(1 for a in acs if a.status == "MAINT"),
        "critical_alerts": len(active_crit), "critical_unreviewed": sum(1 for a in active_crit if not a.reviewed_at),
        "combat_ready": sum(1 for a in acs if a.status == "MC" and a.combat_ready),
        "transport_ready": sum(1 for a in acs if a.status == "MC" and a.transport_ready),
        "availability_target": sq.availability_target,
    }
    return {"squadron": squadron_code, "squadron_name": sq.name, "score": max(100 - p1 - p2 - p3 - p4 - p5, 0),
            "rules": rules, "kpis": kpis}


# ---------- serialisers ----------

def aircraft_dict(ac: Aircraft) -> dict:
    return {"tail_no": ac.tail_no, "type": ac.type, "squadron_code": ac.squadron_code, "flying_hours": ac.flying_hours,
            "status": ac.status, "status_label": STATUS_LABEL[ac.status], "health_score": ac.health_score,
            "combat_ready": ac.combat_ready and ac.status == "MC", "transport_ready": ac.transport_ready and ac.status == "MC",
            "readiness": "Combat-ready" if ac.combat_ready and ac.status == "MC" else
                         "Transport-ready" if ac.transport_ready and ac.status == "MC" else "Not ready",
            "archived": ac.archived}


def alert_dict(a: Alert) -> dict:
    hours_left_ = None
    if a.severity == "Critical" and not a.reviewed_at:
        hours_left_ = round(settings.review_hours - (utcnow() - a.created_at).total_seconds() / 3600, 1)
    return {"id": a.id, "tail_no": a.tail_no, "engine_id": a.engine_id, "kind": a.kind, "severity": a.severity,
            "message": a.message, "created_at": iso(a.created_at), "reviewed_by": a.reviewed_by, "reviewed_at": iso(a.reviewed_at),
            "decision": a.decision, "note": a.note, "escalated": a.escalated, "hours_left": hours_left_,
            "overdue": hours_left_ is not None and hours_left_ < 0}


def task_dict(t: Task) -> dict:
    return {"id": t.id, "tail_no": t.tail_no, "title": t.title, "kind": t.kind, "slot_start": t.slot_start.isoformat(),
            "slot_end": t.slot_end.isoformat(), "hangar": t.hangar, "assigned_to": t.assigned_to, "status": t.status,
            "hours_spent": t.hours_spent, "completed_by": t.completed_by, "signed_off_by": t.signed_off_by, "part_no": t.part_no}


def defect_dict(d: Defect) -> dict:
    return {"id": d.id, "tail_no": d.tail_no, "text": d.text, "suggested_category": d.suggested_category,
            "confirmed_category": d.confirmed_category, "system": d.system, "logged_by": d.logged_by,
            "logged_at": iso(d.logged_at), "status": d.status}


def indent_dict(i: Indent, part: Part | None = None) -> dict:
    d = {"id": i.id, "part_no": i.part_no, "tail_no": i.tail_no, "qty": i.qty, "reason": i.reason,
         "needed_by": i.needed_by.isoformat(), "needed_in_days": (i.needed_by - today()).days, "raised_by": i.raised_by,
         "status": i.status, "created_at": iso(i.created_at), "fitted": i.fitted}
    if part:
        arrival = indent_arrival_day(i, part)
        d.update(part_name=part.name, lead_time_days=part.lead_time_days, stock=part.stock, arrives_in_days=arrival,
                 late=i.status != "Received" and arrival > d["needed_in_days"])
    return d


def twin(db, ac: Aircraft) -> dict:
    """The digital twin: one live state object per aircraft."""
    engines = db.query(Engine).filter(Engine.tail_no == ac.tail_no).order_by(Engine.position).all()
    preds = latest_predictions(db, [e.id for e in engines])
    eng_out = []
    for e in engines:
        p = preds.get(e.id)
        history = (db.query(Prediction).filter(Prediction.engine_id == e.id).order_by(Prediction.id.desc()).limit(40).all())[::-1]
        rows = (db.query(SensorReading).filter(SensorReading.engine_id == e.id).order_by(SensorReading.cycle.desc()).limit(60).all())[::-1]
        latest = rows[-1] if rows else None
        eng_out.append({
            "id": e.id, "position": e.position, "serial": e.serial, "hours_since_overhaul": e.hours_since_overhaul,
            "overhaul_limit_hours": e.overhaul_limit_hours, "hours_left": hours_left(e), "past_overhaul_limit": past_overhaul(e),
            "rul_cycles": p.rul_cycles if p else None, "rul_days": int(p.rul_cycles // settings.sorties_per_day) if p else None,
            "critical": bool(p and p.rul_cycles < settings.critical_rul),
            "anomaly_score": p.anomaly_score if p else None, "anomaly_flag": bool(p and p.anomaly_score >= 0.5),
            "shap_top3": p.shap_top3 if p else [], "model_version": p.model_version if p else None,
            "model_trained_on": p.trained_on if p else None, "model_dataset": p.dataset if p else None,
            "model_test_rmse": p.test_rmse if p else None,
            "rul_history": [{"time": iso(h.time), "rul": h.rul_cycles, "anomaly": h.anomaly_score} for h in history],
            "latest_sensors": {f"s{i}": getattr(latest, f"s{i}") for i in range(1, 22)} | {"cycle": latest.cycle, "time": iso(latest.time)} if latest else None,
            "sensor_history": [{"cycle": r.cycle, "s3": r.s3, "s4": r.s4, "s8": r.s8, "s11": r.s11} for r in rows],
        })
    defects = db.query(Defect).filter(Defect.tail_no == ac.tail_no).order_by(Defect.logged_at.desc()).limit(20).all()
    tasks = db.query(Task).filter(Task.tail_no == ac.tail_no).order_by(Task.slot_start).all()
    alerts = db.query(Alert).filter(Alert.tail_no == ac.tail_no).order_by(Alert.created_at.desc()).all()
    parts = {p.part_no: p for p in db.query(Part).all()}
    indents = db.query(Indent).filter(Indent.tail_no == ac.tail_no).all()
    pending = [t for t in tasks if t.status != "SignedOff"]
    return {
        **aircraft_dict(ac), "updated_at": iso(utcnow()),
        "health": health_breakdown(db, ac, preds), "engines": eng_out,
        "open_defects": [defect_dict(d) for d in defects if d.status == "Open"],
        "defects": [defect_dict(d) for d in defects], "tasks": [task_dict(t) for t in tasks],
        "alerts": [alert_dict(a) for a in alerts],
        "next_maintenance_due": pending[0].slot_start.isoformat() if pending else None,
        "next_maintenance_title": pending[0].title if pending else None,
        "spares": [indent_dict(i, parts.get(i.part_no)) for i in indents],
        "advisory": "Advisory. Final decision rests with the authorised engineer.",
    }


def base_name(db, code):
    b = db.get(BaseStation, code)
    return b.name if b else code
