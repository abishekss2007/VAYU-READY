"""Runtime configuration. Everything comes from environment variables; nothing calls out to the internet."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _db_url(url: str) -> str:
    """Hosted databases hand out postgres:// or postgresql:// URLs; point them at the psycopg 3 driver."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


class Settings:
    database_url = _db_url(os.getenv("DATABASE_URL", "") or f"sqlite:///{ROOT / 'vayu.db'}")
    # The owner connection creates tables and runs the demo reset. The API itself uses DATABASE_URL (vayu_app).
    owner_database_url = _db_url(os.getenv("OWNER_DATABASE_URL", "")) or database_url
    auto_seed = os.getenv("AUTO_SEED", "") == "1"  # cloud copy: load the demo data on first start if the database is empty
    app_db_password = os.getenv("APP_DB_PASSWORD", "vayu_app_pw")
    jwt_secret = os.getenv("JWT_SECRET", "change-me-demo-secret-change-me-demo-secret")
    otp_demo_code = os.getenv("OTP_DEMO_CODE", "482913")
    session_minutes = int(os.getenv("SESSION_MINUTES", "15"))
    cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
    mqtt_url = os.getenv("MQTT_URL", "")  # e.g. mqtt://mqtt:1883 ; empty = live feed disabled
    model_dir = Path(os.getenv("MODEL_DIR", str(ROOT / "models")))
    data_dir = Path(os.getenv("DATA_DIR", str(ROOT / "data")))
    results_dir = Path(os.getenv("RESULTS_DIR", str(ROOT / "results")))
    minio_endpoint = os.getenv("MINIO_ENDPOINT", "")  # e.g. minio:9000 ; empty = file storage disabled
    minio_access_key = os.getenv("MINIO_ROOT_USER", "vayu")
    minio_secret_key = os.getenv("MINIO_ROOT_PASSWORD", "vayu-minio-secret")
    minio_bucket = os.getenv("MINIO_BUCKET", "vayu-private")
    classification = os.getenv("CLASSIFICATION_LABEL", "DEMO DATA – UNCLASSIFIED")
    lockout_attempts = 5
    lockout_minutes = 15
    log_retention_days = 180  # CERT-In Directions 2022: keep logs for 180 days

    # Planning constants (documented on the Schedule screen)
    sorties_per_day = 1.2      # engine cycles per day
    flying_hours_per_day = 2.0  # engine hours per day, used for overhaul limits
    safety_margin_days = 3
    horizon_days = 30
    forecast_day = 9
    critical_rul = 25
    review_hours = 12
    tech_hours_per_day = 80    # 10 technicians x 8 hours
    task_tech_hours = 24       # hours a hangar task uses per day


settings = Settings()
