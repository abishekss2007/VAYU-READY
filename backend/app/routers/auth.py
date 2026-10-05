"""Login: password (bcrypt) -> 2-step OTP for sensitive roles -> 15-minute JWT session."""
from datetime import timedelta

from fastapi import APIRouter, Depends

from .. import audit
from ..config import settings
from ..db import iso, system_session, utcnow
from ..models import User
from ..schemas import LoginIn, OtpIn
from ..security import Ctx, fail, make_token, need, verify_password

router = APIRouter(tags=["auth"])


def _register_failure(db, user: User):
    user.failed_logins += 1
    if user.failed_logins >= settings.lockout_attempts:
        user.locked_until = utcnow() + timedelta(minutes=settings.lockout_minutes)
        audit.write(db, user.email, user.role, "ACCOUNT_LOCKED", f"Account locked after {settings.lockout_attempts} failed logins")
    db.commit()


def _check_lock(user: User):
    if user.locked_until and user.locked_until > utcnow():
        mins = int((user.locked_until - utcnow()).total_seconds() // 60) + 1
        fail(423, f"Account locked after {settings.lockout_attempts} failed logins. Try again in {mins} minutes or ask the Admin to unlock it.")


@router.post("/auth/login")
def login(body: LoginIn):
    db = system_session()
    try:
        user = db.query(User).filter(User.email == body.email.strip().lower()).first()
        if not user or not user.active:
            fail(401, "Wrong email or password.")
        _check_lock(user)
        if not verify_password(body.password, user.password_hash):
            _register_failure(db, user)
            _check_lock(user)
            fail(401, "Wrong email or password.")
        if user.otp_required:
            return {"stage": "otp", "token": make_token(user, "otp"), "message": "Enter the 6-digit code to finish logging in."}
        user.failed_logins, user.locked_until = 0, None
        audit.write(db, user.email, user.role, "LOGIN", "Logged in")
        db.commit()
        return {"stage": "full", "token": make_token(user, "full"), "message": "Logged in."}
    finally:
        db.close()


@router.post("/auth/otp")
def otp(body: OtpIn, ctx: Ctx = Depends(need(stage="otp"))):
    user = ctx.user
    _check_lock(user)
    if body.code != settings.otp_demo_code:
        _register_failure(ctx.db, user)
        _check_lock(user)
        fail(401, "Wrong code. Please try again.")
    user.failed_logins, user.locked_until = 0, None
    audit.write(ctx.db, user.email, user.role, "LOGIN", "Logged in with 2-step code")
    ctx.db.commit()
    return {"stage": "full", "token": make_token(user, "full"), "message": "Logged in."}


@router.get("/auth/me")
def me(ctx: Ctx = Depends(need())):
    u = ctx.user
    return {"email": u.email, "name": u.name, "role": u.role, "squadron_code": u.squadron_code, "otp_required": u.otp_required,
            "notice_acknowledged": u.notice_ack_at is not None, "notice_ack_at": iso(u.notice_ack_at),
            "read_only": u.role in ("FSO", "AUDITOR"), "session_minutes": settings.session_minutes}
