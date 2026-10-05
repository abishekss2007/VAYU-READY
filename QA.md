# Judge Q&A

Short answers first, then the evidence you can show on screen.

## "You have no real IAF data. How do we know it works?"

- The pipeline is validated on public benchmarks: NASA C-MAPSS FD001 for RUL and anomaly detection; NGAFID-MC (real general-aviation flights) and MaintNet (real logbook text) are supported as optional data sets.
- It is data-agnostic: the same `make train` retrains on service data, on-premise, with no data leaving the base.
- Be exact about what was run: see `results/report.md`. If it says "SYNTHETIC FD001-like", the NASA files were not in `data/cmapss/` when the models were trained and the RMSE is for the synthetic stand-in, not for NASA data. Put the NASA files in place and run `make train` before quoting an RMSE to judges.
- Show: **Model Cards** ("trained on simulated NASA data; must be retrained on service data before real use").

## "What if the model is wrong?"

- It is advisory only. No model output can change an aircraft's status; only an Engineering Officer can, with a reason.
- Every critical action needs a human sign-off (two-person rule on tasks).
- Every "False alarm" decision is logged and the false-alarm rate per model is shown on its model card.
- Late predictions are penalised more than early ones (NASA asymmetric score), and the planner keeps a 3-day safety margin.
- Calendar and hour limits stay as a safety floor: the system never extends a manufacturer limit.
- Show: **Review alert** dialog, **Compliance → Airworthiness and human control**.

## "Does it work for different aircraft types?"

- One model per subsystem family (engine type), on a shared data layer keyed by tail number.
- A new type means new sensor mappings and a retrain; screens, scheduler, spares and audit stay the same.

## "How secure is it?"

- Air-gapped: no external API calls, fonts, analytics or CDNs at runtime.
- Role-based access on every API route plus PostgreSQL row-level security by squadron; the API connects as a restricted database user.
- bcrypt passwords, 15-minute JWT sessions, 2-step OTP for sensitive roles, lock after 5 failed logins.
- Hash-chained, append-only audit trail with a database trigger that blocks UPDATE, DELETE and TRUNCATE.
- CERT-In incident workflow (6-hour clock), DPDP breach workflow (72-hour clock), 180-day log retention.
- Be exact: encryption at rest and TLS are deployment steps on the base server (shown as Pending on the Compliance page; `docker-compose.tls.yml` and the backup scripts are provided).
- Show: **Audit Trail → Verify chain**, **Compliance**.

## "How is this different from scheduled maintenance?"

- Condition-based (CBM+): maintenance is triggered by evidence of need: sensor trend, RUL, recurring defect.
- Calendar and hour limits are kept as a hard safety floor.
- The optimiser then places that work where it costs the fewest mission-capable aircraft-days, within hangar slots, technician hours and part arrival dates.

## "Why should we trust the Fleet Health Score?"

- It is 5 plain rules, not a black box. Every lost point is listed with its reason and a link to the fix.
- Same inputs always give the same score; the tests pin 71 → 76 → 83 for the demo data.

## "What happens when a part cannot arrive in time?"

- The plan says so: TAIL-SQ7-114's HPC module arrives on day 21 but the safe date is day 12, so the plan shows "stand-down from day 12" instead of pretending.
- The what-if simulator shows the gain from expediting that part.

## "What is not done yet?"

- Real OTP delivery (the demo uses a fixed code from `OTP_DEMO_CODE`).
- Encryption at rest, TLS certificates from the base PKI and the scheduled backup job are configured at deployment.
- Models must be retrained and approved on service data before any real use.
