"""Maintenance schedule (OR-Tools) and the what-if simulator."""
import time

from fastapi import APIRouter, Depends

from .. import planning, state
from ..models import HangarSlot, Squadron, Task
from ..schemas import PlanIn, WhatIfIn
from ..security import Ctx, fail, need
from .common import ADVISORY, finish, squadron_for

router = APIRouter(tags=["schedule"])
VIEW = ("CO", "ENGO", "FSO", "AUDITOR", "HQ", "BRD")


@router.get("/schedule")
def calendar(squadron: str | None = None, ctx: Ctx = Depends(need(*VIEW))):
    """Tasks already in the calendar, for the Gantt view."""
    sq = squadron_for(ctx, squadron)
    t0 = state.today()
    tails = [a.tail_no for a in state.squadron_aircraft(ctx.db, sq)]
    rows = ctx.db.query(Task).filter(Task.tail_no.in_(tails), Task.status != "SignedOff").order_by(Task.slot_start).all()
    base = ctx.db.get(Squadron, sq).base_code
    cap = {s.day.isoformat(): s.capacity for s in ctx.db.query(HangarSlot).filter(HangarSlot.base_code == base)}
    return {"squadron": sq, "today": t0.isoformat(), "horizon_days": planning.H,
            "tasks": [{**state.task_dict(t), "start_day": max((t.slot_start - t0).days, 0),
                       "duration": (t.slot_end - t0).days + 1 - max((t.slot_start - t0).days, 0)} for t in rows],
            "hangar_capacity": cap, "plan_approved": planning.latest_approved(ctx.db, sq) is not None, "advisory": ADVISORY}


@router.post("/schedule/optimise")
def optimise(body: PlanIn | None = None, ctx: Ctx = Depends(need("ENGO", "CO"))):
    sq = squadron_for(ctx, body.squadron if body else None)
    t = time.perf_counter()
    result = planning.recommend(ctx.db, sq)
    result["solve_seconds"] = round(time.perf_counter() - t, 3)
    return result


@router.post("/schedule/check")
def check(body: PlanIn, ctx: Ctx = Depends(need("ENGO", "CO"))):
    """Called after a task is moved by drag-and-drop: re-checks constraints and updates the forecast."""
    sq = squadron_for(ctx, body.squadron)
    return planning.evaluate(ctx.db, sq, [t.model_dump() for t in body.tasks or []])


@router.post("/schedule/approve")
def approve(body: PlanIn | None = None, ctx: Ctx = Depends(need("CO"))):
    sq = squadron_for(ctx, body.squadron if body else None)
    if body and body.tasks is not None:
        result = planning.evaluate(ctx.db, sq, [t.model_dump() for t in body.tasks])
    else:
        result = planning.recommend(ctx.db, sq)
    if not result["tasks"]:
        fail(409, "There is nothing to approve: no maintenance tasks are waiting to be planned.")
    blocking = [p["message"] for p in result["problems"] if p["blocking"]]
    if blocking:
        fail(409, "The plan cannot be approved: " + " ".join(blocking))
    plan = planning.approve(ctx.db, sq, result, ctx.user)
    tails = [t["tail"] for t in result["tasks"]]
    out = finish(ctx, "PLAN_APPROVED", f"Maintenance plan {plan.id} for {sq} approved: {len(tails)} tasks ({', '.join(tails)})", tails,
                 message=f"Plan approved. {len(tails)} tasks are now in the schedule. {result['summary']}.")
    return {**out, "plan_id": plan.id, "tasks": result["tasks"], "forecast": result["forecast"], "summary": result["summary"]}


@router.post("/whatif")
def whatif(body: WhatIfIn, ctx: Ctx = Depends(need("CO", "ENGO", "HQ", "FSO"))):
    """'If we service these aircraft this week, what is the 30-day availability?' Nothing is saved."""
    sq = squadron_for(ctx, body.squadron)
    t = time.perf_counter()
    base = planning.recommend(ctx.db, sq, only_tails=set())  # today's settings, nothing extra serviced
    scen = planning.recommend(ctx.db, sq, body.sorties_per_day, tuple(body.expedite),
                              only_tails=set(body.service), horizon=body.horizon_days)
    h = body.horizon_days
    before, after = base["forecast"]["without"][h], scen["forecast"]["with_plan"][h]
    return {
        "squadron": sq, "horizon_days": h, "days": scen["forecast"]["days"][:h + 1], "total": scen["forecast"]["total"],
        "without": base["forecast"]["without"][:h + 1], "with": scen["forecast"]["with_plan"][:h + 1],
        "combat_without": base["forecast"]["combat_without"][:h + 1], "combat_with": scen["forecast"]["combat_with_plan"][:h + 1],
        "transport_without": base["forecast"]["transport_without"][:h + 1], "transport_with": scen["forecast"]["transport_with_plan"][:h + 1],
        "tasks": scen["tasks"], "unscheduled": scen["unscheduled"], "before": before, "after": after,
        "message": f"{h}-day availability: {before} -> {after} aircraft", "seconds": round(time.perf_counter() - t, 3),
        "advisory": ADVISORY,
    }
