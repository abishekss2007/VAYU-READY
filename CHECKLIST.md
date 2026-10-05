# Final check

## Update, 5 October 2026: CI/CD and cloud deployment

| Check | Result | Notes |
|---|---|---|
| GitHub Actions CI | Pass | 4 jobs: tests on SQLite, tests on PostgreSQL 16 + TimescaleDB, frontend build, config checks |
| 39 tests on PostgreSQL 16 + TimescaleDB | Pass (in CI) | First real run of `schema.sql` and `rls.sql`; the audit trigger and tamper test run against PostgreSQL |
| Row-level security as the restricted `vayu_app` role | Pass (in CI) | `backend/tests/check_rls.py`: squadron isolation, Admin sees no alerts/defects/tasks, cannot change or truncate `audit_log`, cannot drop tables, hypertable exists |
| 39 tests on Python 3.11 without PyTorch | Pass | Same environment as CI and Render |
| Cloud copy live | Pass | https://vayu-ready.vercel.app (Vercel) + https://vayu-ready-api.onrender.com (Render) + Supabase |
| Deploy workflow smoke tests | Pass | API healthy and reading the database; wrong login refused; web app up; CORS correct |
| All 16 Mermaid diagrams parse | Pass | Checked with the Mermaid library; not viewed on github.com |
| Logged in to the cloud copy and walked the demo | **Not done by me** | Verified only by the smoke tests above |

Found and fixed on the way: the seed script failed on PostgreSQL because the driver read `%` in the SQL files as a placeholder.

Still not run: the docker-compose stack end to end (only syntax-checked in CI), the MQTT live feed, MinIO, backup/restore, the TLS proxy.
The rows below are the original check from 3 October and are kept as written; where they say PostgreSQL was untested, the table above supersedes them.

Checked on 3 October 2026 on a Windows 11 laptop. Docker Desktop was installed but its engine was not running and `make` is not installed,
so everything below was run **locally: Python 3.14 virtual environment, SQLite, `next build` + `next start`**. Rows marked **Not run** still need doing on a machine with Docker.

## Run and fix

| Check | Result | Notes |
|---|---|---|
| `make train` | **Not run** in Docker. Pass locally (`python -m ml.train`) | All four model files, `metrics.json`, `report.md`, 4 charts and model cards are written |
| `docker-compose up --build` from a clean clone | **Not run** | Dockerfiles, compose file, Mosquitto config and seed service are written but untested |
| `make seed` | **Not run** in Docker. Pass locally (`python backend/seed.py`) | Prints score 71 with the 5 expected reasons |
| `make test` | **Not run** in Docker. Pass locally: **39 passed** | SQLite. PostgreSQL-only behaviour is not covered (see below) |
| Final RMSE | **18.216 cycles** (XGBoost; CNN-LSTM 19.499) | On the **synthetic FD001-like** data set: the NASA files were not in `data/cmapss/`. Not a C-MAPSS result |
| Log in as each of the 9 demo users, open every sidebar screen | Pass | No blank page, crash or error box. Checked in the browser for all 9 roles |
| Walk through DEMO.md | Pass | In the browser at 768 px: 71 → 76 → 83; optimiser 11 → 16; plan approved; chain intact |

## Specific checks

| Check | Result | Notes |
|---|---|---|
| No external network calls at runtime | Pass | Browser network log shows only `localhost:3000` and `localhost:8000`. The backend makes no outbound calls with MQTT and MinIO switched off; with them on it only talks to those containers |
| Every alert has an action button | Pass | Review alert (ENGO) or Open / Open spares / Open overhaul tracker / Open defects |
| Every number has a label | Pass | KPI cards, twin, tables |
| Every screen shows the demo banner | Pass | Banner on login and on every app screen; also on the CSV and PDF reports |
| Tablet layout at 768 px | Pass after fixes | See "What was fixed" |
| Error messages are plain English | Pass | Including validation errors, which are rewritten into one sentence |
| Audit chain intact after the demo | Pass | 27 entries verified after the browser walkthrough |
| Audit chain detects tampering | Pass (test) | `test_verify_points_to_the_exact_tampered_entry`: names entry 3. Not shown in the browser |
| Loading and empty states on every list | Pass | Every table and list has both |
| Console errors | One 403 seen | Most likely from forcing a Technician onto `/dashboard` by URL during testing (not traced to the exact request); the guard that allowed it is fixed (see below) |

## What was fixed during this check

1. A page a role cannot see was rendered for a moment before the redirect, which fired a forbidden API call. The shell now shows nothing until the role check passes.
2. At 768 px the dashboard and compliance pages scrolled sideways. Cards can now shrink, and wide tables scroll inside their own card.
3. At 768 px the sidebar took too much width, pushing the technician's "Mark done" button off screen. The sidebar now collapses to a menu button below 1024 px.
4. The aircraft health score on the twin page was shown as a small badge; it is now a large number.
5. The what-if panel mixed aircraft from both squadrons for roles that see all squadrons; it is now limited to the squadron on screen.
6. The spares "Timing" column was too narrow to read.

## Not verified yet

- **Docker stack:** image builds, service start order, the one-off seed service.
- **PostgreSQL:** `schema.sql` and `rls.sql` have not been executed. Row-level security, the `vayu_app` grants, the audit trigger on PostgreSQL and the TimescaleDB hypertable are untested. The tests exercise the same rules at the API level and an equivalent append-only trigger on SQLite.
- **MQTT live feed:** worker replay → Mosquitto → API → WebSocket has not been run end to end. The WebSocket itself connects ("Live updates on") and pushes refresh events.
- **MinIO** file storage and signed links.
- **Backup and restore scripts** and the optional TLS proxy.
- **Excel import** (`.xlsx`); CSV import is tested.
- **NASA C-MAPSS, NGAFID-MC and MaintNet:** none were present, so no result on real or NASA data exists yet.
- **Drag-and-drop** on the schedule was checked through the Earlier / Later path and the constraint-check API, not by dragging with a mouse.

## Known differences from the brief

- "Forecast with the plan is never lower than without it" holds for total mission-capable aircraft-days and for the last day of the horizon (tested). On an individual day the plan can be lower, because an aircraft in the hangar is not flying that day.
- The spoken demo line "servicing 3 aircraft this week" is approximate: the plan has 5 hangar visits, 3 of them in the first 9 days (see DEMO.md).
- `audit_log.ts` is stored as ISO-8601 text rather than a timestamp, so the hash input never changes format.
- Extra columns and tables beyond the 14 listed: `indents.tail_no` and `fitted`, task `kind` / `completed_by` / `engine_ids` / `part_no`, alert `note` and `model_version`, user lockout and notice fields, and tables for plans, settings, grievances, breaches, incidents and system logs.
- The seed stores scenario RUL values so the demo numbers are exact; the trained model is used when "Run prediction" is pressed.
- Screenshots in `docs/screenshots/` cover 11 screens; they were captured before fixes 3 and 4, so the sidebar and twin header look slightly different now.
