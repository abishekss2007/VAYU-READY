# VAYU-READY: 3-minute demo script

DEMO DATA – UNCLASSIFIED. All data is synthetic.

**Before you start**

1. Log in as `admin@vayu.demo` → **Users & Access** → **Reset demo**. The SQ7 score is now 71.
2. Turn on **Demo guide** (top right). It shows the next step of this script on screen.
3. To switch user, log out and tap the role under **Demo accounts** on the login page (password `demo123` and one-time code `482913` are filled in for you).

Keep these numbers the same in the app, the slides and your speech: **71 → 76 → 83** and **11 → 16 aircraft**.

| # | Time | Who | Do | Say |
|---|---|---|---|---|
| 1 | 30 s | Commander `co@vayu.demo` | Open **Readiness Dashboard**. Point at the score and the 5 lines. | "14 of 18 aircraft are mission-capable, but the forecast drops to 11 in 9 days. Fleet Health Score 71, and here are the 5 reasons." |
| 2 | 45 s | Engineering Officer `engo@vayu.demo` | **Aircraft Health** → open **TAIL-SQ7-114** → **Review alert** → *Schedule engine change* → **Save review**. | "Engine 2 has 18 cycles left. SHAP shows HPC outlet temperature and fan speed drift." After saving: "The review clock stops. Score 76." |
| 3 | 30 s | Logistics Officer `logo@vayu.demo` | **Spares and Indents**. Point at **IND-012** (raised by system, red). Then **Mark received** on **IND-010** (HYD-ACT-22). | "The HPC module has a 21-day lead time and zero stock. The indent was raised automatically before anyone asked." |
| 3b | 15 s | Engineering Officer | Open **TAIL-SQ7-105** → **Change status** → *Mission-capable* → reason "MLG actuator fitted and tested" → **Save status**. | "The part is in; the engineer, not the system, releases the aircraft. Score 83." |
| 4 | 45 s | Engineering Officer, then Commander | **Schedule and What-If** → **Run optimiser**. Drag one task to show the constraint check. Log in as `co@vayu.demo` → dashboard → **Approve plan**. | "Servicing 3 aircraft this week lifts 30-day availability from 11 to 16." |
| 5 | 30 s | Auditor `auditor@vayu.demo` | **Audit Trail** → **Verify chain**. Then **Model Cards** and **Compliance**. | "Every action is hash-chained. The models are advisory only. It runs offline, and here is the compliance checklist." |

## What changes at each step

| Step | Fleet Health Score | Why |
|---|---|---|
| Start | **71** | forecast availability −10 (11/18 = 61% vs 75%), critical RUL −8 (2 aircraft), AOG awaiting spares −6 (2 aircraft), unreviewed critical alert −5, overhaul breach 0 |
| ALT-031 reviewed | **76** | the −5 for the unreviewed critical alert is gone |
| HYD-ACT-22 received | 79 | AOG awaiting spares drops to −3 (the aircraft is still on the ground until the ENGO releases it) |
| TAIL-SQ7-105 released | **83** | 9-day forecast rises to 12/18 (67%), so availability becomes −6 |
| Plan approved | 89 | the planned work is now in the calendar, so the 9-day forecast is 14/18 |

Optimiser: 30-day availability **11 → 16** of 18 aircraft.

The plan the optimiser returns after step 3b has 5 hangar visits. The first three, in the first 9 days, are TAIL-SQ7-108 (day 0–2) and
TAIL-SQ7-113 (day 3–5), both engine overhauls before their hour limits, and TAIL-SQ7-109 (day 8, fuel pump fitted when it arrives).
TAIL-SQ7-103 follows on day 9–11 (engine change, RUL 23 cycles) and TAIL-SQ7-114 on day 21–23, when the HPC module arrives.
So the spoken line "3 aircraft this week" is close but not exact: say "3 aircraft in the first 9 days" if a judge is counting.
Two aircraft stay in booked depot inspections for the whole 30 days, which is why the line tops out at 16.

## If something goes wrong

- Score is not 71: log in as Admin and press **Reset demo**.
- "Your session has expired": sessions last 15 minutes; log in again.
- Account locked: 5 wrong passwords lock an account for 15 minutes; Admin → **Unlock**.
- Tamper demo (optional, needs database access): change one `detail` value in `audit_log` after disabling the trigger as the database owner, then press **Verify chain**; it points to that exact entry.
