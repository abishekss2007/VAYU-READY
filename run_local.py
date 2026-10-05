"""Run the API without Docker, for quick local checks (SQLite, no MQTT, no MinIO).

    python run_local.py            # seeds vayu.db if it does not exist, then serves http://localhost:8000
    python run_local.py --reseed   # reload the demo data first

The full offline deployment (PostgreSQL + TimescaleDB + RLS, MQTT, MinIO) is docker-compose; see README.md.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / "backend"), str(ROOT)]
os.environ.setdefault("DATABASE_URL", f"sqlite:///{(ROOT / 'vayu.db').as_posix()}")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")

if __name__ == "__main__":
    import uvicorn

    if "--reseed" in sys.argv or not (ROOT / "vayu.db").exists():
        import seed
        seed.run()
    uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.getenv("PORT", "8000")))
