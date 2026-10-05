"""ISO 13374 block: Prognostic Assessment. Day-by-day readiness forecast.

Pure Python, no database access. The API builds `AircraftState` objects and calls these functions.

How one aircraft is judged on day d (day 0 = today):
  * It is down while any hangar task covers that day.
  * If it is not mission-capable today (AOG / in maintenance), it stays down until a task on it finishes.
  * Predicted engine failure: without a task it goes down on the failure day and stays down.
    With a task it flies until the task starts; if the task can only start after the safety margin
    (for example the part arrives late) it is stood down from the margin day until the task ends.
  * Overhaul limit: a hard limit. Without a task it is locked from the limit day onwards.
"""
from dataclasses import dataclass, field


@dataclass
class Need:
    """One piece of maintenance an aircraft needs (several causes are merged into one hangar visit)."""
    tail: str
    kind: str                     # engine_change | overhaul | defect_fix
    title: str
    duration: int
    earliest: int = 0             # first day it can start (part arrival)
    deadline: int | None = None   # last safe start day
    hard: bool = False            # True for overhaul limits: must never start after the deadline
    part_no: str | None = None
    engine_ids: list = field(default_factory=list)
    risk_day: int = 99            # day the aircraft would be grounded if nothing is done


@dataclass
class AircraftState:
    tail: str
    status: str = "MC"
    combat_ready: bool = True
    transport_ready: bool = True
    fail_day: int | None = None       # earliest predicted engine failure day
    overhaul_day: int | None = None   # day the earliest overhaul limit is reached
    committed: list = field(default_factory=list)  # [(start_day, duration)] tasks already in the calendar
    need: Need | None = None


def aircraft_series(ac: AircraftState, extra_task=None, horizon: int = 30, margin: int = 3) -> list[bool]:
    """True/False mission-capable for each day 0..horizon. extra_task = (start_day, duration) or None."""
    tasks = list(ac.committed) + ([extra_task] if extra_task else [])
    first_start = min((s for s, _ in tasks), default=None)
    fix_end = max((s + du for s, du in tasks), default=None)  # all booked work finished
    conditions = []  # (day it grounds the aircraft, day it must stand down if the task is late)
    if ac.fail_day is not None:
        conditions.append((ac.fail_day, max(ac.fail_day - margin, 0)))
    if ac.overhaul_day is not None:
        conditions.append((ac.overhaul_day, ac.overhaul_day))
    out = []
    for d in range(horizon + 1):
        up = not any(s <= d < s + du for s, du in tasks)
        if ac.status != "MC" and (fix_end is None or d < fix_end):
            up = False
        for ground_day, stand_down_day in conditions:
            if fix_end is None:
                up = up and d < ground_day
            elif first_start > stand_down_day and stand_down_day <= d < fix_end:
                up = False
        out.append(up)
    return out


def fleet_forecast(states: list[AircraftState], plan: dict | None = None, horizon: int = 30, margin: int = 3) -> dict:
    """plan = {tail: (start_day, duration)}. Returns counts per day."""
    plan = plan or {}
    mc = [0] * (horizon + 1)
    combat = [0] * (horizon + 1)
    transport = [0] * (horizon + 1)
    for ac in states:
        for d, up in enumerate(aircraft_series(ac, plan.get(ac.tail), horizon, margin)):
            if up:
                mc[d] += 1
                combat[d] += 1 if ac.combat_ready else 0
                transport[d] += 1 if ac.transport_ready else 0
    return {"mission_capable": mc, "combat_ready": combat, "transport_ready": transport}


def forecast_pair(states, plan, horizon: int = 30, margin: int = 3) -> dict:
    """Both series for the dashboard chart: without the plan and with it."""
    without = fleet_forecast(states, None, horizon, margin)
    with_plan = fleet_forecast(states, plan, horizon, margin)
    return {
        "total": len(states),
        "days": list(range(horizon + 1)),
        "without": without["mission_capable"],
        "with_plan": with_plan["mission_capable"],
        "combat_without": without["combat_ready"],
        "combat_with_plan": with_plan["combat_ready"],
        "transport_without": without["transport_ready"],
        "transport_with_plan": with_plan["transport_ready"],
    }
