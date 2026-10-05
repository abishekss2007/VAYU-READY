"""5. Alerts  6. Spares  7. Overhaul  + airworthiness rules: AI cannot change status, two-person sign-off."""
from datetime import timedelta

from app import jobs
from app.db import utcnow
from app.models import Aircraft, Alert, Engine, Indent, Part, Prediction, Task

HPC_REASON = [{"sensor": "s3", "name": "HPC outlet temperature", "direction": "rising", "impact_cycles": -30, "text": "HPC outlet temperature rising"}]


def low_rul(db, engine_id, rul=20.0):
    db.add(Prediction(engine_id=engine_id, time=utcnow(), rul_cycles=rul, anomaly_score=0.7, model_version="test", shap_top3=HPC_REASON))
    db.commit()


def test_rul_under_25_creates_critical_alert(client, db):
    assert jobs.rul_check(db) == []  # nothing new on the seeded data
    low_rul(db, "ENG-106-1")
    created = jobs.rul_check(db)
    alert = db.query(Alert).filter(Alert.engine_id == "ENG-106-1", Alert.kind == "RUL").one()
    assert alert.id in created and alert.severity == "Critical" and alert.reviewed_at is None
    assert db.get(Aircraft, "TAIL-SQ7-106").status == "MC"  # the alert alone never changes aircraft status


def test_unreviewed_critical_alert_escalates_after_12_hours(client, db, auth):
    assert db.get(Alert, "ALT-031").escalated is False
    assert jobs.escalate(db) == ["ALT-031"]  # created 14 hours ago
    db.expire_all()
    assert db.get(Alert, "ALT-031").escalated is True
    alerts = client.get("/dashboard", headers=auth("co")).json()["alerts"]
    top = alerts[0]
    assert top["id"] == "ALT-031" and top["escalated"] and top["overdue"] and top["hours_left"] < 0
    # a fresh critical alert is not escalated yet
    low_rul(db, "ENG-106-1")
    new = jobs.rul_check(db)
    assert jobs.escalate(db) == [] and new


def test_predicted_failure_needing_out_of_stock_part_auto_raises_indent(client, db):
    assert db.get(Part, "HPC-MOD-07").stock == 0
    low_rul(db, "ENG-106-1")
    jobs.rul_check(db)
    ind = db.query(Indent).filter(Indent.tail_no == "TAIL-SQ7-106", Indent.part_no == "HPC-MOD-07").one()
    assert ind.raised_by == "system" and ind.status == "Raised"
    jobs.rul_check(db)  # running again does not raise a duplicate
    assert db.query(Indent).filter(Indent.tail_no == "TAIL-SQ7-106").count() == 1


def test_receiving_part_releases_aog_aircraft_only_after_engo_signoff(client, auth, db):
    r = client.post("/indents/IND-010/receive", headers=auth("logo"))
    assert r.status_code == 200
    assert db.get(Aircraft, "TAIL-SQ7-105").status == "AOG"  # still on ground
    # the Logistics Officer cannot release it
    assert client.patch("/aircraft/TAIL-SQ7-105/status", json={"status": "MC", "reason": "part in"}, headers=auth("logo")).status_code == 403
    r = client.patch("/aircraft/TAIL-SQ7-105/status", json={"status": "MC", "reason": "actuator fitted, checks passed"}, headers=auth("engo"))
    assert r.status_code == 200
    db.expire_all()
    assert db.get(Aircraft, "TAIL-SQ7-105").status == "MC"
    # an indent that was never approved cannot be received
    r = client.post("/indents/IND-012/receive", headers=auth("logo"))
    assert r.status_code == 409 and r.json()["detail"] == "Cannot receive indent IND-012: it has not been approved yet."


def test_engine_past_overhaul_limit_cannot_be_marked_mission_capable(client, auth, db):
    e = db.get(Engine, "ENG-111-1")
    e.hours_since_overhaul = e.overhaul_limit_hours + 1
    for t in db.query(Task).filter(Task.tail_no == "TAIL-SQ7-111"):
        t.status = "SignedOff"
    db.commit()
    engo = auth("engo")
    r = client.patch("/aircraft/TAIL-SQ7-111/status", json={"status": "MC", "reason": "servicing complete"}, headers=engo)
    assert r.status_code == 409 and "past its overhaul limit" in r.json()["detail"]
    d = client.get("/dashboard", headers=auth("co")).json()
    assert {x["key"]: x["points"] for x in d["rules"]}["overhaul"] == -10
    # once the overhaul is recorded, the lock is lifted
    assert client.post("/engines/ENG-111-1/overhaul", headers=engo).status_code == 200
    assert client.patch("/aircraft/TAIL-SQ7-111/status", json={"status": "MC", "reason": "overhaul recorded"}, headers=engo).status_code == 200


def test_ai_cannot_change_aircraft_status(client, auth, db):
    before = {a.tail_no: a.status for a in db.query(Aircraft)}
    r = client.post("/predict/ENG-114-2", headers=auth("engo"))
    assert r.status_code in (200, 503)  # 503 only if models are not trained
    low_rul(db, "ENG-106-1", 3.0)
    jobs.run_all(db)
    client.post("/schedule/optimise", headers=auth("engo"))
    client.post("/whatif", json={"service": ["TAIL-SQ7-108"]}, headers=auth("engo"))
    db.expire_all()
    assert {a.tail_no: a.status for a in db.query(Aircraft)} == before
    # a status change needs an ENGO and a reason
    assert client.patch("/aircraft/TAIL-SQ7-106/status", json={"status": "AOG"}, headers=auth("engo")).status_code == 422
    assert client.patch("/aircraft/TAIL-SQ7-106/status", json={"status": "AOG", "reason": "x"}, headers=auth("co")).status_code == 403


def test_two_person_signoff(client, auth, db):
    tech, engo = auth("tech"), auth("engo")
    task = db.query(Task).filter(Task.title.like("Replace worn brake%")).one()
    # ENGO cannot sign off work that is not done, and cannot close the task for the technician
    assert client.post(f"/tasks/{task.id}/signoff", headers=engo).status_code == 409
    assert client.post(f"/tasks/{task.id}/complete", json={"hours_spent": 2}, headers=engo).status_code == 403
    assert client.post(f"/tasks/{task.id}/complete", json={"hours_spent": 2.5}, headers=tech).status_code == 200
    assert client.post(f"/tasks/{task.id}/signoff", headers=tech).status_code == 403  # technician cannot sign off
    # same person doing and signing is refused even if they hold the ENGO role
    db.expire_all()
    db.get(Task, task.id).completed_by = "engo@vayu.demo"
    db.commit()
    r = client.post(f"/tasks/{task.id}/signoff", headers=engo)
    assert r.status_code == 409 and "Two-person rule" in r.json()["detail"]
    db.get(Task, task.id).completed_by = "tech@vayu.demo"
    db.commit()
    assert client.post(f"/tasks/{task.id}/signoff", headers=engo).status_code == 200
    db.expire_all()
    t = db.get(Task, task.id)
    assert (t.completed_by, t.signed_off_by, t.status) == ("tech@vayu.demo", "engo@vayu.demo", "SignedOff")
    assert db.get(Aircraft, "TAIL-SQ7-111").status == "MAINT"  # the 300-hour servicing is still open


def test_recurring_defect_alert(client, auth, db):
    tech = auth("tech")
    for _ in range(3):
        r = client.post("/defects", json={"tail_no": "TAIL-SQ7-104", "text": "hyd leak near left MLG actuator"}, headers=tech)
        assert r.status_code == 200
    assert r.json()["recurring_alert"]
    assert db.query(Alert).filter(Alert.tail_no == "TAIL-SQ7-104", Alert.kind == "RECURRING").count() == 1
    # the seeded scenario: TAIL-SQ7-107 already shows as RECURRING
    assert db.query(Alert).filter(Alert.tail_no == "TAIL-SQ7-107", Alert.kind == "RECURRING").count() == 1


def test_overhaul_tracker_three_engines_due_within_30_days(client, auth):
    r = client.get("/overhaul?days=90", headers=auth("brd")).json()
    assert r["due_within_30_days"] == 3 and r["past_limit"] == 0
    assert {e["engine_id"] for e in r["engines"] if e["due_in_days"] <= 30} == {"ENG-108-1", "ENG-108-2", "ENG-113-1"}
    assert client.get("/overhaul", headers=auth("logo")).status_code == 403


def test_old_alert_time_is_reported(client, auth):
    a = [x for x in client.get("/alerts", headers=auth("engo")).json()["alerts"] if x["id"] == "ALT-031"][0]
    assert -3 < a["hours_left"] < -1 and a["action_label"] == "Review alert"
    assert utcnow() - timedelta(hours=15) < utcnow()
