"""Tamper-proof audit trail: append-only, each entry SHA-256 chained to the previous one."""
import hashlib

from sqlalchemy import text

from .db import utcnow
from .models import AuditLog

GENESIS = "0" * 64


def entry_hash(ts, actor, role, action, detail, prev_hash) -> str:
    return hashlib.sha256(f"{ts}|{actor}|{role}|{action}|{detail}|{prev_hash}".encode()).hexdigest()


def write(db, actor: str, role: str, action: str, detail: str) -> AuditLog:
    """Adds one entry inside the caller's transaction (the caller commits)."""
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(726249)"))  # one writer at a time keeps the chain straight
    last = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    prev = last.hash if last else GENESIS
    ts = utcnow().isoformat(timespec="milliseconds") + "Z"
    row = AuditLog(ts=ts, actor=actor, role=role, action=action, detail=detail, prev_hash=prev,
                   hash=entry_hash(ts, actor, role, action, detail, prev))
    db.add(row)
    db.flush()
    return row


def verify(db) -> dict:
    """Recomputes every hash. Returns the first entry that does not match, if any."""
    prev = GENESIS
    count = 0
    for e in db.query(AuditLog).order_by(AuditLog.id):
        count += 1
        if e.prev_hash != prev or e.hash != entry_hash(e.ts, e.actor, e.role, e.action, e.detail, e.prev_hash):
            return {"intact": False, "first_broken_entry": e.id, "entries": count,
                    "message": f"Entry {e.id} does not match its hash. It was changed after it was written."}
        prev = e.hash
    return {"intact": True, "first_broken_entry": None, "entries": count, "message": "All entries intact"}
