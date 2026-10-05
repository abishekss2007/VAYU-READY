"""VAYU-READY API. Runs fully offline: no external calls, no telemetry."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .db import system_session, utcnow
from .live import hub, start_subscriber
from .models import SystemLog
from .routers import admin, auth, compliance, fleet, ops, schedule
from .security import decode_token

log = logging.getLogger("vayu")


@asynccontextmanager
async def lifespan(app: FastAPI):
    hub.loop = asyncio.get_running_loop()
    if settings.auto_seed:
        from sqlalchemy import inspect

        from .db import owner_engine
        if not inspect(owner_engine).has_table("users"):
            import seed
            log.warning("AUTO_SEED=1 and the database is empty: loading the synthetic demo data")
            seed.run(quiet=True)
    client = start_subscriber()  # MQTT -> WebSocket bridge (skipped when MQTT_URL is empty)
    yield
    if client:
        client.loop_stop()


app = FastAPI(title="VAYU-READY API", version="1.0.0", lifespan=lifespan,
              description="Predictive maintenance and fleet availability (SIH26249). DEMO DATA – UNCLASSIFIED.")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                   allow_methods=["GET", "POST", "PATCH", "PUT"], allow_headers=["Authorization", "Content-Type"])

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store", "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=()",
}


@app.middleware("http")
async def headers_and_log(request: Request, call_next):
    response = await call_next(request)
    for k, v in SECURITY_HEADERS.items():
        response.headers.setdefault(k, v)
    if request.method != "GET" and request.url.path != "/demo/reset":
        try:  # system log (kept 180 days); never contains request bodies
            db = system_session()
            db.add(SystemLog(ts=utcnow(), level="INFO" if response.status_code < 400 else "WARN",
                             message=f"{request.method} {request.url.path} -> {response.status_code}"))
            db.commit()
            db.close()
        except Exception as e:
            log.warning("could not write system log: %s", e)
    return response


@app.exception_handler(RequestValidationError)
async def plain_validation_errors(request: Request, exc: RequestValidationError):
    """Turn validation errors into one plain-English sentence."""
    parts = []
    for e in exc.errors():
        field = " ".join(str(x) for x in e["loc"] if x not in ("body", "query", "path")) or "input"
        parts.append(f"{field.replace('_', ' ')}: {e['msg'].replace('String', 'text').replace('Input', 'value')}")
    return JSONResponse(status_code=422, content={"detail": "Please check the form. " + "; ".join(parts) + "."})


for r in (auth, fleet, ops, schedule, admin, compliance):
    app.include_router(r.router)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "time": utcnow().isoformat() + "Z"}


@app.websocket("/ws/live")
async def ws_live(ws: WebSocket, token: str = ""):
    """Pushes twin updates to dashboards. The token is the same JWT used for the API."""
    try:
        data = decode_token(token)
        if data.get("stage") != "full":
            raise ValueError
    except Exception:
        await ws.close(code=4401)
        return
    await ws.accept()
    hub.clients.add(ws)
    try:
        while True:
            await ws.receive_text()  # keep-alive pings from the browser
    except WebSocketDisconnect:
        pass
    finally:
        hub.clients.discard(ws)
