"""4. Score: demo data gives 71; after ALT-031 review 76; after HYD-ACT-22 received and TAIL-SQ7-105 released 83.
Then the optimiser: 30-day forecast 11 -> 16. The audit chain stays intact throughout."""


def points(dash):
    return {r["key"]: r["points"] for r in dash["rules"]}


def test_demo_walkthrough_71_76_83_and_forecast_11_to_16(client, auth):
    co, engo, logo = auth("co"), auth("engo"), auth("logo")

    d = client.get("/dashboard", headers=co).json()
    assert d["score"] == 71
    assert points(d) == {"forecast": -10, "rul": -8, "aog": -6, "review": -5, "overhaul": 0}
    k = d["kpis"]
    assert (k["mission_capable"], k["total"], k["forecast_mission_capable"]) == (14, 18, 11)
    assert (k["aog"], k["aog_awaiting_spares"], k["critical_alerts"]) == (4, 2, 2)
    assert (k["combat_ready"], k["transport_ready"]) == (12, 14)
    assert d["forecast"]["without"][0] == 14 and d["forecast"]["without"][9] == 11

    # Engineering Officer reviews ALT-031 -> 76
    r = client.post("/alerts/ALT-031/review", json={"decision": "Schedule", "note": "HPC trend confirmed"}, headers=engo)
    assert r.status_code == 200 and r.json()["fleet_health_score"] == 76
    assert client.get("/dashboard", headers=co).json()["score"] == 76

    # Release is refused until the part is received
    r = client.patch("/aircraft/TAIL-SQ7-105/status", json={"status": "MC", "reason": "try early"}, headers=engo)
    assert r.status_code == 409
    assert r.json()["detail"] == "Cannot release aircraft: required part HYD-ACT-22 has not been received."

    # Logistics receives HYD-ACT-22: the aircraft is NOT released by that alone
    r = client.post("/indents/IND-010/receive", headers=logo)
    assert r.status_code == 200 and "after Engineering Officer sign-off" in r.json()["message"]
    assert client.get("/aircraft/TAIL-SQ7-105/twin", headers=engo).json()["status"] == "AOG"

    # ENGO releases TAIL-SQ7-105 -> 83
    r = client.patch("/aircraft/TAIL-SQ7-105/status", json={"status": "MC", "reason": "MLG actuator fitted and tested"}, headers=engo)
    assert r.status_code == 200 and r.json()["fleet_health_score"] == 83
    d = client.get("/dashboard", headers=co).json()
    assert d["score"] == 83
    assert points(d) == {"forecast": -6, "rul": -8, "aog": -3, "review": 0, "overhaul": 0}
    assert d["kpis"]["forecast_mission_capable"] == 12

    # Optimiser: 30-day availability 11 -> 16
    plan = client.post("/schedule/optimise", headers=engo).json()
    assert plan["forecast"]["without"][30] == 11 and plan["forecast"]["with_plan"][30] == 16
    assert plan["can_approve"]
    assert client.post("/schedule/approve", headers=engo).status_code == 403  # only the Commander approves
    r = client.post("/schedule/approve", headers=co)
    assert r.status_code == 200, r.text
    d = client.get("/dashboard", headers=co).json()
    assert d["forecast"]["with_plan"][30] == 16 and d["forecast"]["without"][30] == 11
    assert d["forecast"]["plan_approved"]

    # the audit chain is intact after the whole demo
    v = client.get("/audit/verify", headers=auth("auditor")).json()
    assert v["intact"] is True and v["entries"] > 5
