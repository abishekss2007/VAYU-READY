"""Dashboard, portfolio, aircraft, digital twin, predictions and overhaul tracker."""
from datetime import timedelta

import pandas as pd
from fastapi import APIRouter, Depends

from .. import jobs, planning, state
from ..config import settings
from ..db import iso, utcnow
from ..models import Aircraft, Alert, BaseStation, Engine, Indent, Part, Prediction, SensorReading, Squadron
from ..schemas import AircraftIn, AircraftPatch, BaseIn, StatusIn
from ..security import OPS_ROLES, Ctx, fail, need
from .common import ADVISORY, SCOPED, finish, get_aircraft, squadron_for

router = APIRouter(tags=["fleet"])
SEVERITY_ORDER = {"Critical": 0, "Warning": 1, "Info": 2}
ALERT_ACTION = {"RUL": "Review alert", "ANOMALY": "Review alert", "OVERHAUL": "Open overhaul tracker",
                "SPARES": "Open spares", "RECURRING": "Open defects"}
ALERT_LINK = {"OVERHAUL": "/overhaul", "SPARES": "/spares", "RECURRING": "/defects"}


def alert_out(a: Alert) -> dict:
    d = state.alert_dict(a)
    d["action_label"] = ALERT_ACTION[a.kind]
    d["action_link"] = ALERT_LINK.get(a.kind, f"/aircraft/{a.tail_no}")
    return d


def needs_attention(db, tails):
    rows = db.query(Alert).filter(Alert.tail_no.in_(tails), Alert.reviewed_at.is_(None)).all() if tails else []
    rows.sort(key=lambda a: (SEVERITY_ORDER[a.severity], a.created_at))
    return [alert_out(a) for a in rows]


@router.get("/dashboard")
def dashboard(squadron: str | None = None, ctx: Ctx = Depends(need("CO", "ENGO", "FSO", "AUDITOR", "HQ"))):
    sq = squadron_for(ctx, squadron)
    score = state.fleet_score(ctx.db, sq)
    acs = state.squadron_aircraft(ctx.db, sq)
    return {**score, "alerts": needs_attention(ctx.db, [a.tail_no for a in acs]),
            "forecast": planning.dashboard_forecast(ctx.db, sq),
            "aircraft": [state.aircraft_dict(a) for a in acs],
            "squadrons": [{"code": s.code, "name": s.name} for s in ctx.db.query(Squadron).order_by(Squadron.code)]
            if ctx.user.role not in SCOPED else [], "advisory": ADVISORY, "generated_at": iso(utcnow())}


@router.get("/portfolio")
def portfolio(ctx: Ctx = Depends(need("HQ"))):
    out, causes, spares = [], {}, {}
    parts = {p.part_no: p for p in ctx.db.query(Part)}
    for sq in ctx.db.query(Squadron).order_by(Squadron.code):
        s = state.fleet_score(ctx.db, sq.code)
        k = s["kpis"]
        out.append({"code": sq.code, "name": sq.name, "base": state.base_name(ctx.db, sq.base_code), "score": s["score"],
                    "availability": round(k["mission_capable"] / max(k["total"], 1), 3), "kpis": k, "rules": s["rules"]})
        tails = [a.tail_no for a in state.squadron_aircraft(ctx.db, sq.code)]
        for tail, part_nos in state.awaiting_spares(ctx.db, tails).items():
            for pn in part_nos:
                causes[parts[pn].system] = causes.get(parts[pn].system, 0) + 1
                spares[pn] = spares.get(pn, 0) + 1
        if k["in_maintenance"]:
            causes["Scheduled maintenance"] = causes.get("Scheduled maintenance", 0) + k["in_maintenance"]
    return {"squadrons": out,
            "top_aog_causes": sorted(({"cause": c, "aircraft": n} for c, n in causes.items()), key=lambda x: -x["aircraft"]),
            "top_grounding_spares": sorted(({"part_no": pn, "name": parts[pn].name, "aircraft_grounded": n,
                                             "lead_time_days": parts[pn].lead_time_days, "stock": parts[pn].stock}
                                            for pn, n in spares.items()), key=lambda x: -x["aircraft_grounded"])}


@router.get("/aircraft")
def list_aircraft(squadron: str | None = None, status: str | None = None, include_archived: bool = False,
                  ctx: Ctx = Depends(need())):
    q = ctx.db.query(Aircraft)
    if ctx.user.role in SCOPED:
        q = q.filter(Aircraft.squadron_code == squadron_for(ctx, squadron))
    elif squadron:
        q = q.filter(Aircraft.squadron_code == squadron)
    if status:
        q = q.filter(Aircraft.status == status)
    if not include_archived:
        q = q.filter(Aircraft.archived.is_(False))
    acs = q.order_by(Aircraft.health_score, Aircraft.tail_no).all()  # lowest health first
    engines = ctx.db.query(Engine).filter(Engine.tail_no.in_([a.tail_no for a in acs])).all() if acs else []
    preds = state.latest_predictions(ctx.db, [e.id for e in engines]) if ctx.user.role != "ADMIN" else {}
    out = []
    for a in acs:
        d = state.aircraft_dict(a)
        ruls = [preds[e.id].rul_cycles for e in engines if e.tail_no == a.tail_no and e.id in preds]
        d["min_rul_cycles"] = min(ruls) if ruls else None
        d["archived_reason"] = a.archived_reason
        out.append(d)
    return out


@router.get("/aircraft/{tail_no}/twin")
def twin(tail_no: str, ctx: Ctx = Depends(need(*OPS_ROLES))):
    return state.twin(ctx.db, get_aircraft(ctx, tail_no))


@router.patch("/aircraft/{tail_no}/status")
def set_status(tail_no: str, body: StatusIn, ctx: Ctx = Depends(need("ENGO"))):
    """Only an Engineering Officer changes an aircraft's status, always with a reason. No model output can."""
    ac = get_aircraft(ctx, tail_no)
    old = ac.status
    if body.status == old:
        fail(409, f"{tail_no} is already {state.STATUS_LABEL[old]}.")
    if body.status == "MC":
        reason = jobs.lock_check(ctx.db, ac)
        if reason:
            fail(409, reason)
        # parts received for this aircraft are now fitted
        for ind in ctx.db.query(Indent).filter(Indent.tail_no == tail_no, Indent.status == "Received", Indent.fitted.is_(False)):
            ind.fitted = True
            part = ctx.db.get(Part, ind.part_no)
            part.stock = max(part.stock - ind.qty, 0)
    ac.status = body.status
    ctx.db.flush()
    return finish(ctx, "STATUS_CHANGED", f"{tail_no}: {state.STATUS_LABEL[old]} -> {state.STATUS_LABEL[body.status]}. Reason: {body.reason}",
                  [tail_no], message=f"{tail_no} is now {state.STATUS_LABEL[body.status]}.")


@router.post("/predict/{engine_id}")
def predict(engine_id: str, ctx: Ctx = Depends(need("ENGO", "CO"))):
    """Runs the RUL and anomaly models on the latest 30-cycle window. Advisory only."""
    from ml import infer
    e = ctx.db.get(Engine, engine_id)
    if not e:
        fail(404, f"Engine {engine_id} not found.")
    get_aircraft(ctx, e.tail_no)
    rows = (ctx.db.query(SensorReading).filter(SensorReading.engine_id == engine_id)
            .order_by(SensorReading.cycle.desc()).limit(30).all())[::-1]
    if len(rows) < 2:
        fail(409, f"Not enough sensor data for {engine_id}: at least 2 cycles are needed.")
    if not infer.available():
        fail(503, "The RUL model has not been trained yet. Run 'make train' first.")
    window = pd.DataFrame([{f"s{i}": getattr(r, f"s{i}") for i in range(1, 22)} for r in rows])
    res = infer.predict(window)
    ctx.db.add(Prediction(engine_id=engine_id, time=utcnow(), rul_cycles=res["rul_cycles"], anomaly_score=res["anomaly_score"],
                          model_version=res["model_version"], shap_top3=res["shap_top3"], trained_on=res["trained_on"],
                          dataset=res["dataset"], test_rmse=res["test_rmse"]))
    ctx.db.flush()
    out = finish(ctx, "PREDICTION_RUN", f"{engine_id}: RUL {res['rul_cycles']} cycles, anomaly {res['anomaly_score']} ({res['model_version']})",
                 [e.tail_no], message=f"{engine_id}: predicted RUL {res['rul_cycles']} cycles.")
    out["new_alerts"] = jobs.rul_check(ctx.db)  # may raise an alert and an indent; never changes aircraft status
    return {**out, **res, "advisory": ADVISORY}


@router.get("/overhaul")
def overhaul(days: int = 90, ctx: Ctx = Depends(need("BRD", "ENGO", "FSO"))):
    q = ctx.db.query(Engine, Aircraft).join(Aircraft, Aircraft.tail_no == Engine.tail_no).filter(Aircraft.archived.is_(False))
    if ctx.user.role in SCOPED:
        q = q.filter(Aircraft.squadron_code == ctx.squadron)
    rows = []
    for e, ac in q:
        left = state.hours_left(e)
        due_days = int(max(left, 0) // settings.flying_hours_per_day)
        if due_days <= days:
            rows.append({"engine_id": e.id, "tail_no": e.tail_no, "squadron_code": ac.squadron_code, "position": e.position,
                         "serial": e.serial, "hours_since_overhaul": e.hours_since_overhaul, "overhaul_limit_hours": e.overhaul_limit_hours,
                         "hours_left": left, "due_in_days": due_days, "due_date": (state.today() + timedelta(days=due_days)).isoformat(),
                         "past_limit": state.past_overhaul(e),
                         "level": "Critical" if left <= 10 else "Warning" if left <= 50 else "OK"})
    rows.sort(key=lambda r: r["hours_left"])
    return {"days": days, "engines": rows, "due_within_30_days": sum(1 for r in rows if r["due_in_days"] <= 30),
            "past_limit": sum(1 for r in rows if r["past_limit"]),
            "note": "Hour limits are a safety floor. The system never extends a manufacturer limit.",
            "flying_hours_per_day": settings.flying_hours_per_day}


@router.post("/engines/{engine_id}/overhaul")
def record_overhaul(engine_id: str, ctx: Ctx = Depends(need("ENGO", "BRD"))):
    e = ctx.db.get(Engine, engine_id)
    if not e:
        fail(404, f"Engine {engine_id} not found.")
    get_aircraft(ctx, e.tail_no)
    e.hours_since_overhaul = 0
    ctx.db.flush()
    return finish(ctx, "OVERHAUL_RECORDED", f"Overhaul recorded for {engine_id} ({e.tail_no}); hours since overhaul reset to 0",
                  [e.tail_no], message=f"Overhaul recorded for {engine_id}.")


# ---------- Admin: bases and aircraft records only ----------

@router.get("/bases")
def bases(ctx: Ctx = Depends(need())):
    return {"bases": [{"code": b.code, "name": b.name} for b in ctx.db.query(BaseStation).order_by(BaseStation.code)],
            "squadrons": [{"code": s.code, "name": s.name, "base_code": s.base_code, "availability_target": s.availability_target}
                          for s in ctx.db.query(Squadron).order_by(Squadron.code)]}


@router.post("/bases")
def add_base(body: BaseIn, ctx: Ctx = Depends(need("ADMIN"))):
    if ctx.db.get(BaseStation, body.code):
        fail(409, f"Base {body.code} already exists.")
    ctx.db.add(BaseStation(code=body.code, name=body.name))
    ctx.db.flush()
    return finish(ctx, "BASE_ADDED", f"Base {body.code} ({body.name}) added")


@router.post("/aircraft")
def add_aircraft(body: AircraftIn, ctx: Ctx = Depends(need("ADMIN"))):
    if ctx.db.get(Aircraft, body.tail_no):
        fail(409, f"Aircraft {body.tail_no} already exists.")
    if not ctx.db.get(Squadron, body.squadron_code):
        fail(404, f"Squadron {body.squadron_code} not found.")
    # A new record starts as "In maintenance": only an Engineering Officer can declare it mission-capable.
    ctx.db.add(Aircraft(tail_no=body.tail_no, type=body.type, squadron_code=body.squadron_code, flying_hours=body.flying_hours, status="MAINT"))
    ctx.db.flush()
    return finish(ctx, "AIRCRAFT_ADDED", f"Aircraft record {body.tail_no} added to {body.squadron_code}")


@router.patch("/aircraft/{tail_no}")
def edit_aircraft(tail_no: str, body: AircraftPatch, ctx: Ctx = Depends(need("ADMIN"))):
    ac = get_aircraft(ctx, tail_no)
    if body.archived and not (body.archived_reason or "").strip():
        fail(422, "A reason is needed to archive an aircraft record. Records are never deleted, only archived.")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(ac, k, v)
    ctx.db.flush()
    return finish(ctx, "AIRCRAFT_EDITED", f"Aircraft record {tail_no} updated: {body.model_dump(exclude_none=True)}",
                  message=f"Aircraft record {tail_no} updated.")
