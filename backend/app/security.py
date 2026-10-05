"""Passwords (bcrypt), JWT sessions and the role check used by every route."""
from datetime import timedelta

import bcrypt
import jwt
from fastapi import Header, HTTPException

from .config import settings
from .db import open_session, utcnow
from .models import User


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def make_token(user: User, stage: str) -> str:
    minutes = settings.session_minutes if stage == "full" else 5
    payload = {"sub": user.email, "role": user.role, "sq": user.squadron_code, "stage": stage,
               "exp": utcnow() + timedelta(minutes=minutes)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Your session has expired. Please log in again.")
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid session. Please log in again.")


def fail(status: int, message: str):
    raise HTTPException(status, message)


class Ctx:
    """What a route gets: the logged-in user and a database session bound to that user's role and squadron."""

    def __init__(self, user: User, db):
        self.user, self.db = user, db

    @property
    def squadron(self):
        return self.user.squadron_code


def user_from_token(token: str, stage: str = "full") -> Ctx:
    data = decode_token(token)
    if data.get("stage") != stage:
        fail(401, "Complete the 2-step login (OTP) before using the system." if stage == "full" else "This step needs a fresh login.")
    db = open_session(data["role"], data.get("sq"))
    user = db.query(User).filter(User.email == data["sub"]).first()
    if not user or not user.active:
        db.close()
        fail(401, "This account is not active.")
    return Ctx(user, db)


def need(*roles: str, stage: str = "full"):
    """Dependency: login required; if roles are given, only those roles may call the route."""

    def dep(authorization: str | None = Header(None)):
        if not authorization or not authorization.lower().startswith("bearer "):
            fail(401, "Please log in.")
        ctx = user_from_token(authorization[7:], stage)
        try:
            if roles and ctx.user.role not in roles:
                fail(403, f"Your role ({ctx.user.role}) cannot do this")
            yield ctx
        finally:
            ctx.db.close()

    return dep


READ_ONLY_ROLES = {"FSO", "AUDITOR"}
OPS_ROLES = ("CO", "ENGO", "TECH", "LOGO", "BRD", "FSO", "AUDITOR", "HQ")  # everyone except ADMIN
