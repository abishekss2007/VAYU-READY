"""Compliance: model governance, DPDP Act 2023 (personnel data), CERT-In Directions 2022, ISO 13374 mapping."""
import json
from datetime import timedelta

from fastapi import APIRouter, Depends

from ..config import settings
from ..db import iso, utcnow
from ..models import Alert, AuditLog, Breach, Grievance, Incident, SystemLog, User
from ..schemas import INCIDENT_TYPES, BreachIn, GrievanceIn, IncidentIn, RespondIn, SettingsIn
from ..security import Ctx, fail, need
from .admin import put_setting, setting
from .common import finish

router = APIRouter(tags=["compliance"])
BREACH_HOURS = 72   # DPDP: report to the Data Protection Board
CERTIN_HOURS = 6    # CERT-In Directions 2022
CERTIN_EMAIL = "incident@cert-in.org.in"

ISO_13374 = [
    {"block": "Data Acquisition", "modules": ["app/live.py (MQTT sensor feed)", "app/routers/admin.py (CSV/Excel import)", "ml/common.py (C-MAPSS loader)"]},
    {"block": "Data Manipulation", "modules": ["app/db.py", "app/models.py (records stored against the tail number)", "ml/common.py (scaling, windows)"]},
    {"block": "State Detection", "modules": ["ml/infer.py: anomaly_scores (autoencoder)", "ml/infer.py: classify_defect (defect NLP)"]},
    {"block": "Health Assessment", "modules": ["app/state.py (aircraft health score, Fleet Health Score, digital twin)"]},
    {"block": "Prognostic Assessment", "modules": ["ml/infer.py: predict (RUL per engine)", "optimiser/forecast.py (readiness forecast)"]},
    {"block": "Advisory Generation", "modules": ["app/jobs.py (alerts, indents, escalation)", "optimiser/plan.py (OR-Tools plan)", "app/planning.py", "dashboards and reports"]},
]

NOTICE = {
    "en": {"title": "Privacy notice",
           "body": "VAYU-READY keeps only this personal data about you: name, role, squadron and email. It is used for one purpose: "
                   "maintenance accountability (who logged, did, reviewed or approved a piece of work). No phone numbers, addresses or "
                   "health data are stored. You can view your data under 'My data' and ask the Admin to correct it. "
                   "For questions or complaints, use the grievance form or contact: {contact}."},
    "hi": {"title": "गोपनीयता सूचना",
           "body": "VAYU-READY आपके बारे में केवल यह व्यक्तिगत जानकारी रखता है: नाम, भूमिका, स्क्वाड्रन और ईमेल। इसका उपयोग केवल एक उद्देश्य के लिए होता है: "
                   "रखरखाव की जवाबदेही (किसने काम दर्ज किया, किया, जाँचा या स्वीकृत किया)। कोई फ़ोन नंबर, पता या स्वास्थ्य जानकारी नहीं रखी जाती। "
                   "आप 'मेरा डेटा' में अपनी जानकारी देख सकते हैं और एडमिन से सुधार का अनुरोध कर सकते हैं। "
                   "प्रश्न या शिकायत के लिए शिकायत फ़ॉर्म का उपयोग करें या संपर्क करें: {contact}।"},
}


# ---------- public configuration (banner) ----------

@router.get("/config/public")
def public_config():
    from ..db import system_session
    db = system_session()
    try:
        return {"classification": setting(db, "classification", settings.classification), "app": "VAYU-READY",
                "offline": True, "session_minutes": settings.session_minutes}
    finally:
        db.close()


# ---------- model governance ----------

def false_alarm_rates(db) -> dict:
    out = {}
    for kind in ("RUL", "ANOMALY"):
        reviewed = db.query(Alert).filter(Alert.kind == kind, Alert.reviewed_at.isnot(None)).count()
        false_ = db.query(Alert).filter(Alert.kind == kind, Alert.decision == "FalseAlarm").count()
        out[kind] = {"reviewed": reviewed, "false_alarms": false_, "rate": round(false_ / reviewed, 3) if reviewed else None}
    return out


@router.get("/models/cards")
def model_cards(ctx: Ctx = Depends(need())):
    path = settings.results_dir / "model_cards.json"
    cards = json.loads(path.read_text()) if path.exists() else []
    rates = false_alarm_rates(ctx.db) if ctx.user.role != "ADMIN" else {}
    for c in cards:
        c["false_alarm"] = rates.get(c.get("alert_kind"))
    return {"cards": cards, "trained": bool(cards), "advisory": "Advisory. Final decision rests with the authorised engineer.",
            "message": None if cards else "Models have not been trained yet. Run 'make train'."}


# ---------- DPDP: notice, own data, grievances ----------

@router.get("/me/notice")
def notice(ctx: Ctx = Depends(need())):
    contact = setting(ctx.db, "grievance_contact", "admin@vayu.demo")
    return {lang: {"title": n["title"], "body": n["body"].format(contact=contact)} for lang, n in NOTICE.items()}


@router.post("/me/notice-ack")
def notice_ack(ctx: Ctx = Depends(need())):
    ctx.user.notice_ack_at = utcnow()
    return finish(ctx, "NOTICE_ACKNOWLEDGED", "Privacy notice acknowledged", message="Thank you. The notice is recorded as read.")


@router.get("/me/profile")
def profile(ctx: Ctx = Depends(need())):
    u = ctx.user
    return {"personal_data_held": {"name": u.name, "email": u.email, "role": u.role, "squadron": u.squadron_code},
            "purpose": "Maintenance accountability", "not_stored": ["phone number", "address", "health data"],
            "notice_ack_at": iso(u.notice_ack_at),
            "how_to_correct": "Raise a 'Correction' request below; the Admin will update your record."}


def _grievance(g: Grievance) -> dict:
    return {"id": g.id, "kind": g.kind, "raised_by": g.raised_by, "text": g.text, "created_at": iso(g.created_at), "status": g.status,
            "response": g.response, "responded_by": g.responded_by, "responded_at": iso(g.responded_at)}


@router.get("/grievances")
def grievances(ctx: Ctx = Depends(need())):
    q = ctx.db.query(Grievance)
    if ctx.user.role != "ADMIN":
        q = q.filter(Grievance.raised_by == ctx.user.email)  # users see only their own
    return [_grievance(g) for g in q.order_by(Grievance.id.desc())]


@router.post("/grievances")
def add_grievance(body: GrievanceIn, ctx: Ctx = Depends(need())):
    g = Grievance(kind=body.kind, raised_by=ctx.user.email, text=body.text, created_at=utcnow())
    ctx.db.add(g)
    ctx.db.flush()
    return finish(ctx, "GRIEVANCE_RAISED", f"{body.kind} request {g.id} raised", message=f"{body.kind} request {g.id} sent to the Admin.",
                  grievance=_grievance(g))


@router.post("/grievances/{gid}/respond")
def respond(gid: int, body: RespondIn, ctx: Ctx = Depends(need("ADMIN"))):
    g = ctx.db.get(Grievance, gid)
    if not g:
        fail(404, f"Request {gid} not found.")
    g.response, g.responded_by, g.responded_at, g.status = body.response, ctx.user.email, utcnow(), "Resolved"
    ctx.db.flush()
    return finish(ctx, "GRIEVANCE_RESPONDED", f"Request {g.id} from {g.raised_by} answered", message=f"Response recorded for request {g.id}.")


# ---------- DPDP: breach handling (72 hours) ----------

def _countdown(due, done):
    left = (due - utcnow()).total_seconds() / 3600
    return {"hours_left": None if done else round(left, 1), "overdue": not done and left < 0}


def _breach(b: Breach) -> dict:
    return {"id": b.id, "what_happened": b.what_happened, "impact": b.impact, "steps_taken": b.steps_taken,
            "affected_users": b.affected_users, "detected_at": iso(b.detected_at), "report_due_at": iso(b.report_due_at),
            "users_informed_at": iso(b.users_informed_at), "reported_at": iso(b.reported_at), "recorded_by": b.recorded_by,
            "report_to": "Data Protection Board of India", **_countdown(b.report_due_at, b.reported_at)}


@router.get("/breaches")
def breaches(ctx: Ctx = Depends(need("ADMIN", "AUDITOR", "CO"))):
    return [_breach(b) for b in ctx.db.query(Breach).order_by(Breach.id.desc())]


@router.get("/me/breach-notices")
def my_breach_notices(ctx: Ctx = Depends(need())):
    """Affected users are informed here."""
    rows = [b for b in ctx.db.query(Breach).order_by(Breach.id.desc()) if ctx.user.email in (b.affected_users or [])]
    return [{"id": b.id, "what_happened": b.what_happened, "impact": b.impact, "steps_taken": b.steps_taken, "detected_at": iso(b.detected_at)} for b in rows]


@router.post("/breaches")
def add_breach(body: BreachIn, ctx: Ctx = Depends(need("ADMIN"))):
    now = utcnow()
    known = {u.email for u in ctx.db.query(User)}
    unknown = [e for e in body.affected_users if e not in known]
    if unknown:
        fail(422, f"These affected users are not in the system: {', '.join(unknown)}.")
    b = Breach(what_happened=body.what_happened, impact=body.impact, steps_taken=body.steps_taken, affected_users=body.affected_users,
               detected_at=now, report_due_at=now + timedelta(hours=BREACH_HOURS), users_informed_at=now if body.affected_users else None,
               recorded_by=ctx.user.email)
    ctx.db.add(b)
    ctx.db.flush()
    return finish(ctx, "BREACH_RECORDED", f"Personal-data breach {b.id} recorded; {len(body.affected_users)} affected user(s) informed",
                  message=f"Breach {b.id} recorded. Report to the Data Protection Board within {BREACH_HOURS} hours.", breach=_breach(b))


@router.post("/breaches/{bid}/reported")
def breach_reported(bid: int, ctx: Ctx = Depends(need("ADMIN"))):
    b = ctx.db.get(Breach, bid)
    if not b:
        fail(404, f"Breach {bid} not found.")
    b.reported_at = utcnow()
    ctx.db.flush()
    return finish(ctx, "BREACH_REPORTED", f"Breach {b.id} reported to the Data Protection Board", message=f"Breach {b.id} marked as reported.")


# ---------- CERT-In: cyber incident reporting (6 hours) ----------

def _incident(i: Incident) -> dict:
    return {"id": i.id, "incident_type": i.incident_type, "description": i.description, "noticed_at": iso(i.noticed_at),
            "report_due_at": iso(i.report_due_at), "reported_at": iso(i.reported_at), "recorded_by": i.recorded_by,
            "report_to": CERTIN_EMAIL, **_countdown(i.report_due_at, i.reported_at)}


@router.get("/incidents")
def incidents(ctx: Ctx = Depends(need("ADMIN", "AUDITOR", "CO"))):
    return {"types": INCIDENT_TYPES, "report_to": CERTIN_EMAIL, "hours": CERTIN_HOURS,
            "incidents": [_incident(i) for i in ctx.db.query(Incident).order_by(Incident.id.desc())]}


@router.post("/incidents")
def add_incident(body: IncidentIn, ctx: Ctx = Depends(need("ADMIN", "CO"))):
    if body.incident_type not in INCIDENT_TYPES:
        fail(422, "Please choose an incident type from the CERT-In list.")
    now = utcnow()
    i = Incident(incident_type=body.incident_type, description=body.description, noticed_at=now,
                 report_due_at=now + timedelta(hours=CERTIN_HOURS), recorded_by=ctx.user.email)
    ctx.db.add(i)
    ctx.db.flush()
    return finish(ctx, "INCIDENT_RECORDED", f"Cyber incident {i.id} recorded: {body.incident_type}",
                  message=f"Incident {i.id} recorded. Report to CERT-In ({CERTIN_EMAIL}) within {CERTIN_HOURS} hours. "
                          "This system is offline: send the report from an approved internet-connected channel.", incident=_incident(i))


@router.post("/incidents/{iid}/reported")
def incident_reported(iid: int, ctx: Ctx = Depends(need("ADMIN"))):
    i = ctx.db.get(Incident, iid)
    if not i:
        fail(404, f"Incident {iid} not found.")
    i.reported_at = utcnow()
    ctx.db.flush()
    return finish(ctx, "INCIDENT_REPORTED", f"Incident {i.id} reported to CERT-In", message=f"Incident {i.id} marked as reported to CERT-In.")


# ---------- settings and the compliance page ----------

SETTING_KEYS = ["classification", "certin_poc_name", "certin_poc_contact", "ntp_servers", "grievance_contact", "log_retention_days"]


@router.get("/settings")
def get_settings(ctx: Ctx = Depends(need("ADMIN", "AUDITOR", "CO"))):
    return {k: setting(ctx.db, k) for k in SETTING_KEYS}


@router.put("/settings")
def put_settings(body: SettingsIn, ctx: Ctx = Depends(need("ADMIN"))):
    changes = body.model_dump(exclude_none=True)
    for k, v in changes.items():
        put_setting(ctx.db, k, v)
    ctx.db.flush()
    return finish(ctx, "SETTINGS_CHANGED", f"Settings changed: {', '.join(changes)}", message="Settings saved.")


@router.get("/compliance")
def compliance(ctx: Ctx = Depends(need("ADMIN", "CO", "AUDITOR"))):
    db = ctx.db
    cards = (settings.results_dir / "model_cards.json").exists()
    poc = bool(setting(db, "certin_poc_name"))
    oldest = db.query(SystemLog).order_by(SystemLog.ts).first()
    done, pending = "Done", "Pending"

    def item(text, status, link, how):
        return {"item": text, "status": status, "link": link, "how": how}

    groups = [
        {"group": "Airworthiness and human control", "items": [
            item("AI is advisory only", done, "/models", "No model output changes aircraft status; only PATCH /aircraft/{tail}/status by an Engineering Officer with a reason."),
            item("Two-person sign-off", done, "/defects", "The technician who did the task closes it; a different Engineering Officer signs it off."),
            item("Overhaul limit lock", done, "/overhaul", "An aircraft past an overhaul limit cannot be marked Mission-capable until the overhaul is recorded."),
            item("Model cards and versions stored with every prediction", done if cards else pending, "/models", "model_version, training date, dataset and test RMSE are saved on each prediction."),
            item("False-alarm tracking per model", done, "/models", "Every 'False alarm' decision is logged; the rate is shown on the model card."),
        ]},
        {"group": "ISO 13374 / CBM+", "items": [
            item("ISO 13374 layer mapping", done, "/compliance", "Each backend module is labelled with its block (see table below)."),
            item("Maintenance triggered by evidence of need", done, "/alerts", "RUL, sensor anomaly and recurring-defect alerts trigger maintenance."),
            item("Calendar and hour limits kept as a safety floor", done, "/overhaul", "The system never extends a manufacturer limit."),
        ]},
        {"group": "Data security", "items": [
            item("Runs offline; no external calls, fonts, analytics or CDNs", done, "/compliance", "All assets are bundled; the stack runs on docker-compose inside the base network."),
            item("Classification banner on every page and export", done, "/admin", f"Current label: {setting(db, 'classification')}"),
            item("2-step login, 15-minute session, lock after 5 failed logins", done, "/admin", "OTP for CO, ENGO, LOGO, Auditor and Admin."),
            item("Role checks on every route + row-level security by squadron", done, "/admin", "PostgreSQL RLS on aircraft, engines, alerts, defects and tasks."),
            item("Least-privilege database user", done, "/audit", "The API connects as vayu_app, which cannot drop tables or edit audit_log."),
            item("Tamper-proof audit trail", done, "/audit", "SHA-256 hash chain + trigger blocking UPDATE, DELETE and TRUNCATE."),
            item("Encryption at rest and TLS inside the network", pending, "/compliance", "Deployment step: enable disk encryption (LUKS/BitLocker), MinIO SSE and the TLS reverse proxy (see README)."),
            item("Daily encrypted backup with tested restore", pending, "/compliance", "Scripts provided (scripts/backup.sh, scripts/restore.sh); schedule them on the base server."),
        ]},
        {"group": "DPDP Act 2023", "items": [
            item("Data minimisation", done, "/privacy", "Only name, role, squadron and email are stored."),
            item("Notice in English and Hindi on first login", done, "/privacy", "Shown until acknowledged."),
            item("View own data and request correction", done, "/privacy", "Under 'My data'."),
            item("Grievance form with tracked responses", done, "/privacy", "Requests go to the Admin."),
            item("Breach workflow with 72-hour timer", done, "/compliance", "Records what happened, impact and steps; informs affected users."),
        ]},
        {"group": "CERT-In Directions 2022", "items": [
            item("Cyber incident reporting with 6-hour countdown", done, "/compliance", f"Report to {CERTIN_EMAIL}."),
            item("Logs kept for 180 days, stored on the base server (in India)", done, "/compliance",
                 f"Retention {settings.log_retention_days} days; oldest log: {iso(oldest.ts) if oldest else 'none yet'}; audit entries: {db.query(AuditLog).count()}."),
            item("Clock sync with NIC / NPL NTP servers", done if setting(db, "ntp_servers") else pending, "/admin", f"Configured: {setting(db, 'ntp_servers') or 'not set'}. The base server must run chrony/ntpd."),
            item("Named Point of Contact for CERT-In", done if poc else pending, "/admin", setting(db, "certin_poc_name") or "Not set"),
        ]},
    ]
    return {"groups": groups, "iso_13374": ISO_13374, "settings": {k: setting(db, k) for k in SETTING_KEYS},
            "summary": {"done": sum(i["status"] == done for g in groups for i in g["items"]),
                        "pending": sum(i["status"] == pending for g in groups for i in g["items"])}}
