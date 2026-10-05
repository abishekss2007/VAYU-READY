"""1. Login  2. Roles  3. Squadron privacy  (+ account lockout from the compliance prompt)."""
import time

import jwt

from app.config import settings


def test_wrong_password_returns_401(client):
    r = client.post("/auth/login", json={"email": "tech@vayu.demo", "password": "nope"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Wrong email or password."


def test_co_needs_otp_and_otp_stage_token_cannot_call_api(client):
    r = client.post("/auth/login", json={"email": "co@vayu.demo", "password": "demo123"})
    assert r.json()["stage"] == "otp"
    half = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/dashboard", headers=half).status_code == 401
    assert client.get("/auth/me", headers=half).status_code == 401
    assert client.post("/auth/otp", json={"code": "000000"}, headers=half).status_code == 401
    full = client.post("/auth/otp", json={"code": "482913"}, headers=half).json()
    assert full["stage"] == "full"
    assert client.get("/dashboard", headers={"Authorization": f"Bearer {full['token']}"}).status_code == 200


def test_technician_logs_in_without_otp_and_session_is_15_minutes(client):
    r = client.post("/auth/login", json={"email": "tech@vayu.demo", "password": "demo123"}).json()
    assert r["stage"] == "full"
    claims = jwt.decode(r["token"], settings.jwt_secret, algorithms=["HS256"])
    assert 14 * 60 < claims["exp"] - time.time() <= 15 * 60


def test_account_locks_after_5_failed_logins(client):
    for _ in range(4):
        assert client.post("/auth/login", json={"email": "tech@vayu.demo", "password": "bad"}).status_code == 401
    r = client.post("/auth/login", json={"email": "tech@vayu.demo", "password": "bad"})
    assert r.status_code == 423 and "locked" in r.json()["detail"]
    # even the right password is refused while locked
    assert client.post("/auth/login", json={"email": "tech@vayu.demo", "password": "demo123"}).status_code == 423


def test_technician_cannot_open_dashboard(client, auth):
    r = client.get("/dashboard", headers=auth("tech"))
    assert r.status_code == 403
    assert r.json()["detail"] == "Your role (TECH) cannot do this"


def test_admin_cannot_see_alerts_or_defects(client, auth):
    for path in ("/alerts", "/defects", "/tasks", "/dashboard"):
        assert client.get(path, headers=auth("admin")).status_code == 403, path
    assert client.get("/users", headers=auth("admin")).status_code == 200
    assert client.get("/aircraft", headers=auth("admin")).status_code == 200


def test_fso_and_auditor_are_read_only(client, auth):
    for who in ("fso", "auditor"):
        h = auth(who)
        assert client.get("/alerts", headers=h).status_code == 200
        assert client.get("/dashboard", headers=h).status_code == 200
        assert client.post("/alerts/ALT-031/review", json={"decision": "Inspect"}, headers=h).status_code == 403
        assert client.post("/defects", json={"tail_no": "TAIL-SQ7-101", "text": "test defect"}, headers=h).status_code == 403
        assert client.patch("/aircraft/TAIL-SQ7-101/status", json={"status": "AOG", "reason": "test"}, headers=h).status_code == 403
        assert client.post("/indents/IND-012/approve", headers=h).status_code == 403
        assert client.post("/schedule/approve", headers=h).status_code == 403
        assert client.post("/users", json={}, headers=h).status_code == 403


def test_sq7_engineering_officer_cannot_see_sq12_aircraft(client, auth):
    h = auth("engo")
    tails = [a["tail_no"] for a in client.get("/aircraft", headers=h).json()]
    assert len(tails) == 18 and all(t.startswith("TAIL-SQ7-") for t in tails)
    assert client.get("/aircraft?squadron=SQ12", headers=h).status_code == 403
    assert client.get("/aircraft/TAIL-SQ12-201/twin", headers=h).status_code == 404
    assert client.get("/dashboard?squadron=SQ12", headers=h).status_code == 403
    assert all(a["tail_no"].startswith("TAIL-SQ7-") for a in client.get("/alerts", headers=h).json()["alerts"])
    # HQ sees both squadrons
    assert len(client.get("/aircraft", headers=auth("hq")).json()) == 30
