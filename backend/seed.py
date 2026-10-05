"""Fill VAYU-READY with synthetic demo data.  Run:  python backend/seed.py   (or: make seed)

FAKE squadron data only: no real aircraft, units or people. Sensor data comes from the public
NASA C-MAPSS FD001 data set (or a synthetic stand-in if the files are missing).

The SQ7 scenario is exact: the Commander dashboard opens at Fleet Health Score 71/100.
"""
import json
import random
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app import audit, models as m, state  # noqa: E402
from app.config import settings  # noqa: E402
from app.db import Base, owner_engine, utcnow  # noqa: E402
from app.security import hash_password  # noqa: E402
from ml import common as mlc  # noqa: E402
from ml.defect_data import synthetic_defects  # noqa: E402

SQL_DIR = Path(__file__).resolve().parent / "sql"
SQLITE_TRIGGERS = [
    "CREATE TRIGGER IF NOT EXISTS audit_log_no_update BEFORE UPDATE ON audit_log BEGIN SELECT RAISE(ABORT, 'audit_log is append-only: UPDATE is not allowed'); END",
    "CREATE TRIGGER IF NOT EXISTS audit_log_no_delete BEFORE DELETE ON audit_log BEGIN SELECT RAISE(ABORT, 'audit_log is append-only: DELETE is not allowed'); END",
]

USERS = [  # every user: password "demo123", OTP code from OTP_DEMO_CODE (482913)
    ("co@vayu.demo", "Demo Commander", "CO", "SQ7"), ("engo@vayu.demo", "Demo Engineering Officer", "ENGO", "SQ7"),
    ("tech@vayu.demo", "Demo Technician", "TECH", "SQ7"), ("logo@vayu.demo", "Demo Logistics Officer", "LOGO", None),
    ("brd@vayu.demo", "Demo BRD Planner", "BRD", None), ("fso@vayu.demo", "Demo Flight Safety Officer", "FSO", None),
    ("admin@vayu.demo", "Demo Administrator", "ADMIN", None), ("auditor@vayu.demo", "Demo Auditor", "AUDITOR", None),
    ("hq@vayu.demo", "Demo Air HQ Staff", "HQ", None),
]
PARTS = [  # part_no, name, system, stock, reorder point, lead time (days)
    ("HPC-MOD-07", "HPC module", "Engine", 0, 1, 21), ("HYD-ACT-22", "MLG actuator", "Hydraulics", 0, 1, 14),
    ("FUEL-PMP-03", "Fuel pump", "Fuel", 0, 1, 10),
    ("LPT-MOD-04", "LPT module", "Engine", 2, 1, 21), ("FAN-MOD-02", "Fan module", "Engine", 2, 1, 18),
    ("CORE-BRG-09", "Core bearing set", "Engine", 4, 2, 12), ("AVX-MFD-11", "Multi-function display", "Avionics", 3, 1, 15),
    ("AVX-INS-05", "Inertial navigation unit", "Avionics", 2, 1, 25), ("ELE-GEN-08", "Generator", "Electrical", 3, 1, 12),
    ("ELE-BAT-01", "Main battery", "Electrical", 6, 2, 7), ("LDG-TYR-14", "MLG tyre", "Landing gear", 24, 8, 5),
    ("LDG-BRK-06", "Brake unit", "Landing gear", 8, 3, 9), ("ECS-VLV-10", "ECS bleed valve", "Environmental control", 3, 1, 14),
    ("AFR-SEAL-12", "Canopy seal", "Airframe", 5, 2, 6), ("FUEL-FLT-13", "Fuel filter", "Fuel", 30, 10, 4),
]
REASONS_HPC = [
    {"sensor": "s3", "name": "HPC outlet temperature", "direction": "rising", "impact_cycles": -31.0, "text": "HPC outlet temperature rising"},
    {"sensor": "s8", "name": "Fan speed", "direction": "rising", "impact_cycles": -12.4, "text": "Fan speed drift"},
    {"sensor": "s11", "name": "HPC outlet static pressure", "direction": "rising", "impact_cycles": -9.8, "text": "HPC outlet static pressure rising"},
]
REASONS_LPT = [
    {"sensor": "s4", "name": "LPT outlet temperature", "direction": "rising", "impact_cycles": -27.5, "text": "LPT outlet temperature rising"},
    {"sensor": "s21", "name": "LPT coolant bleed", "direction": "falling", "impact_cycles": -11.2, "text": "LPT coolant bleed falling"},
    {"sensor": "s9", "name": "Core speed", "direction": "rising", "impact_cycles": -6.9, "text": "Core speed rising"},
]
REASONS_OK = [
    {"sensor": "s11", "name": "HPC outlet static pressure", "direction": "steady", "impact_cycles": 4.1, "text": "HPC outlet static pressure steady"},
    {"sensor": "s4", "name": "LPT outlet temperature", "direction": "steady", "impact_cycles": 3.2, "text": "LPT outlet temperature steady"},
    {"sensor": "s15", "name": "Bypass ratio", "direction": "steady", "impact_cycles": 1.7, "text": "Bypass ratio steady"},
]


def create_schema(engine):
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.exec_driver_sql((SQL_DIR / "schema.sql").read_text())
            conn.exec_driver_sql((SQL_DIR / "rls.sql").read_text())
            pw = settings.app_db_password.replace("'", "''")
            conn.exec_driver_sql(f"ALTER ROLE vayu_app PASSWORD '{pw}'")
    else:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            for t in SQLITE_TRIGGERS:
                conn.exec_driver_sql(t)


def run(engine=owner_engine, quiet=False):
    create_schema(engine)
    rng = random.Random(7)
    now = utcnow()
    today = now.date()
    train, _, _, dataset = mlc.load_fd001(quiet=quiet)
    lives = train.groupby("unit")["cycle"].max().to_dict()
    metrics_path = settings.results_dir / "metrics.json"
    metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
    rmse = metrics.get("rul", {}).get("best_rmse")

    with Session(engine) as db:
        db.add_all([m.BaseStation(code="BA", name="Base Alpha"), m.BaseStation(code="BB", name="Base Bravo")])
        db.flush()
        db.add_all([m.Squadron(code="SQ7", name="Demo Squadron 7", base_code="BA"),
                    m.Squadron(code="SQ12", name="Demo Squadron 12", base_code="BB")])
        db.flush()
        pw = hash_password("demo123")
        db.add_all([m.User(email=e, name=n, role=r, squadron_code=s, password_hash=pw, otp_required=r in m.OTP_ROLES)
                    for e, n, r, s in USERS])

        # ---- aircraft: 18 in SQ7, 12 in SQ12, all fictional "Demo Fighter-A" ----
        status = {105: "AOG", 109: "AOG", 111: "MAINT", 116: "MAINT", 204: "PMC", 207: "AOG", 210: "MAINT"}
        not_combat = {102, 110, 203}  # open avionics defects: transport-ready but not combat-ready
        nums = [("SQ7", n) for n in range(101, 119)] + [("SQ12", n) for n in range(201, 213)]
        for sq, n in nums:
            db.add(m.Aircraft(tail_no=f"TAIL-{sq}-{n}", type="Demo Fighter-A", squadron_code=sq,
                              flying_hours=rng.randint(800, 2400), status=status.get(n, "MC"),
                              combat_ready=n not in not_combat, transport_ready=True))
        db.flush()

        # ---- engines: exact scenario values first, healthy values for the rest ----
        rul_exact = {"ENG-114-2": 18, "ENG-103-1": 23}
        hours_left_exact = {"ENG-108-1": 8, "ENG-108-2": 12, "ENG-113-1": 14}   # the 3 engines due within 30 days
        brd_window = {"ENG-102-2": 96, "ENG-106-1": 124, "ENG-115-1": 150, "ENG-118-2": 172, "ENG-203-1": 110, "ENG-209-2": 164}
        unit = 0
        readings, preds, engines = [], [], []
        for sq, n in nums:
            for pos in (1, 2):
                eid = f"ENG-{n}-{pos}"
                rul = rul_exact.get(eid, rng.randint(60, 180))
                left = hours_left_exact.get(eid, brd_window.get(eid, rng.randint(190, 900)))
                while True:  # map to a C-MAPSS unit that has enough life for this RUL
                    unit = unit % 100 + 1
                    if lives[unit] - rul >= 45:
                        break
                engines.append(m.Engine(id=eid, tail_no=f"TAIL-{sq}-{n}", position=pos, serial=f"DEMO-ENG-{n}{pos:02d}",
                                        hours_since_overhaul=1500 - left, overhaul_limit_hours=1500, cmapss_unit=unit))
                current = lives[unit] - rul  # load cycles up to this point, so the true RUL matches the scenario
                rows = train[(train["unit"] == unit) & (train["cycle"] <= current)].tail(120)
                for r in rows.itertuples(index=False):
                    d = r._asdict()
                    readings.append({"time": now - timedelta(days=(current - d["cycle"]) / settings.sorties_per_day), "engine_id": eid,
                                     "cycle": int(d["cycle"]), **{k: float(d[k]) for k in mlc.OPS + mlc.SENSORS}})
                critical = eid in rul_exact
                reasons = REASONS_HPC if eid == "ENG-114-2" else REASONS_LPT if eid == "ENG-103-1" else REASONS_OK
                final_anomaly = {"ENG-114-2": 0.82, "ENG-103-1": 0.61}.get(eid, round(rng.uniform(0.05, 0.3), 2))
                for j in range(11, -1, -1):  # 12 history points, 5 cycles apart, RUL falling
                    preds.append(m.Prediction(
                        engine_id=eid, time=now - timedelta(days=j * 5 / settings.sorties_per_day), rul_cycles=float(rul + j * 5),
                        anomaly_score=round(max(final_anomaly - (0.06 * j if critical else 0), 0.03), 2),
                        model_version="scenario-seed (true RUL at the replay point)", shap_top3=reasons,
                        trained_on=metrics.get("trained_on"), dataset=dataset, test_rmse=rmse))
        db.add_all(engines)
        db.flush()
        db.execute(m.SensorReading.__table__.insert(), readings)
        db.add_all(preds)

        db.add_all([m.Part(part_no=p, name=nm, system=s, stock=st, reorder_point=rp, lead_time_days=lt) for p, nm, s, st, rp, lt in PARTS])
        db.flush()
        db.add_all([
            m.Indent(id="IND-009", part_no="FUEL-PMP-03", tail_no="TAIL-SQ12-207", qty=1, reason="AOG: fuel pump failed on ground run",
                     needed_by=today, raised_by="logo@vayu.demo", status="Approved", created_at=now - timedelta(days=3)),
            m.Indent(id="IND-010", part_no="HYD-ACT-22", tail_no="TAIL-SQ7-105", qty=1, reason="AOG: left MLG actuator leaking",
                     needed_by=today, raised_by="logo@vayu.demo", status="Approved", created_at=now - timedelta(days=13)),
            m.Indent(id="IND-011", part_no="FUEL-PMP-03", tail_no="TAIL-SQ7-109", qty=1, reason="AOG: fuel pump low pressure",
                     needed_by=today, raised_by="logo@vayu.demo", status="Approved", created_at=now - timedelta(days=2)),
            m.Indent(id="IND-012", part_no="HPC-MOD-07", tail_no="TAIL-SQ7-114", qty=1,
                     reason="Predicted failure: Engine 2 RUL 18 cycles (HPC). Raised automatically.",
                     needed_by=today + timedelta(days=12), raised_by="system", status="Raised", created_at=now - timedelta(hours=14)),
        ])

        def alert(i, tail, eng, kind, sev, msg, age_h, **kw):
            return m.Alert(id=f"ALT-{i:03d}", tail_no=tail, engine_id=eng, kind=kind, severity=sev, message=msg,
                           created_at=now - timedelta(hours=age_h), **kw)
        db.add_all([
            alert(22, "TAIL-SQ12-207", None, "SPARES", "Warning", "AOG: waiting for FUEL-PMP-03 (Fuel pump). Stock 0, lead time 10 days.", 70),
            alert(24, "TAIL-SQ7-108", "ENG-108-1", "OVERHAUL", "Warning", "Engine 1: 8 hours left before the overhaul limit (10 hours reminder).", 30),
            alert(25, "TAIL-SQ7-108", "ENG-108-2", "OVERHAUL", "Warning", "Engine 2: 12 hours left before the overhaul limit (25 hours reminder).", 52),
            alert(26, "TAIL-SQ7-113", "ENG-113-1", "OVERHAUL", "Warning", "Engine 1: 14 hours left before the overhaul limit (25 hours reminder).", 49),
            alert(27, "TAIL-SQ7-107", None, "RECURRING", "Warning", "Recurring defect: Hydraulics logged 3 times in 30 days.", 71),
            alert(28, "TAIL-SQ7-105", None, "SPARES", "Warning", "AOG: waiting for HYD-ACT-22 (MLG actuator). Stock 0, lead time 14 days.", 312),
            alert(29, "TAIL-SQ7-109", None, "SPARES", "Warning", "AOG: waiting for FUEL-PMP-03 (Fuel pump). Stock 0, lead time 10 days.", 48),
            alert(30, "TAIL-SQ7-103", "ENG-103-1", "RUL", "Critical", "Engine 1 RUL 23 cycles (under 25). Top reason: LPT outlet temperature rising.", 20,
                  reviewed_by="engo@vayu.demo", reviewed_at=now - timedelta(hours=16), decision="Schedule",
                  note="Engine change to be planned; LPT module in stock.", model_version="scenario-seed"),
            alert(31, "TAIL-SQ7-114", "ENG-114-2", "RUL", "Critical", "Engine 2 RUL 18 cycles (under 25). Top reason: HPC outlet temperature rising.", 14,
                  model_version="scenario-seed"),
            alert(32, "TAIL-SQ7-114", "ENG-114-2", "ANOMALY", "Warning", "Unusual sensor pattern on Engine 2 (anomaly score 0.82).", 60,
                  model_version="scenario-seed"),
        ])

        # ---- tasks already in the calendar ----
        db.add_all([
            m.Task(tail_no="TAIL-SQ7-111", title="Scheduled 300-hour servicing", kind="scheduled", slot_start=today - timedelta(days=3),
                   slot_end=today + timedelta(days=10), hangar="Hangar 1", assigned_to="tech@vayu.demo"),
            m.Task(tail_no="TAIL-SQ7-111", title="Replace worn brake unit (left wheel)", kind="scheduled", slot_start=today,
                   slot_end=today, hangar="Flight line", assigned_to="tech@vayu.demo", part_no="LDG-BRK-06"),
            m.Task(tail_no="TAIL-SQ7-116", title="Depot-level structural inspection", kind="scheduled", slot_start=today - timedelta(days=10),
                   slot_end=today + timedelta(days=33), hangar="BRD Depot", assigned_to=None),
            m.Task(tail_no="TAIL-SQ7-117", title="Calendar phase inspection (booked)", kind="scheduled", slot_start=today + timedelta(days=6),
                   slot_end=today + timedelta(days=31), hangar="BRD Depot", assigned_to=None),
            m.Task(tail_no="TAIL-SQ12-210", title="Scheduled 150-hour servicing", kind="scheduled", slot_start=today - timedelta(days=1),
                   slot_end=today + timedelta(days=4), hangar="Hangar 1", assigned_to=None),
        ])

        # ---- 20 past defects ----
        def defect(tail, txt, cat, days_ago, status="Closed"):
            return m.Defect(tail_no=tail, text=txt, suggested_category=cat, confirmed_category=cat, system=cat,
                            logged_by="tech@vayu.demo", logged_at=now - timedelta(days=days_ago), status=status)
        defects = [
            defect("TAIL-SQ7-107", "hyd leak near left MLG actuator", "Hydraulics", 25),
            defect("TAIL-SQ7-107", "hyd leak near left MLG actuator, seal replaced last time", "Hydraulics", 14),
            defect("TAIL-SQ7-107", "hyd leak near left MLG actuator again", "Hydraulics", 3, "Open"),
            defect("TAIL-SQ7-102", "radar display blank intermittently", "Avionics", 2, "Open"),
            defect("TAIL-SQ7-110", "weapons interface bus fault on power-up", "Avionics", 1, "Open"),
            defect("TAIL-SQ12-203", "INS drift excessive after 1 hour", "Avionics", 4, "Open"),
            defect("TAIL-SQ7-104", "intermittent fuel qty indication", "Fuel", 18),
            defect("TAIL-SQ7-112", "ECS duct temp high on climb", "Environmental control", 22),
            defect("TAIL-SQ7-101", "nose wheel steering sluggish", "Landing gear", 35),
        ]
        closed_tails = [f"TAIL-SQ7-{n}" for n in (101, 104, 106, 112, 115, 118)] + [f"TAIL-SQ12-{n}" for n in (201, 205, 208, 211, 212)]
        for i, (txt, cat) in enumerate(synthetic_defects(200, 7)[:11]):
            defects.append(defect(closed_tails[i], txt, cat, 8 + i * 4))
        db.add_all(defects)

        for base in ("BA", "BB"):  # 2 hangar slots per day at each base
            db.add_all([m.HangarSlot(base_code=base, day=today + timedelta(days=d), capacity=2) for d in range(45)])
        db.add_all([m.Setting(key=k, value=v) for k, v in {
            "classification": settings.classification, "certin_poc_name": "Demo IT Security Officer (fictional)",
            "certin_poc_contact": "itsec@vayu.demo", "ntp_servers": "samay1.nic.in, time.nplindia.org",
            "log_retention_days": "180", "stream_running": "0", "grievance_contact": "admin@vayu.demo",
            "technicians": "10", "technician_hours_per_day": "8",
        }.items()])
        db.add(m.SystemLog(ts=now, level="INFO", message="Demo data loaded"))
        db.flush()
        state.refresh_health(db, [f"TAIL-{sq}-{n}" for sq, n in nums])

        for action, detail in [
            ("DATA_LOADED", f"Demo data loaded: 2 squadrons, 30 aircraft, 60 engines. Sensor source: {dataset}"),
            ("PREDICTIONS_COMPUTED", "RUL and anomaly predictions computed for 60 engines"),
            ("ALERT_CREATED", "Critical alert ALT-031 created for TAIL-SQ7-114 Engine 2 (RUL 18 cycles)"),
            ("INDENT_RAISED", "Indent IND-012 auto-raised for HPC-MOD-07 (TAIL-SQ7-114)"),
            ("DEFECT_LOGGED", "Defect logged on TAIL-SQ7-107: hyd leak near left MLG actuator again"),
        ]:
            audit.write(db, "system", "SYSTEM", action, detail)
        db.commit()
        score = state.fleet_score(db, "SQ7")
    if not quiet:
        print(f"Seeded demo data ({dataset}). SQ7 Fleet Health Score: {score['score']}/100")
        for r in score["rules"]:
            print(f"  {r['points']:>4}  {r['label']}: {r['detail']}")
    return score


if __name__ == "__main__":
    run()
