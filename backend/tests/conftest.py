"""Test setup: a throw-away database seeded with the synthetic demo data.

Uses SQLite by default. Set TEST_DATABASE_URL (and TEST_OWNER_DATABASE_URL) to run against PostgreSQL.
"""
import os
import tempfile
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="vayu-test-"))
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{(_tmp / 'test.db').as_posix()}")
os.environ["OWNER_DATABASE_URL"] = os.environ.get("TEST_OWNER_DATABASE_URL", os.environ["DATABASE_URL"])
os.environ["MQTT_URL"] = ""
os.environ["MINIO_ENDPOINT"] = ""
os.environ["OTP_DEMO_CODE"] = "482913"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import seed  # noqa: E402
from app.db import open_session  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    """Fresh demo data for every test."""
    seed.run(quiet=True)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db(client):
    s = open_session("SYSTEM")
    yield s
    s.close()


def login(client, who: str) -> dict:
    """Logs in a demo user (with OTP when needed) and returns the auth header."""
    r = client.post("/auth/login", json={"email": f"{who}@vayu.demo", "password": "demo123"})
    assert r.status_code == 200, r.text
    body = r.json()
    if body["stage"] == "otp":
        r = client.post("/auth/otp", json={"code": "482913"}, headers={"Authorization": f"Bearer {body['token']}"})
        assert r.status_code == 200, r.text
        body = r.json()
    return {"Authorization": f"Bearer {body['token']}"}


@pytest.fixture()
def auth(client):
    cache = {}

    def get(who):
        if who not in cache:
            cache[who] = login(client, who)
        return cache[who]
    return get
