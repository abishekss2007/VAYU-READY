# VAYU-READY: presentation content (SIH template)

Numbers marked **[check source]** come from the project brief. Confirm each against the cited document before presenting; they were not verified while building this repository.

## Slide 1: Title

- Problem Statement ID: **SIH26249**
- Problem Statement Title: Air Power – Predictive Maintenance & Fleet Availability (Ministry of Defence)
- Theme: Transportation & Logistics
- Team name: *(your team name)*
- Solution: **VAYU-READY**: on-premise, AI-powered predictive maintenance and fleet availability platform

## Slide 2: Idea / solution

**The problem in numbers**

- CAG: Su-30MKI serviceability about 55–60% against 75% required **[check source: CAG Report 38 of 2015]**
- Spares shortages and cannibalisation keep aircraft on the ground **[check source: CAG Report 24 of 2017]**
- Maintenance data is scattered across health-monitoring systems, technical records, spares and maintenance agencies; maintenance is reactive

**One-line pitch**

VAYU-READY predicts component failures before they ground aircraft, joins maintenance data into one record per aircraft, plans the maintenance, and raises spares indents early.

**4 AI modules**

1. RUL prediction per engine, with the top 3 sensor reasons (SHAP)
2. Anomaly detection that fires before RUL drops
3. Defect text classifier for free-text technician entries
4. Maintenance optimiser (OR-Tools CP-SAT) with a what-if simulator

**What a Commander sees:** Fleet Health Score 71/100 with the reason for every lost point; 14 of 18 mission-capable today, 11 in 9 days without action.

## Slide 3: Technical approach

- Architecture diagram: `docs/architecture.md` (Mermaid, 5 layers following ISO 13374; screenshot it for the slide)
  1. Data acquisition → 2. Data manipulation → 3. State detection and health assessment → 4. Prognostic assessment → 5. Advisory generation
- Tech stack
  - Frontend: Next.js 14, React, TypeScript, Tailwind CSS, shadcn/ui-style components, Recharts
  - Backend: Python 3.11, FastAPI, Pydantic, SQLAlchemy 2.0
  - Database: PostgreSQL 16 + TimescaleDB, row-level security
  - ML: scikit-learn, XGBoost, PyTorch, SHAP
  - Optimiser: Google OR-Tools (CP-SAT)
  - Streaming: MQTT (Eclipse Mosquitto); files: MinIO; jobs: APScheduler
  - Deployment: Docker + docker-compose, fully offline
- Datasets: NASA C-MAPSS FD001 (engine run-to-failure, simulated); NGAFID-MC (real general-aviation flights, optional); MaintNet (aviation logbook text, optional)

## Slide 4: Feasibility and viability

**Achieved accuracy:** take the numbers from `results/metrics.json` after `make train`.

- RUL test RMSE: `rul.best_rmse` cycles (model: `rul.best`), NASA score `rul.<best>.nasa_score`
- Anomaly flag fires `anomaly.mean_cycles_earlier_than_rul_alert` cycles before the RUL alert
- Defect classifier accuracy: `defect.cv_accuracy`
- State the data set shown in `dataset`. If it reads "SYNTHETIC FD001-like", the NASA files were missing and the figure must not be presented as a C-MAPSS result.

**Risks and mitigations**

| Risk | Mitigation |
|---|---|
| No service data yet | Data-agnostic pipeline; retrain on-premise with `make train` |
| Model is wrong | Advisory only, human sign-off, false-alarm tracking, safety margin, hard hour limits |
| Data quality | Validation on every input; bulk import rejects bad rows with a clear message |
| Insider tampering | Hash-chained audit trail, database trigger, least-privilege database user |
| Adoption on the flight line | Tablet layout, free-text defect entry, one question per screen |

**Phased plan**

1. Pilot: one squadron, read-only shadow mode alongside current practice
2. Retrain on service data; Engineering Officer review of every alert; measure false-alarm rate
3. Add spares and depot (BRD) integration; extend to more squadrons and aircraft types
4. Air HQ portfolio view across bases

## Slide 5: Impact and benefits

- Fewer AOG days: failures are predicted and fixed in planned slots
- Spares ordered ahead: indents are raised automatically when a predicted failure needs a part that is short
- Faster decisions: a Commander understands readiness in 10 seconds; an Engineering Officer goes from alert to scheduled fix in 3 clicks
- Demo result: 30-day availability 11 → 16 of 18 aircraft with the recommended plan (synthetic demo scenario)
- Benchmark: USAF PANDA: 51% fewer unscheduled maintenance man-hours on monitored B-1 systems; up to 25% potential availability gain **[check source]**
- Accountability: every action is recorded in a tamper-proof audit trail

## Slide 6: Research and references

- CAG Report No. 38 of 2015 and Report No. 24 of 2017
- DoD Instruction 4151.22, Condition-Based Maintenance Plus (CBM+)
- ISO 13374 (condition monitoring and diagnostics: data processing, communication and presentation) / OSA-CBM
- NASA C-MAPSS turbofan engine degradation simulation data set
- NGAFID-MC (National General Aviation Flight Information Database, maintenance classification)
- MaintNet (aviation maintenance logbook data sets)
- CERT-In Directions of 28 April 2022
- Digital Personal Data Protection Act, 2023

## Demo numbers to keep consistent

Fleet Health Score **71 → 76 → 83**; 30-day availability **11 → 16** aircraft.
