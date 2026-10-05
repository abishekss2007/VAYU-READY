"""ISO 13374 block: Data Manipulation. Database engines and sessions."""
from datetime import datetime, timezone

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


def _make(url: str):
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    # prepare_threshold=None: no server-side prepared statements, so the demo reset (drop + recreate) is safe
    args = {"prepare_threshold": None} if "+psycopg" in url else {}
    return create_engine(url, pool_pre_ping=True, connect_args=args)


engine = _make(settings.database_url)
owner_engine = engine if settings.owner_database_url == settings.database_url else _make(settings.owner_database_url)
IS_PG = engine.dialect.name == "postgresql"
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    """All timestamps are stored as naive UTC."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(dt):
    return dt.isoformat(timespec="seconds") + "Z" if dt else None


@event.listens_for(Session, "after_begin")
def _set_rls_context(session, transaction, connection):
    """Tell PostgreSQL who is asking, so row-level security can filter by role and squadron."""
    if connection.dialect.name != "postgresql":
        return
    connection.execute(
        text("SELECT set_config('app.role', :r, true), set_config('app.squadron', :s, true)"),
        {"r": session.info.get("role", ""), "s": session.info.get("squadron", "") or ""},
    )


def open_session(role: str = "", squadron: str | None = None) -> Session:
    s = SessionLocal()
    s.info["role"], s.info["squadron"] = role, squadron
    return s


def system_session() -> Session:
    """Used by background jobs and the login step (before the user's role is known)."""
    return open_session("SYSTEM")
