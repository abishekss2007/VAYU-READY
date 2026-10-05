"""11. Audit chain  + SQL test (UPDATE/DELETE on audit_log must fail)  + compliance timers, log retention, import."""
from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app import jobs
from app.db import owner_engine, utcnow
from app.models import AuditLog, SystemLog


def test_seed_has_5_chained_entries_and_verify_reports_intact(client, auth, db):
    rows = db.query(AuditLog).order_by(AuditLog.id).all()
    assert len(rows) == 5
    assert rows[0].prev_hash == "0" * 64 and all(rows[i].prev_hash == rows[i - 1].hash for i in range(1, 5))
    v = client.get("/audit/verify", headers=auth("auditor")).json()
    assert v == {"intact": True, "first_broken_entry": None, "entries": v["entries"], "message": "All entries intact"}


def test_update_or_delete_on_audit_log_fails(client):
    for sql in ("UPDATE audit_log SET detail = 'changed' WHERE id = 3", "DELETE FROM audit_log WHERE id = 3"):
        with pytest.raises(DBAPIError) as err:
            with owner_engine.begin() as conn:
                conn.execute(text(sql))
        assert "append-only" in str(err.value)


def test_verify_points_to_the_exact_tampered_entry(client, auth):
    """Someone with full database rights disables the trigger and edits entry 3. The hash chain still catches it."""
    pg = owner_engine.dialect.name == "postgresql"
    with owner_engine.begin() as conn:
        if pg:
            conn.execute(text("ALTER TABLE audit_log DISABLE TRIGGER audit_log_no_update_delete"))
        else:
            conn.execute(text("DROP TRIGGER audit_log_no_update"))
        conn.execute(text("UPDATE audit_log SET detail = 'Critical alert ALT-031 created for TAIL-SQ7-114 Engine 2 (RUL 80 cycles)' WHERE id = 3"))
        if pg:
            conn.execute(text("ALTER TABLE audit_log ENABLE TRIGGER audit_log_no_update_delete"))
    v = client.get("/audit/verify", headers=auth("auditor")).json()
    assert v["intact"] is False and v["first_broken_entry"] == 3


def test_every_write_adds_an_audit_entry(client, auth, db):
    before = db.query(AuditLog).count()
    client.post("/alerts/ALT-031/review", json={"decision": "FalseAlarm", "note": "sensor fault"}, headers=auth("engo"))
    db.expire_all()
    last = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    assert db.query(AuditLog).count() > before
    assert (last.actor, last.role, last.action) == ("engo@vayu.demo", "ENGO", "ALERT_REVIEWED")
    # the false alarm shows up in the per-model false-alarm rate
    cards = client.get("/models/cards", headers=auth("co")).json()["cards"]
    rul = [c for c in cards if c.get("alert_kind") == "RUL"]
    if rul:
        assert rul[0]["false_alarm"]["false_alarms"] == 1 and rul[0]["false_alarm"]["reviewed"] == 2


def test_breach_has_72_hour_timer_and_informs_affected_users(client, auth):
    admin = auth("admin")
    r = client.post("/breaches", json={"what_happened": "Tablet with a logged-in session left unattended", "impact": "One user's name and email visible",
                                      "steps_taken": "Session revoked, password reset", "affected_users": ["tech@vayu.demo"]}, headers=admin)
    assert r.status_code == 200, r.text
    b = r.json()["breach"]
    assert 71.9 < b["hours_left"] <= 72 and not b["overdue"] and b["users_informed_at"]
    assert client.get("/me/breach-notices", headers=auth("tech")).json()[0]["id"] == b["id"]
    assert client.get("/me/breach-notices", headers=auth("brd")).json() == []
    assert client.post(f"/breaches/{b['id']}/reported", headers=admin).status_code == 200
    assert client.get("/breaches", headers=admin).json()[0]["hours_left"] is None


def test_certin_incident_has_6_hour_timer(client, auth):
    admin = auth("admin")
    types = client.get("/incidents", headers=admin).json()
    assert "Ransomware attack" in types["types"] and types["report_to"] == "incident@cert-in.org.in"
    r = client.post("/incidents", json={"incident_type": "Unauthorised access to IT systems or data", "description": "Repeated failed logins from an unknown terminal"}, headers=admin)
    assert r.status_code == 200, r.text
    i = r.json()["incident"]
    assert 5.9 < i["hours_left"] <= 6 and not i["overdue"]
    assert client.post("/incidents", json={"incident_type": "Something else", "description": "not on the list"}, headers=admin).status_code == 422
    assert client.post("/incidents", json={"incident_type": "Data breach", "description": "tech tries"}, headers=auth("tech")).status_code == 403


def test_logs_are_kept_for_180_days(client, db):
    db.add_all([SystemLog(ts=utcnow() - timedelta(days=179), level="INFO", message="inside retention"),
                SystemLog(ts=utcnow() - timedelta(days=181), level="INFO", message="older than retention")])
    db.commit()
    assert jobs.purge_logs(db) == 1
    messages = [s.message for s in db.query(SystemLog)]
    assert "inside retention" in messages and "older than retention" not in messages


def test_privacy_notice_profile_and_grievance(client, auth):
    tech = auth("tech")
    assert client.get("/auth/me", headers=tech).json()["notice_acknowledged"] is False
    notice = client.get("/me/notice", headers=tech).json()
    assert "maintenance accountability" in notice["en"]["body"] and notice["hi"]["body"]
    client.post("/me/notice-ack", headers=tech)
    assert client.get("/auth/me", headers=tech).json()["notice_acknowledged"] is True
    held = client.get("/me/profile", headers=tech).json()["personal_data_held"]
    assert set(held) == {"name", "email", "role", "squadron"}  # data minimisation
    g = client.post("/grievances", json={"kind": "Correction", "text": "My name is spelt wrongly"}, headers=tech).json()["grievance"]
    assert client.get("/grievances", headers=auth("brd")).json() == []  # others cannot see it
    client.post(f"/grievances/{g['id']}/respond", json={"response": "Corrected"}, headers=auth("admin"))
    assert client.get("/grievances", headers=tech).json()[0]["status"] == "Resolved"


def test_compliance_page_roles_and_checklist(client, auth):
    assert client.get("/compliance", headers=auth("tech")).status_code == 403
    c = client.get("/compliance", headers=auth("auditor")).json()
    assert [g["group"] for g in c["groups"]] == ["Airworthiness and human control", "ISO 13374 / CBM+", "Data security", "DPDP Act 2023", "CERT-In Directions 2022"]
    assert all(i["status"] in ("Done", "Pending") and i["link"] for g in c["groups"] for i in g["items"])
    assert len(c["iso_13374"]) == 6
    assert client.get("/config/public").json()["classification"] == "DEMO DATA – UNCLASSIFIED"


def test_bulk_import_gives_a_clear_message_for_each_bad_row(client, auth):
    csv_text = ("tail_no,flying_hours,engine_position,hours_since_overhaul\n"
                "TAIL-SQ7-101,9000,1,700\n"
                "TAIL-SQ7-999,100,1,10\n"
                "TAIL-SQ7-102,abc,1,10\n"
                "TAIL-SQ7-103,9000,3,10\n"
                "TAIL-SQ12-201,9000,1,10\n")
    r = client.post("/import/records", files={"file": ("records.csv", csv_text, "text/csv")}, headers=auth("engo"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["saved"], body["rejected"]) == (1, 4)
    msgs = {e["row"]: e["message"] for e in body["errors"]}
    assert msgs[3] == "Row 3: aircraft 'TAIL-SQ7-999' not found."
    assert "must be numbers" in msgs[4] and "must be 1 or 2" in msgs[5]
    assert "not found" in msgs[6]  # another squadron's aircraft is invisible to the SQ7 ENGO
    r = client.post("/import/records", files={"file": ("records.txt", "x", "text/plain")}, headers=auth("engo"))
    assert r.status_code == 422


def test_reports_carry_the_classification_banner(client, auth):
    r = client.get("/reports/readiness.csv", headers=auth("co"))
    assert r.status_code == 200 and r.text.startswith("DEMO DATA – UNCLASSIFIED") and "Fleet Health Score,71" in r.text
    r = client.get("/reports/readiness.pdf", headers=auth("co"))
    assert r.status_code == 200 and r.content[:4] == b"%PDF"


def test_admin_manages_users_and_demo_reset(client, auth):
    admin = auth("admin")
    r = client.post("/users", json={"email": "tech2@vayu.demo", "name": "Second Technician", "role": "TECH", "squadron_code": "SQ7", "password": "demo123"}, headers=admin)
    assert r.status_code == 200, r.text
    assert client.post("/users", json={"email": "bad", "name": "x", "role": "TECH", "password": "1"}, headers=admin).status_code == 422
    assert client.post("/users", json={"email": "t3@vayu.demo", "name": "No Squadron", "role": "TECH", "password": "demo123"}, headers=admin).status_code == 422
    client.post("/alerts/ALT-031/review", json={"decision": "Inspect"}, headers=auth("engo"))
    assert client.get("/dashboard", headers=auth("co")).json()["score"] == 76
    assert client.post("/demo/reset", headers=auth("engo")).status_code == 403
    assert client.post("/demo/reset", headers=admin).json()["score"] == 71
    assert client.get("/dashboard", headers=auth("co")).json()["score"] == 71
    # HQ portfolio
    p = client.get("/portfolio", headers=auth("hq")).json()
    assert [s["code"] for s in p["squadrons"]] == ["SQ12", "SQ7"] and p["top_grounding_spares"][0]["part_no"] == "FUEL-PMP-03"
