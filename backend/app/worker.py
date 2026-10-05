"""Background worker: APScheduler jobs + MQTT sensor replay.  Run:  python -m app.worker

Jobs: RUL checks, overhaul limits, spares alerts, escalations, log retention.
Replay: publishes each engine's stored sensor cycles to MQTT every few seconds, as a live feed.
The replay only feeds the live view; it never changes predictions, alerts or aircraft status.
"""
import json
import logging
import random
import time

from apscheduler.schedulers.background import BackgroundScheduler

from . import jobs
from .db import iso, system_session, utcnow
from .live import mqtt_client
from .models import Engine, SensorReading, Setting

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
log = logging.getLogger("vayu.worker")
REPLAY_SECONDS = 3
REPLAY_CYCLES = 40
LIVE_SENSORS = ["s2", "s3", "s4", "s7", "s8", "s9", "s11", "s12", "s15", "s17", "s20", "s21"]


def run_jobs():
    db = system_session()
    try:
        log.info("jobs: %s", jobs.run_all(db))
    except Exception:
        log.exception("jobs failed")
    finally:
        db.close()


def load_replay():
    """The last 40 stored cycles of every engine, replayed in a loop."""
    db = system_session()
    try:
        buf = {}
        for e in db.query(Engine).all():
            rows = (db.query(SensorReading).filter(SensorReading.engine_id == e.id).order_by(SensorReading.cycle.desc())
                    .limit(REPLAY_CYCLES).all())[::-1]
            buf[e.id] = (e.tail_no, [{s: getattr(r, s) for s in LIVE_SENSORS} | {"cycle": r.cycle} for r in rows])
        return buf
    finally:
        db.close()


def stream_running() -> bool:
    db = system_session()
    try:
        s = db.get(Setting, "stream_running")
        return bool(s and s.value == "1")
    except Exception:
        return False
    finally:
        db.close()


def main():
    sched = BackgroundScheduler(timezone="UTC")
    sched.add_job(run_jobs, "interval", minutes=5)
    sched.start()
    client = None
    while client is None:
        client = mqtt_client("vayu-worker")
        if client is None:
            log.info("waiting for MQTT broker...")
            time.sleep(5)
    client.loop_start()
    rng = random.Random(1)
    buf, loaded_at, step = {}, 0.0, 0
    while True:
        if stream_running():
            if not buf or time.time() - loaded_at > 300:
                buf, loaded_at = load_replay(), time.time()
            for eid, (tail, rows) in buf.items():
                if not rows:
                    continue
                r = rows[step % len(rows)]
                values = {s: round(r[s] * (1 + rng.gauss(0, 0.0004)), 3) for s in LIVE_SENSORS}  # tiny jitter so the feed looks live
                client.publish(f"vayu/sensors/{eid}", json.dumps({"engine_id": eid, "tail_no": tail, "cycle": r["cycle"],
                                                                  "time": iso(utcnow()), "values": values}))
            step += 1
        time.sleep(REPLAY_SECONDS)


if __name__ == "__main__":
    main()
