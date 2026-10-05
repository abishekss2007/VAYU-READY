# VAYU-READY

**DEMO DATA – UNCLASSIFIED.** Synthetic squadron data only: no real aircraft, units or people.

On-premise, AI-powered predictive maintenance and fleet availability platform for an air force squadron.
Smart India Hackathon 2026, problem statement **SIH26249** (Air Power – Predictive Maintenance & Fleet Availability, Ministry of Defence).

It predicts component failures before they ground aircraft, joins scattered maintenance data into one record per aircraft, plans maintenance, and raises spares indents early.

- A Commander understands squadron readiness in 10 seconds.
- An Engineering Officer goes from alert to scheduled fix in 3 clicks.
- The AI advises; an authorised engineer decides.

## What is in this repository

| Folder | What |
|---|---|
| `frontend/` | Next.js 14 (App Router) + React + TypeScript + Tailwind + Recharts |
| `backend/app/` | FastAPI + Pydantic + SQLAlchemy 2.0: routers, digital twin, Fleet Health Score, jobs, live feed |
| `backend/optimiser/` | Google OR-Tools CP-SAT scheduler (`plan.py`) and readiness forecast (`forecast.py`) |
| `backend/sql/` | `schema.sql` (TimescaleDB hypertable) and `rls.sql` (row-level security, audit trigger, least-privilege role) |
| `backend/seed.py` | Synthetic demo data: 2 squadrons, 30 aircraft, 60 engines |
| `backend/tests/` | pytest suite (39 tests) |
| `ml/` | `train.py`, `evaluate.py`, `infer.py`: RUL, anomaly, defect classifier |
| `models/`, `results/` | Trained models, `metrics.json`, `report.md`, charts, model cards |
| `docs/` | Architecture diagram and screenshots |
| `DEMO.md`, `PPT_CONTENT.md`, `QA.md`, `CHECKLIST.md` | Demo script, slide content, judge Q&A, final check |

## Setup, step by step (offline deployment)

You need Docker with docker-compose. Internet is needed only to build the images.

1. **Get the NASA data (recommended).** Download C-MAPSS and put `train_FD001.txt`, `test_FD001.txt` and `RUL_FD001.txt` in `data/cmapss/`.
   If they are missing, a synthetic FD001-like data set is used and every result is labelled "SYNTHETIC".
2. **Create `.env`:** copy `.env.example` to `.env` and change the secrets.
3. **Build:** `make setup`
4. **Train the models once:** `make train` (saved in `models/`, which is mounted into the api container)
5. **Start everything:** `make up` (same as `docker-compose up --build`)
   - Web app: http://localhost:3000
   - API docs: http://localhost:8000/docs
   - The demo data is loaded automatically the first time.
6. **Reload the demo data any time:** `make seed`, or log in as Admin and press **Reset demo**.
7. **Run the tests:** `make test`

Services: `db` (TimescaleDB), `mqtt` (Mosquitto), `minio`, `seed` (one-off), `api` (FastAPI), `worker` (APScheduler + MQTT replay), `web` (Next.js).

No `make` (for example on Windows)? Use the commands directly:

```bash
docker-compose build
docker-compose run --rm --no-deps --user 0 api python -m ml.train
docker-compose up --build
docker-compose run --rm api python seed.py
docker-compose run --rm --no-deps api python -m pytest -q
```

### Quick local run without Docker

For a fast look or for development. Uses SQLite, so PostgreSQL row-level security, TimescaleDB, MQTT and MinIO are not active
(role checks and squadron filters in the API still are).

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements.txt torch
.venv/Scripts/python -m ml.train
.venv/Scripts/python run_local.py --reseed
```

```bash
npm --prefix frontend install
npm --prefix frontend run build
npm --prefix frontend run start
```

```bash
.venv/Scripts/python -m pytest -q
```

## Demo logins (all 9 roles)

**Easiest way in:** the login page lists all 9 demo accounts. Tap a role and you are logged in; for 2-step roles the code is already filled in, so just press **Verify code**.
This demo panel shows the password and code on screen, so build the web app with `NEXT_PUBLIC_DEMO_MODE=off` for any real deployment.

Every user has the password **`demo123`**. Roles marked 2-step also need the one-time code **`482913`**.

| Role | Email | 2-step | Lands on | Sees |
|---|---|---|---|---|
| Squadron Commander (CO) | co@vayu.demo | yes | Readiness Dashboard | SQ7 readiness, forecast; approves the maintenance plan |
| Engineering Officer (ENGO) | engo@vayu.demo | yes | Aircraft Health | SQ7 aircraft, alerts, schedule; reviews critical alerts, changes aircraft status |
| Technician (TECH) | tech@vayu.demo | no | My tasks | SQ7 tasks; logs defects and completed work |
| Logistics Officer (LOGO) | logo@vayu.demo | yes | Spares | Stock, demand, indents; approves and receives indents |
| BRD Planner (BRD) | brd@vayu.demo | no | Overhaul Tracker | Engine overhauls across squadrons |
| Flight Safety Officer (FSO) | fso@vayu.demo | no | Readiness Dashboard | Read-only: trends, recurring defects, overhaul limits |
| Admin (ADMIN) | admin@vayu.demo | yes | Users & Access | Users, bases, aircraft records only; no maintenance decisions |
| Auditor (AUDITOR) | auditor@vayu.demo | yes | Audit Trail | Read-only: audit trail and chain verification |
| Air HQ Leadership (HQ) | hq@vayu.demo | no | Portfolio | All squadrons and bases |

## 3-minute demo

Full script with what to say: [DEMO.md](DEMO.md). In short:

1. **Commander:** score 71; 14/18 mission-capable, 11/18 in 9 days.
2. **Engineering Officer:** open TAIL-SQ7-114, review alert ALT-031 → score **76**.
3. **Logistics:** IND-012 was raised automatically; receive HYD-ACT-22. ENGO releases TAIL-SQ7-105 → score **83**.
4. **Optimiser:** run it; Commander approves. 30-day availability **11 → 16**.
5. **Auditor:** Verify chain; show Model Cards and Compliance.

## How the numbers are worked out

**Fleet Health Score** = 100 minus:

| Rule | Points |
|---|---|
| Forecast availability in 9 days against the 75% target | 1 per 1.4% shortfall, rounded, max 20 |
| Aircraft with a critical RUL alert (under 25 cycles) | 4 each, max 16 |
| Aircraft on ground awaiting spares | 3 each, max 12 |
| Any critical alert not reviewed by an Engineering Officer within 12 hours | 5 flat |
| Any aircraft past its overhaul limit (safety flag) | 10 each |

**Aircraft health** = 100 × lowest engine RUL / 125, minus 10 if the anomaly flag is on, minus 5 per open defect (never below 0).

**Forecast:** an aircraft is down while a hangar task covers the day; an aircraft not mission-capable today stays down until its task finishes;
a predicted failure grounds it on day `RUL / 1.2 sorties per day`; an overhaul limit grounds it on day `hours left / 2.0 flying hours per day`.
The plan keeps a 3-day safety margin. These constants are in `backend/app/config.py`.

**Demo predictions:** the seed script stores each engine's true RUL at its replay point (labelled `scenario-seed`), so the demo numbers are exact.
**Run prediction** on an engine calls the trained model on the last 30 sensor cycles and stores the real model output; that can move the score.

## Model results

Read `results/report.md` after training. The models in this folder were trained on **the synthetic FD001-like stand-in**, because the NASA files were not present:

| Model | Result |
|---|---|
| RUL (XGBoost, used by the API) | test RMSE 18.2 cycles, NASA score 828 |
| RUL (CNN-LSTM) | test RMSE 19.5 cycles |
| Anomaly autoencoder | flag fires about 53 cycles before the RUL<25 alert |
| Defect classifier | 96.5% cross-validated accuracy on 200 template-generated sentences |
| NGAFID-MC classifier | not trained (data not present) |

These are not NASA C-MAPSS results. Put the NASA files in `data/cmapss/` and run `make train` to get the real figures before presenting them.

## Security

- bcrypt passwords, JWT sessions that expire after 15 minutes, 2-step OTP for CO, ENGO, LOGO, Auditor and Admin, lock after 5 failed logins
- Role check on every API route (`Your role (X) cannot do this`), plus PostgreSQL row-level security by squadron on aircraft, engines, alerts, defects and tasks
- The API connects as the restricted role `vayu_app`, which cannot drop tables or change `audit_log`
- Audit trail: append-only, SHA-256 hash chain, trigger blocks UPDATE, DELETE and TRUNCATE; **Verify chain** names the exact tampered entry
- Security headers, CORS allow-list, private MinIO bucket with signed links
- No external API calls, fonts, analytics or CDNs at runtime
- Every screen and export carries the classification banner (configurable in Admin settings or `CLASSIFICATION_LABEL`)

## Compliance

The **Compliance** page (Admin, CO, Auditor) shows a checklist with Done / Pending for each item and a link to the feature.

| Area | What the system does |
|---|---|
| Airworthiness | AI is advisory only; status changes need an ENGO and a reason; two-person sign-off; overhaul-limit lock; model cards; false-alarm rate per model |
| ISO 13374 / CBM+ | Each backend module is labelled with its block; maintenance is triggered by evidence of need; hour limits stay as a safety floor |
| Data security | Offline, classification banner, RBAC + RLS, least-privilege database user, hash-chained audit |
| DPDP Act 2023 | Only name, role, squadron and email are stored; notice in English and Hindi on first login; view own data; correction and grievance requests with tracked responses; breach workflow with a 72-hour timer |
| CERT-In Directions 2022 | Cyber incident workflow with a 6-hour timer and the incident types from the Directions; logs kept 180 days on the base server; NTP servers and a named Point of Contact in Admin settings |

**To do on the base server before real use** (shown as Pending on the Compliance page):

- Encryption at rest: full-disk encryption (LUKS or BitLocker) for the Docker volumes; enable MinIO server-side encryption.
- TLS inside the network: `docker-compose -f docker-compose.yml -f docker-compose.tls.yml up --build` (Caddy with an internal CA, or certificates from the base PKI).
- Daily encrypted backup: schedule `scripts/backup.sh`; run a restore drill with `scripts/restore.sh`. These scripts were written but not run during the build.
- Clock sync: run chrony or ntpd on the server against the NIC / NPL servers listed in Admin settings.
- Replace the fixed demo OTP with a real OTP provider on the base network.

## Environment variables

`DATABASE_URL`, `OWNER_DATABASE_URL`, `APP_DB_PASSWORD`, `JWT_SECRET`, `OTP_DEMO_CODE`, `CORS_ORIGINS`, `MQTT_URL`, `MODEL_DIR`, `NEXT_PUBLIC_API_URL`,
`MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `CLASSIFICATION_LABEL`. See `.env.example`.

## Optional cloud copy (for judges to try)

- Database: Supabase (Mumbai region). Run `python backend/seed.py` once with `OWNER_DATABASE_URL` set to the Supabase owner connection. If TimescaleDB is not available there, `sensor_readings` stays a normal table.
- Backend: Render (Docker, `backend/Dockerfile`, build context = repository root). Leave `MQTT_URL` and `MINIO_ENDPOINT` empty to switch off the live feed and file storage.
- Frontend: Vercel (root directory `frontend`, `NEXT_PUBLIC_API_URL` = the Render URL). Add the Vercel URL to `CORS_ORIGINS`.

## What has and has not been verified

See [CHECKLIST.md](CHECKLIST.md). In short: the tests, the local run and the browser walkthrough were done on SQLite without Docker.
The docker-compose stack, PostgreSQL row-level security, the TimescaleDB hypertable, the MQTT live feed and MinIO have not been run yet.
