"""ISO 13374 block: Advisory Generation. Glue between the database and the optimiser package."""
from datetime import timedelta

from optimiser import plan as cp
from optimiser.forecast import forecast_pair

from . import state
from .config import settings
from .models import Plan, Task, User

H = settings.horizon_days
MARGIN = settings.safety_margin_days


def _assign_hangars(db, squadron, tasks):
    """Give each planned task a hangar name that is free for its whole slot."""
    t0 = state.today()
    busy = {"Hangar 1": set(), "Hangar 2": set()}
    tails = [a.tail_no for a in state.squadron_aircraft(db, squadron)]
    for t in db.query(Task).filter(Task.tail_no.in_(tails), Task.status.in_(["Scheduled", "Done"]), Task.hangar.like("Hangar%")):
        busy.setdefault(t.hangar, set()).update(range((t.slot_start - t0).days, (t.slot_end - t0).days + 1))
    for t in tasks:
        days = set(range(t["start_day"], t["start_day"] + t["duration"]))
        name = next((h for h in sorted(busy) if not busy[h] & days), "Hangar 1")
        busy[name] |= days
        t["hangar"] = name
        t["start_date"] = (t0 + timedelta(days=t["start_day"])).isoformat()
        t["end_date"] = (t0 + timedelta(days=t["start_day"] + t["duration"] - 1)).isoformat()
    return tasks


def _summary(fc, h):
    return (f"{h}-day availability: {fc['without'][h]} -> {fc['with_plan'][h]} aircraft "
            f"(of {fc['total']}); mission-capable aircraft-days {sum(fc['without'][:h + 1])} -> {sum(fc['with_plan'][:h + 1])}")


def recommend(db, squadron, sorties_per_day=None, expedite=(), only_tails=None, horizon=H) -> dict:
    """Run the optimiser and return the plan with both forecast lines. Nothing is saved."""
    states = state.build_states(db, squadron, sorties_per_day, expedite, only_tails)
    free, hours = state.capacity(db, squadron)
    tasks = cp.optimise(states, free, hours, settings.task_tech_hours, H, MARGIN)
    return _package(db, squadron, states, tasks, free, hours, horizon)


def evaluate(db, squadron, moved: list[dict]) -> dict:
    """Re-check a plan after tasks were moved by hand (drag-and-drop)."""
    states = state.build_states(db, squadron)
    free, hours = state.capacity(db, squadron)
    needs = {s.tail: s.need for s in states if s.need}
    tasks = [cp._task_dict(needs[t["tail"]], t["start_day"], False) for t in moved if t["tail"] in needs]
    for t in tasks:
        t["late"] = t["deadline"] is not None and t["start_day"] > t["deadline"]
    return _package(db, squadron, states, tasks, free, hours, H)


def _package(db, squadron, states, tasks, free, hours, horizon):
    plan = {t["tail"]: (t["start_day"], t["duration"]) for t in tasks}
    fc = forecast_pair(states, plan, H, MARGIN)
    problems = cp.check(states, tasks, free, hours, settings.task_tech_hours, H)
    return {
        "squadron": squadron, "tasks": _assign_hangars(db, squadron, tasks), "unscheduled": cp.unscheduled(states, tasks),
        "forecast": fc, "problems": problems, "can_approve": not any(p["blocking"] for p in problems),
        "free_slots": free, "summary": _summary(fc, horizon), "horizon_days": H,
        "assumptions": {"sorties_per_day": settings.sorties_per_day, "flying_hours_per_day": settings.flying_hours_per_day,
                        "safety_margin_days": MARGIN, "engine_change_days": 3, "inspection_days": 1, "defect_fix_days": 1,
                        "technician_hours_per_day": settings.tech_hours_per_day},
        "advisory": "Advisory. Final decision rests with the authorised engineer.",
    }


def latest_approved(db, squadron) -> Plan | None:
    return db.query(Plan).filter(Plan.squadron_code == squadron, Plan.status == "Approved").order_by(Plan.id.desc()).first()


def dashboard_forecast(db, squadron) -> dict:
    """Forecast chart for the dashboard: without and with the recommended (or approved) plan."""
    rec = recommend(db, squadron)
    fc = rec["forecast"]
    approved = latest_approved(db, squadron)
    if approved and not rec["tasks"]:
        # The plan is now in the calendar, so today's forecast is the "with plan" line.
        # Keep the "without" line frozen from the moment of approval so the benefit stays visible.
        offset = (state.today() - approved.created_at.date()).days
        frozen = approved.payload["forecast"]["without"][offset:]
        fc["without"] = (frozen + [frozen[-1]] * (H + 1))[:H + 1] if frozen else fc["without"]
    return {**fc, "plan_approved": bool(approved), "plan_tasks": rec["tasks"], "summary": _summary(fc, H),
            "approved_by": approved.approved_by if approved else None}


def approve(db, squadron, result: dict, approver: User) -> Plan:
    """Put the plan into the calendar as tasks. Only a Commander calls this."""
    t0 = state.today()
    tech = db.query(User).filter(User.role == "TECH", User.squadron_code == squadron, User.active.is_(True)).first()
    for t in result["tasks"]:
        db.add(Task(tail_no=t["tail"], title=t["title"], kind=t["kind"], slot_start=t0 + timedelta(days=t["start_day"]),
                    slot_end=t0 + timedelta(days=t["start_day"] + t["duration"] - 1), hangar=t["hangar"],
                    assigned_to=tech.email if tech else None, engine_ids=t["engine_ids"], part_no=t["part_no"]))
    p = Plan(squadron_code=squadron, created_at=state.utcnow(), created_by=approver.email, status="Approved",
             approved_by=approver.email, payload={"tasks": result["tasks"], "forecast": result["forecast"]})
    db.add(p)
    db.flush()
    return p
