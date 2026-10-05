# VAYU-READY architecture

DEMO DATA – UNCLASSIFIED. Five layers following ISO 13374. GitHub renders this diagram; for slides, open this page and take a screenshot.

```mermaid
flowchart TB
    subgraph SRC["Sources"]
        S1[Engine sensors]
        S2[Technical records]
        S3[Defects and tasks]
        S4[Spares stock]
        S5[Depot overhaul data]
    end
    subgraph L1["1. Data acquisition"]
        MQ[MQTT feed - Mosquitto]
        IMP[Forms and CSV / Excel import]
    end
    subgraph L2["2. Data manipulation"]
        API[FastAPI + Pydantic validation]
        DB[(PostgreSQL 16 + TimescaleDB<br/>row-level security)]
    end
    subgraph L3["3. State detection and health assessment"]
        AN[Anomaly autoencoder]
        NLP[Defect text classifier]
        TW[Digital twin and aircraft health score]
    end
    subgraph L4["4. Prognostic assessment"]
        RUL[RUL per engine + SHAP reasons]
        FC[30-day readiness forecast]
    end
    subgraph L5["5. Advisory generation"]
        AL[Alerts and 12-hour review clock]
        OPT[OR-Tools maintenance plan]
        IND[Auto-raised spares indents]
        FHS[Fleet Health Score]
    end
    OUT[Role dashboards, readiness reports, spares indents, audit reports]

    S1 --> MQ
    S2 --> IMP
    S3 --> IMP
    S4 --> IMP
    S5 --> IMP
    MQ --> API
    IMP --> API
    API --> DB
    DB --> AN
    DB --> NLP
    AN --> TW
    NLP --> TW
    DB --> RUL
    RUL --> FC
    RUL --> AL
    FC --> OPT
    FC --> FHS
    TW --> FHS
    AL --> IND
    AL --> OUT
    OPT --> OUT
    FHS --> OUT
    IND --> OUT
```

Across all layers: JWT + OTP login, role checks on every route, SHA-256 hash-chained audit trail. The AI advises; an Engineering Officer decides.

More diagrams (request path, data model, ML pipeline, optimiser, CI/CD, deployment) are in the [README](../README.md).
