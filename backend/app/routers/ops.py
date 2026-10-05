"""Alerts, defects, tasks, spares and indents."""
from fastapi import APIRouter, Depends

from .. import jobs, state
from ..db import utcnow
from ..models import Aircraft, Alert, Defect, Engine, Indent, Part, Prediction, Task
from ..schemas import CloseIn, CompleteIn, ConfirmIn, DefectIn, ReviewIn
from ..security import OPS_ROLES, Ctx, fail, need
from .common import ADVISORY, finish, get_aircraft, scope_tails
from .fleet import SEVERITY_ORDER, alert_out

router = APIRouter(tags=["operations"])


# ---------- alerts ----------

@router.get("/alerts")
def alerts(ctx: Ctx = Depends(need(*OPS_ROLES))):
    rows = scope_tails(ctx, ctx.db.query(Alert), Alert.tail_no).all()
    rows.sort(key=lambda a: (a.reviewed_at is not None, SEVERITY_ORDER[a.severity], a.created_at))
    return {"alerts": [alert_out(a) for a in rows], "advisory": ADVISORY}


@router.post("/alerts/{alert_id}/review")
def review(alert_id: str, body: ReviewIn, ctx: Ctx = Depends(need("ENGO"))):
    a = ctx.db.get(Alert, alert_id)
    if not a:
        fail(404, f"Alert {alert_id} not found.")
    get_aircraft(ctx, a.tail_no)
    if a.reviewed_at:
        fail(409, f"Alert {alert_id} was already reviewed by {a.reviewed_by}.")
    a.reviewed_by, a.reviewed_at, a.decision, a.note = ctx.user.email, utcnow(), body.decision, body.note
    ctx.db.flush()
    label = {"Inspect": "Inspect", "Schedule": "Schedule engine change", "FalseAlarm": "False alarm"}[body.decision]
    # The decision is recorded; it does not change the aircraft status by itself.
    return finish(ctx, "ALERT_REVIEWED", f"Alert {alert_id} on {a.tail_no} reviewed: {label}. Note: {body.note or '-'}", [a.tail_no],
                  message=f"Alert {alert_id} reviewed: {label}. The 12-hour review clock has stopped.")


# ---------- defects ----------

@router.get("/defects")
def defects(ctx: Ctx = Depends(need(*OPS_ROLES))):
    rows = scope_tails(ctx, ctx.db.query(Defect), Defect.tail_no).order_by(Defect.logged_at.desc()).all()
    return [state.defect_dict(d) for d in rows]


@router.post("/defects")
def log_defect(body: DefectIn, ctx: Ctx = Depends(need("TECH", "ENGO"))):
    from ml import infer
    ac = get_aircraft(ctx, body.tail_no)
    s = infer.classify_defect(body.text)
    d = Defect(tail_no=ac.tail_no, text=body.text.strip(), suggested_category=s["category"], system=s["category"],
               logged_by=ctx.user.email, logged_at=utcnow(), status="Open")
    ctx.db.add(d)
    ctx.db.flush()
    recurring = jobs.recurring_check(ctx.db, ac.tail_no)
    out = finish(ctx, "DEFECT_LOGGED", f"Defect logged on {ac.tail_no}: {d.text}", [ac.tail_no],
                 message=f"Defect logged on {ac.tail_no}. Suggested category: {s['category']}. Please confirm.")
    suggestion = s["category"] + (f" / {s['related']}" if s["related"] else "")
    return {**out, "defect": state.defect_dict(d), "suggested_category": s["category"], "related_system": s["related"],
            "suggestion": suggestion, "confidence": s["confidence"], "recurring_alert": recurring,
            "advisory": "Suggestion only. The technician confirms the category."}


@router.post("/defects/{defect_id}/confirm")
def confirm_defect(defect_id: int, body: ConfirmIn, ctx: Ctx = Depends(need("TECH", "ENGO"))):
    d = ctx.db.get(Defect, defect_id)
    if not d:
        fail(404, f"Defect {defect_id} not found.")
    get_aircraft(ctx, d.tail_no)
    d.confirmed_category = d.system = body.category
    ctx.db.flush()
    jobs.recurring_check(ctx.db, d.tail_no)
    return finish(ctx, "DEFECT_CONFIRMED", f"Defect {d.id} on {d.tail_no} confirmed as {body.category}", [d.tail_no],
                  message=f"Category confirmed: {body.category}.")


@router.post("/defects/{defect_id}/close")
def close_defect(defect_id: int, body: CloseIn, ctx: Ctx = Depends(need("ENGO"))):
    d = ctx.db.get(Defect, defect_id)
    if not d:
        fail(404, f"Defect {defect_id} not found.")
    get_aircraft(ctx, d.tail_no)
    if d.status != "Open":
        fail(409, f"Defect {defect_id} is already {d.status.lower()}.")
    d.status = "Closed"
    ctx.db.flush()
    return finish(ctx, "DEFECT_CLOSED", f"Defect {d.id} on {d.tail_no} closed. Reason: {body.reason}", [d.tail_no],
                  message=f"Defect {d.id} closed.")


# ---------- tasks ----------

@router.get("/tasks")
def tasks(mine: bool = False, ctx: Ctx = Depends(need(*OPS_ROLES))):
    q = scope_tails(ctx, ctx.db.query(Task), Task.tail_no)
    if mine:
        q = q.filter(Task.assigned_to == ctx.user.email)
    return [state.task_dict(t) for t in q.order_by(Task.slot_start, Task.id)]


def _task(ctx, task_id) -> Task:
    t = ctx.db.get(Task, task_id)
    if not t:
        fail(404, f"Task {task_id} not found.")
    get_aircraft(ctx, t.tail_no)
    return t


@router.post("/tasks/{task_id}/complete")
def complete_task(task_id: int, body: CompleteIn, ctx: Ctx = Depends(need("TECH"))):
    t = _task(ctx, task_id)
    if t.status != "Scheduled":
        fail(409, f"Task {task_id} is already marked done.")
    if t.assigned_to and t.assigned_to != ctx.user.email:
        fail(403, f"Task {task_id} is assigned to {t.assigned_to}. Only the technician who did the work can close it.")
    t.status, t.hours_spent, t.completed_by, t.assigned_to = "Done", body.hours_spent, ctx.user.email, ctx.user.email
    ctx.db.flush()
    return finish(ctx, "TASK_COMPLETED", f"Task {t.id} on {t.tail_no} ({t.title}) marked done, {body.hours_spent} h", [t.tail_no],
                  message="Task marked done. Waiting for Engineering Officer sign-off.")


@router.post("/tasks/{task_id}/signoff")
def signoff_task(task_id: int, ctx: Ctx = Depends(need("ENGO"))):
    t = _task(ctx, task_id)
    if t.status == "SignedOff":
        fail(409, f"Task {task_id} is already signed off.")
    if t.status != "Done":
        fail(409, f"Task {task_id} cannot be signed off yet: the technician has not marked it done.")
    if t.completed_by == ctx.user.email:
        fail(409, "Two-person rule: the person who did the work cannot sign it off.")
    t.status, t.signed_off_by = "SignedOff", ctx.user.email
    if t.kind in ("overhaul", "engine_change"):  # the work is now on record: the engine starts a new life
        for eid in t.engine_ids or []:
            e = ctx.db.get(Engine, eid)
            e.hours_since_overhaul = 0
            ctx.db.add(Prediction(engine_id=eid, time=utcnow(), rul_cycles=125.0, anomaly_score=0.02,
                                  model_version="reset after engine change / overhaul", shap_top3=[]))
    if t.part_no:
        part = ctx.db.get(Part, t.part_no)
        for ind in ctx.db.query(Indent).filter(Indent.tail_no == t.tail_no, Indent.part_no == t.part_no, Indent.fitted.is_(False)):
            ind.fitted = True
        if part:
            part.stock = max(part.stock - 1, 0)
    ctx.db.flush()
    ac = ctx.db.get(Aircraft, t.tail_no)
    released = ""
    open_tasks = ctx.db.query(Task).filter(Task.tail_no == t.tail_no, Task.status != "SignedOff").count()
    if ac.status in ("MAINT", "AOG") and open_tasks == 0 and jobs.lock_check(ctx.db, ac) is None:
        ac.status = "MC"  # released by the Engineering Officer's sign-off, not by the system
        released = f" {ac.tail_no} is now Mission-capable."
    ctx.db.flush()
    return finish(ctx, "TASK_SIGNED_OFF", f"Task {t.id} on {t.tail_no} ({t.title}) signed off.{released}", [t.tail_no],
                  message=f"Task signed off.{released}")


# ---------- spares ----------

@router.get("/parts")
def parts(ctx: Ctx = Depends(need(*OPS_ROLES))):
    rows = ctx.db.query(Part).order_by(Part.stock - Part.reorder_point, Part.part_no).all()
    on_order = {}
    for i in ctx.db.query(Indent).filter(Indent.status != "Received"):
        on_order[i.part_no] = on_order.get(i.part_no, 0) + i.qty
    # simple demand forecast: parts needed in the next 30 days by AOG aircraft and predicted failures
    demand = {}
    for i in ctx.db.query(Indent).filter(Indent.fitted.is_(False), Indent.tail_no.isnot(None)):
        demand[i.part_no] = demand.get(i.part_no, 0) + i.qty
    return [{"part_no": p.part_no, "name": p.name, "system": p.system, "stock": p.stock, "reorder_point": p.reorder_point,
             "lead_time_days": p.lead_time_days, "below_reorder": p.stock < p.reorder_point, "on_order": on_order.get(p.part_no, 0),
             "demand_30_days": demand.get(p.part_no, 0), "shortfall": max(demand.get(p.part_no, 0) - p.stock, 0)} for p in rows]


@router.get("/indents")
def indents(ctx: Ctx = Depends(need(*OPS_ROLES))):
    parts_ = {p.part_no: p for p in ctx.db.query(Part)}
    q = ctx.db.query(Indent)
    if ctx.user.role in ("CO", "ENGO", "TECH"):
        tails = [a.tail_no for a in ctx.db.query(Aircraft.tail_no).filter(Aircraft.squadron_code == ctx.squadron)]
        q = q.filter(Indent.tail_no.in_(tails))
    rows = sorted(q.all(), key=lambda i: (i.status == "Received", i.needed_by))  # sorted by "needed by"
    return [state.indent_dict(i, parts_.get(i.part_no)) for i in rows]


def _indent(ctx, indent_id) -> Indent:
    i = ctx.db.get(Indent, indent_id)
    if not i:
        fail(404, f"Indent {indent_id} not found.")
    return i


@router.post("/indents/{indent_id}/approve")
def approve_indent(indent_id: str, ctx: Ctx = Depends(need("LOGO"))):
    i = _indent(ctx, indent_id)
    if i.status != "Raised":
        fail(409, f"Indent {indent_id} is already {i.status.lower()}.")
    i.status = "Approved"
    ctx.db.flush()
    return finish(ctx, "INDENT_APPROVED", f"Indent {i.id} for {i.part_no} approved", [i.tail_no] if i.tail_no else [],
                  message=f"Indent {i.id} approved. Part {i.part_no} is on order.")


@router.post("/indents/{indent_id}/receive")
def receive_indent(indent_id: str, ctx: Ctx = Depends(need("LOGO"))):
    i = _indent(ctx, indent_id)
    if i.status == "Received":
        fail(409, f"Indent {indent_id} was already received.")
    if i.status != "Approved":
        fail(409, f"Cannot receive indent {indent_id}: it has not been approved yet.")
    i.status = "Received"
    part = ctx.db.get(Part, i.part_no)
    part.stock += i.qty
    ctx.db.flush()
    note = ""
    if i.tail_no:
        ac = ctx.db.get(Aircraft, i.tail_no)
        if ac and ac.status == "AOG":
            note = f" {i.tail_no} can be released after Engineering Officer sign-off."
    return finish(ctx, "INDENT_RECEIVED", f"Indent {i.id}: {i.qty} x {i.part_no} received.{note}", [i.tail_no] if i.tail_no else [],
                  message=f"{i.part_no} received.{note}")
