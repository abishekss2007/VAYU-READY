"""ISO 13374 block: Data Manipulation. SQLAlchemy 2.0 models (mirror of sql/schema.sql)."""
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base

ROLES = ["CO", "ENGO", "TECH", "LOGO", "BRD", "FSO", "ADMIN", "AUDITOR", "HQ"]
OTP_ROLES = {"CO", "ENGO", "LOGO", "AUDITOR", "ADMIN"}


class BaseStation(Base):
    __tablename__ = "bases"
    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))


class Squadron(Base):
    __tablename__ = "squadrons"
    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    base_code: Mapped[str] = mapped_column(ForeignKey("bases.code"))
    availability_target: Mapped[float] = mapped_column(Float, default=0.75)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(120), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(8))
    squadron_code: Mapped[str | None] = mapped_column(ForeignKey("squadrons.code"), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    otp_required: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notice_ack_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Aircraft(Base):
    __tablename__ = "aircraft"
    tail_no: Mapped[str] = mapped_column(String(20), primary_key=True)
    type: Mapped[str] = mapped_column(String(40))
    squadron_code: Mapped[str] = mapped_column(ForeignKey("squadrons.code"))
    flying_hours: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(8), default="MC")  # MC, PMC, AOG, MAINT
    combat_ready: Mapped[bool] = mapped_column(Boolean, default=True)
    transport_ready: Mapped[bool] = mapped_column(Boolean, default=True)
    health_score: Mapped[int] = mapped_column(Integer, default=100)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    archived_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class Engine(Base):
    __tablename__ = "engines"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    tail_no: Mapped[str] = mapped_column(ForeignKey("aircraft.tail_no"))
    position: Mapped[int] = mapped_column(Integer)
    serial: Mapped[str] = mapped_column(String(30))
    hours_since_overhaul: Mapped[float] = mapped_column(Float)
    overhaul_limit_hours: Mapped[float] = mapped_column(Float)
    cmapss_unit: Mapped[int] = mapped_column(Integer)


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    time: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
    engine_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    cycle: Mapped[int] = mapped_column(Integer)
    op_setting_1: Mapped[float] = mapped_column(Float)
    op_setting_2: Mapped[float] = mapped_column(Float)
    op_setting_3: Mapped[float] = mapped_column(Float)
    s1: Mapped[float] = mapped_column(Float)
    s2: Mapped[float] = mapped_column(Float)
    s3: Mapped[float] = mapped_column(Float)
    s4: Mapped[float] = mapped_column(Float)
    s5: Mapped[float] = mapped_column(Float)
    s6: Mapped[float] = mapped_column(Float)
    s7: Mapped[float] = mapped_column(Float)
    s8: Mapped[float] = mapped_column(Float)
    s9: Mapped[float] = mapped_column(Float)
    s10: Mapped[float] = mapped_column(Float)
    s11: Mapped[float] = mapped_column(Float)
    s12: Mapped[float] = mapped_column(Float)
    s13: Mapped[float] = mapped_column(Float)
    s14: Mapped[float] = mapped_column(Float)
    s15: Mapped[float] = mapped_column(Float)
    s16: Mapped[float] = mapped_column(Float)
    s17: Mapped[float] = mapped_column(Float)
    s18: Mapped[float] = mapped_column(Float)
    s19: Mapped[float] = mapped_column(Float)
    s20: Mapped[float] = mapped_column(Float)
    s21: Mapped[float] = mapped_column(Float)


class Prediction(Base):
    __tablename__ = "predictions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    engine_id: Mapped[str] = mapped_column(ForeignKey("engines.id"))
    time: Mapped[datetime] = mapped_column(DateTime)
    rul_cycles: Mapped[float] = mapped_column(Float)
    anomaly_score: Mapped[float] = mapped_column(Float, default=0)
    model_version: Mapped[str] = mapped_column(String(60))
    shap_top3: Mapped[list] = mapped_column(JSON, default=list)
    # Model governance: stored with every prediction
    trained_on: Mapped[str | None] = mapped_column(String(30), nullable=True)
    dataset: Mapped[str | None] = mapped_column(String(80), nullable=True)
    test_rmse: Mapped[float | None] = mapped_column(Float, nullable=True)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    tail_no: Mapped[str] = mapped_column(ForeignKey("aircraft.tail_no"))
    engine_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    kind: Mapped[str] = mapped_column(String(12))  # RUL, ANOMALY, OVERHAUL, SPARES, RECURRING
    severity: Mapped[str] = mapped_column(String(10))  # Info, Warning, Critical
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    reviewed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decision: Mapped[str | None] = mapped_column(String(12), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    model_version: Mapped[str | None] = mapped_column(String(60), nullable=True)


class Defect(Base):
    __tablename__ = "defects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tail_no: Mapped[str] = mapped_column(ForeignKey("aircraft.tail_no"))
    text: Mapped[str] = mapped_column(Text)
    suggested_category: Mapped[str | None] = mapped_column(String(30), nullable=True)
    confirmed_category: Mapped[str | None] = mapped_column(String(30), nullable=True)
    system: Mapped[str | None] = mapped_column(String(30), nullable=True)
    logged_by: Mapped[str] = mapped_column(String(120))
    logged_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(12), default="Open")  # Open, Closed, Archived


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tail_no: Mapped[str] = mapped_column(ForeignKey("aircraft.tail_no"))
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20), default="scheduled")
    slot_start: Mapped[date] = mapped_column(Date)
    slot_end: Mapped[date] = mapped_column(Date)  # last day of work (inclusive)
    hangar: Mapped[str] = mapped_column(String(30))
    assigned_to: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="Scheduled")  # Scheduled, Done, SignedOff
    hours_spent: Mapped[float | None] = mapped_column(Float, nullable=True)
    completed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    signed_off_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    engine_ids: Mapped[list] = mapped_column(JSON, default=list)
    part_no: Mapped[str | None] = mapped_column(String(20), nullable=True)


class Part(Base):
    __tablename__ = "parts"
    part_no: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    system: Mapped[str] = mapped_column(String(30))
    stock: Mapped[int] = mapped_column(Integer)
    reorder_point: Mapped[int] = mapped_column(Integer)
    lead_time_days: Mapped[int] = mapped_column(Integer)


class Indent(Base):
    __tablename__ = "indents"
    id: Mapped[str] = mapped_column(String(12), primary_key=True)
    part_no: Mapped[str] = mapped_column(ForeignKey("parts.part_no"))
    tail_no: Mapped[str | None] = mapped_column(String(20), nullable=True)
    qty: Mapped[int] = mapped_column(Integer, default=1)
    reason: Mapped[str] = mapped_column(Text)
    needed_by: Mapped[date] = mapped_column(Date)
    raised_by: Mapped[str] = mapped_column(String(120))  # "system" or a user's email
    status: Mapped[str] = mapped_column(String(10), default="Raised")  # Raised, Approved, Received
    created_at: Mapped[datetime] = mapped_column(DateTime)
    fitted: Mapped[bool] = mapped_column(Boolean, default=False)


class HangarSlot(Base):
    __tablename__ = "hangar_slots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    base_code: Mapped[str] = mapped_column(ForeignKey("bases.code"))
    day: Mapped[date] = mapped_column(Date)
    capacity: Mapped[int] = mapped_column(Integer)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[str] = mapped_column(String(32))  # ISO-8601 UTC text, so the hash input never changes shape
    actor: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(10))
    action: Mapped[str] = mapped_column(String(60))
    detail: Mapped[str] = mapped_column(Text)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


# ---- Supporting tables (plans, settings, compliance) ----

class Plan(Base):
    __tablename__ = "plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    squadron_code: Mapped[str] = mapped_column(String(8))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    created_by: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(10), default="Proposed")  # Proposed, Approved
    approved_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class Grievance(Base):
    __tablename__ = "grievances"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(12))  # Grievance, Correction
    raised_by: Mapped[str] = mapped_column(String(120))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(10), default="Open")  # Open, Resolved
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    responded_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Breach(Base):
    """DPDP Act 2023 personal-data breach record (72-hour report to the Data Protection Board)."""
    __tablename__ = "breaches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    what_happened: Mapped[str] = mapped_column(Text)
    impact: Mapped[str] = mapped_column(Text)
    steps_taken: Mapped[str] = mapped_column(Text)
    affected_users: Mapped[list] = mapped_column(JSON, default=list)
    detected_at: Mapped[datetime] = mapped_column(DateTime)
    report_due_at: Mapped[datetime] = mapped_column(DateTime)
    users_informed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    recorded_by: Mapped[str] = mapped_column(String(120))


class Incident(Base):
    """CERT-In Directions 2022 cyber incident record (6-hour report)."""
    __tablename__ = "incidents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_type: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    noticed_at: Mapped[datetime] = mapped_column(DateTime)
    report_due_at: Mapped[datetime] = mapped_column(DateTime)
    reported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    recorded_by: Mapped[str] = mapped_column(String(120))


class SystemLog(Base):
    __tablename__ = "system_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime)
    level: Mapped[str] = mapped_column(String(10))
    message: Mapped[str] = mapped_column(Text)
