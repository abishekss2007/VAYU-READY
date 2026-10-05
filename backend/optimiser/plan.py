"""ISO 13374 block: Advisory Generation. Maintenance scheduler (Google OR-Tools CP-SAT).

Decision: for each needed task, a start day (or "not scheduled").
Objective: maximise mission-capable aircraft-days over the horizon; tie-break: highest-risk aircraft first.
Constraints: part arrival, failure day minus safety margin, overhaul limits (hard), hangar slots, technician hours.

Advisory only: the plan changes nothing until a Commander approves it.
"""
from ortools.sat.python import cp_model

from .forecast import AircraftState, aircraft_series

AIRCRAFT_DAY_WEIGHT = 100_000  # keeps the tie-breaker from ever outweighing one aircraft-day


def _allowed_starts(need, horizon):
    """Start days that respect part arrival and deadlines. Returns (days, late)."""
    last = horizon - 1
    if need.deadline is not None and need.deadline >= need.earliest:
        return list(range(need.earliest, min(need.deadline, last) + 1)), False
    if need.deadline is not None and need.hard:
        return [], True  # an overhaul limit can never be planned past its limit
    # No deadline, or the part arrives after the safe date: start as soon as possible, flagged late.
    return list(range(min(need.earliest, last + 1), last + 1)), need.deadline is not None


def optimise(states: list[AircraftState], free_slots: list[int], tech_hours: list[int],
             task_tech_hours: int = 24, horizon: int = 30, margin: int = 3, time_limit: float = 1.5) -> list[dict]:
    """free_slots[d] / tech_hours[d] = hangar slots and technician hours still free on day d.

    Returns a list of planned tasks: {tail, kind, title, start_day, duration, late, ...}.
    """
    needs = [(ac, ac.need) for ac in states if ac.need]
    model = cp_model.CpModel()
    choice = {}   # (tail, start) -> BoolVar
    objective = []
    late_flag = {}
    for ac, need in needs:
        starts, late = _allowed_starts(need, horizon)
        late_flag[ac.tail] = late
        baseline = sum(aircraft_series(ac, None, horizon, margin))
        options = []
        for s in starts:
            v = model.NewBoolVar(f"{ac.tail}_{s}")
            choice[(ac.tail, s)] = v
            options.append(v)
            gain = sum(aircraft_series(ac, (s, need.duration), horizon, margin)) - baseline
            # Tie-breaker: the sooner an aircraft would be grounded, the more an early slot is worth.
            urgency = max(horizon - need.risk_day, 1)
            objective.append(v * (gain * AIRCRAFT_DAY_WEIGHT - s * urgency))
        model.Add(sum(options) <= 1)  # leaving a task out is allowed (it then counts as "no plan")
    for d in range(horizon):
        covering = [choice[(ac.tail, s)] for ac, need in needs
                    for s in range(max(0, d - need.duration + 1), d + 1) if (ac.tail, s) in choice]
        if covering:
            model.Add(sum(covering) <= max(free_slots[d], 0))
            model.Add(sum(covering) * task_tech_hours <= max(tech_hours[d], 0))
    model.Maximize(sum(objective))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.random_seed = 42
    solver.parameters.num_workers = 1  # deterministic
    status = solver.Solve(model)
    tasks = []
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for ac, need in needs:
            for s in range(horizon):
                if (ac.tail, s) in choice and solver.Value(choice[(ac.tail, s)]):
                    tasks.append(_task_dict(need, s, late_flag[ac.tail]))
    return sorted(tasks, key=lambda t: (t["start_day"], t["tail"]))


def _task_dict(need, start, late):
    return {
        "tail": need.tail, "kind": need.kind, "title": need.title, "start_day": start,
        "duration": need.duration, "earliest": need.earliest, "deadline": need.deadline, "hard": need.hard,
        "part_no": need.part_no, "engine_ids": need.engine_ids, "late": late,
    }


def unscheduled(states, tasks) -> list[dict]:
    planned = {t["tail"] for t in tasks}
    return [{"tail": ac.tail, "title": ac.need.title, "reason": "No free hangar slot or part before the limit"}
            for ac in states if ac.need and ac.tail not in planned]


def check(states: list[AircraftState], tasks: list[dict], free_slots: list[int], tech_hours: list[int],
          task_tech_hours: int = 24, horizon: int = 30) -> list[dict]:
    """Re-check a plan after a task is moved by hand. Returns plain-English problems.

    blocking=True means the plan cannot be approved (hard limit); False is a warning.
    """
    problems = []
    by_tail = {ac.tail: ac for ac in states}
    used = [0] * horizon
    for t in tasks:
        need = by_tail[t["tail"]].need if t["tail"] in by_tail else None
        s, du = t["start_day"], t["duration"]
        if s < 0 or s >= horizon:
            problems.append({"tail": t["tail"], "blocking": True,
                             "message": f"{t['tail']}: start day must be within the {horizon}-day plan."})
            continue
        for d in range(s, min(s + du, horizon)):
            used[d] += 1
        if not need:
            continue
        if s < need.earliest:
            problems.append({"tail": t["tail"], "blocking": True,
                             "message": f"{t['tail']}: cannot start on day {s}; part {need.part_no} arrives on day {need.earliest}."})
        if need.deadline is not None and s > need.deadline:
            if need.hard:
                problems.append({"tail": t["tail"], "blocking": True,
                                 "message": f"{t['tail']}: overhaul limit is reached on day {need.deadline}; the task cannot start later."})
            elif need.deadline >= need.earliest:
                problems.append({"tail": t["tail"], "blocking": False,
                                 "message": f"{t['tail']}: starts after the safe date (day {need.deadline}); the aircraft must stand down from day {need.deadline}."})
    for d in range(horizon):
        if used[d] > max(free_slots[d], 0):
            problems.append({"tail": None, "blocking": True,
                             "message": f"Day {d}: {used[d]} hangar tasks planned but only {max(free_slots[d], 0)} slot(s) free."})
        elif used[d] * task_tech_hours > tech_hours[d]:
            problems.append({"tail": None, "blocking": True,
                             "message": f"Day {d}: not enough technician hours ({used[d] * task_tech_hours} needed, {tech_hours[d]} free)."})
    return problems
