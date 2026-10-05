"""PostgreSQL-only check, run by CI after the test suite: does row-level security really hold for vayu_app?

Seeds the database as the owner, then connects as the restricted role and checks what it can see and do.
Run:  TEST_DATABASE_URL=postgresql+psycopg://owner:pw@host/db python backend/tests/check_rls.py
"""
import os
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[2])]
owner_url = os.environ["TEST_DATABASE_URL"]
os.environ["DATABASE_URL"] = os.environ["OWNER_DATABASE_URL"] = owner_url
os.environ["APP_DB_PASSWORD"] = "ci_app_pw"

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.exc import DBAPIError  # noqa: E402

import seed  # noqa: E402

seed.run(quiet=True)
app_url = make_url(owner_url).set(username="vayu_app", password="ci_app_pw")
app = create_engine(app_url, connect_args={"prepare_threshold": None})
failures = []


def count(role, squadron, table):
    with app.begin() as c:
        c.execute(text("SELECT set_config('app.role', :r, true), set_config('app.squadron', :s, true)"), {"r": role, "s": squadron})
        return c.execute(text(f"SELECT count(*) FROM {table}")).scalar()


def expect(label, got, want):
    ok = got == want if not callable(want) else want(got)
    print(f"{'ok  ' if ok else 'FAIL'} {label}: {got}")
    if not ok:
        failures.append(label)


def refused(label, sql):
    try:
        with app.begin() as c:
            c.execute(text("SELECT set_config('app.role', 'SYSTEM', true)"))
            c.execute(text(sql))
        print(f"FAIL {label}: was allowed")
        failures.append(label)
    except DBAPIError as e:
        print(f"ok   {label}: refused ({str(e.orig).splitlines()[0][:70]})")


expect("no role set sees no aircraft", count("", "", "aircraft"), 0)
expect("ENGO SQ7 sees only SQ7 aircraft", count("ENGO", "SQ7", "aircraft"), 18)
expect("TECH SQ7 sees only SQ7 engines", count("TECH", "SQ7", "engines"), 36)
expect("CO SQ12 sees only SQ12 aircraft", count("CO", "SQ12", "aircraft"), 12)
expect("HQ sees all aircraft", count("HQ", "", "aircraft"), 30)
expect("ENGO SQ12 sees no SQ7 alerts", count("ENGO", "SQ12", "alerts"), lambda n: 0 < n < 5)
expect("ADMIN sees aircraft records", count("ADMIN", "", "aircraft"), 30)
expect("ADMIN sees no alerts", count("ADMIN", "", "alerts"), 0)
expect("ADMIN sees no defects", count("ADMIN", "", "defects"), 0)
expect("ADMIN sees no tasks", count("ADMIN", "", "tasks"), 0)
expect("FSO sees all defects", count("FSO", "", "defects"), 20)
refused("vayu_app cannot UPDATE audit_log", "UPDATE audit_log SET detail = 'x' WHERE id = 1")
refused("vayu_app cannot DELETE from audit_log", "DELETE FROM audit_log WHERE id = 1")
refused("vayu_app cannot TRUNCATE audit_log", "TRUNCATE audit_log")
refused("vayu_app cannot DROP a table", "DROP TABLE parts")
with app.begin() as c:
    hyper = c.execute(text("SELECT count(*) FROM timescaledb_information.hypertables WHERE hypertable_name = 'sensor_readings'")).scalar()
expect("sensor_readings is a TimescaleDB hypertable", hyper, 1)

if failures:
    print(f"\n{len(failures)} row-level security check(s) failed: {failures}")
    for f in failures:
        print(f"::error title=row-level security::{f}")  # shown as a GitHub Actions annotation
    sys.exit(1)
print("\nAll row-level security checks passed.")
