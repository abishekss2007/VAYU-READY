"""8. ML  9. NLP  10. Optimiser and what-if."""
import json

import pytest

from app import state
from app.config import settings
from ml import common as mlc
from ml import infer
from optimiser import plan as cp
from optimiser.forecast import forecast_pair

needs_models = pytest.mark.skipif(not infer.available(), reason="models not trained: run 'make train' first")


@needs_models
def test_rul_model_returns_number_between_0_and_125_with_3_shap_reasons():
    train, _, _, _ = mlc.load_fd001(quiet=True)
    for unit, cut in ((1, 40), (2, 15), (3, 1)):
        g = train[train["unit"] == unit]
        res = infer.predict(g.iloc[:len(g) - cut])
        assert 0 <= res["rul_cycles"] <= 125
        assert 0 <= res["anomaly_score"] <= 1
        assert len(res["shap_top3"]) == 3
        for reason in res["shap_top3"]:
            assert reason["name"] and reason["direction"] in ("rising", "falling", "steady")
        assert res["model_version"] and res["trained_on"] and res["dataset"] and res["test_rmse"]


@needs_models
def test_rul_rmse_on_fd001_test_set_is_under_20():
    m = json.loads((settings.results_dir / "metrics.json").read_text())
    rmse = m["rul"]["best_rmse"]
    print(f"\nRUL test RMSE ({m['rul']['best']}, {m['dataset']}): {rmse} cycles")
    assert rmse < 20


@needs_models
def test_predict_endpoint_stores_governance_fields(client, auth):
    r = client.post("/predict/ENG-101-1", headers=auth("engo"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert 0 <= body["rul_cycles"] <= 125 and len(body["shap_top3"]) == 3
    eng = client.get("/aircraft/TAIL-SQ7-101/twin", headers=auth("engo")).json()["engines"][0]
    assert eng["model_version"] == body["model_version"] and eng["model_test_rmse"] and eng["model_dataset"] and eng["model_trained_on"]


def test_hyd_leak_is_classified_as_hydraulics(client, auth):
    assert infer.classify_defect("hyd leak near left MLG actuator")["category"] == "Hydraulics"
    r = client.post("/defects", json={"tail_no": "TAIL-SQ7-101", "text": "hyd leak near left MLG actuator"}, headers=auth("tech")).json()
    assert r["suggested_category"] == "Hydraulics" and r["suggestion"].startswith("Hydraulics")


def test_plan_never_uses_more_than_2_hangar_slots_per_day(client, db):
    states = state.build_states(db, "SQ7")
    free, hours = state.capacity(db, "SQ7")
    tasks = cp.optimise(states, free, hours)
    assert tasks
    committed = [2 - f for f in free]  # hangar tasks already in the calendar
    for d in range(30):
        planned = sum(1 for t in tasks if t["start_day"] <= d < t["start_day"] + t["duration"])
        assert planned + committed[d] <= 2, f"day {d}"
    assert cp.check(states, tasks, free, hours) == [] or all(not p["blocking"] for p in cp.check(states, tasks, free, hours))
    # hard limits respected: overhaul tasks start on or before the limit day, part tasks not before arrival
    for t in tasks:
        assert t["start_day"] >= t["earliest"]
        if t["hard"]:
            assert t["start_day"] <= t["deadline"]


def test_forecast_with_plan_is_never_lower_than_without(client, db):
    for sq in ("SQ7", "SQ12"):
        for spd in (0.6, 1.2, 3.0):
            states = state.build_states(db, sq, sorties_per_day=spd)
            free, hours = state.capacity(db, sq)
            tasks = cp.optimise(states, free, hours)
            fc = forecast_pair(states, {t["tail"]: (t["start_day"], t["duration"]) for t in tasks})
            # the plan never loses mission-capable aircraft-days, and never ends the horizon worse
            assert sum(fc["with_plan"]) >= sum(fc["without"]), (sq, spd)
            assert fc["with_plan"][-1] >= fc["without"][-1], (sq, spd)


def test_moving_a_task_past_a_hard_limit_is_blocked(client, auth):
    engo = auth("engo")
    plan = client.post("/schedule/optimise", headers=engo).json()
    moved = [{"tail": t["tail"], "start_day": 20 if t["tail"] == "TAIL-SQ7-108" else t["start_day"]} for t in plan["tasks"]]
    r = client.post("/schedule/check", json={"tasks": moved}, headers=engo).json()
    assert not r["can_approve"]
    assert any("overhaul limit" in p["message"] for p in r["problems"])
    assert client.post("/schedule/approve", json={"tasks": moved}, headers=auth("co")).status_code == 409


def test_whatif_runs_in_under_2_seconds(client, auth):
    r = client.post("/whatif", json={"service": ["TAIL-SQ7-108", "TAIL-SQ7-113", "TAIL-SQ7-103"], "horizon_days": 30}, headers=auth("co"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["seconds"] < 2
    assert body["after"] > body["before"] and body["message"].startswith("30-day availability:")
    assert len(body["combat_with"]) == 31 and len(body["transport_with"]) == 31
    # expediting the HPC module lets TAIL-SQ7-114 be fixed before its safe date
    slow = client.post("/whatif", json={"service": ["TAIL-SQ7-114"]}, headers=auth("co")).json()
    fast = client.post("/whatif", json={"service": ["TAIL-SQ7-114"], "expedite": ["HPC-MOD-07"]}, headers=auth("co")).json()
    assert sum(fast["with"]) > sum(slow["with"])
