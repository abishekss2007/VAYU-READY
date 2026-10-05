"""Helpers shared by the routers."""
from .. import audit, state
from ..live import hub
from ..models import Aircraft, Squadron
from ..security import Ctx, fail

SCOPED = {"CO", "ENGO", "TECH"}  # these roles see their own squadron only
ADVISORY = "Advisory. Final decision rests with the authorised engineer."


def squadron_for(ctx: Ctx, requested: str | None = None) -> str:
    """Which squadron this request is about."""
    if ctx.user.role in SCOPED:
        if requested and requested != ctx.squadron:
            fail(403, f"You can only see your own squadron ({ctx.squadron}).")
        return ctx.squadron
    code = requested or "SQ7"
    if not ctx.db.get(Squadron, code):
        fail(404, f"Squadron {code} not found.")
    return code


def get_aircraft(ctx: Ctx, tail_no: str) -> Aircraft:
    ac = ctx.db.get(Aircraft, tail_no)
    if not ac or (ctx.user.role in SCOPED and ac.squadron_code != ctx.squadron):
        # Same message whether it does not exist or belongs to another squadron: no information leak.
        fail(404, f"Aircraft {tail_no} not found in your squadron." if ctx.user.role in SCOPED else f"Aircraft {tail_no} not found.")
    return ac


def scope_tails(ctx: Ctx, query, column):
    """App-level squadron filter (PostgreSQL row-level security enforces the same rule underneath)."""
    if ctx.user.role in SCOPED:
        tails = [a.tail_no for a in ctx.db.query(Aircraft.tail_no).filter(Aircraft.squadron_code == ctx.squadron)]
        return query.filter(column.in_(tails))
    return query


def finish(ctx: Ctx, action: str, detail: str, tails=(), message: str | None = None, **extra) -> dict:
    """Steps 4-6 of every write: audit entry, update the twin and score, return a clear message."""
    audit.write(ctx.db, ctx.user.email, ctx.user.role, action, detail)
    state.refresh_health(ctx.db, tails)
    ctx.db.commit()
    hub.refresh(tails, action)
    out = {"message": message or detail, **extra}
    squadrons = {ctx.db.get(Aircraft, t).squadron_code for t in tails if ctx.db.get(Aircraft, t)}
    if ctx.user.role != "ADMIN" and len(squadrons) == 1:
        out["fleet_health_score"] = state.fleet_score(ctx.db, squadrons.pop())["score"]
    return out
