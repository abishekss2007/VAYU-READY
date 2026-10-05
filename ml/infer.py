"""Inference used by the API.  ISO 13374 blocks: State Detection (anomaly), Prognostic Assessment (RUL).

All outputs are ADVISORY. Nothing here changes an aircraft's status.
"""
import json
from functools import lru_cache

import numpy as np
import pandas as pd

from . import common as c
from .defect_data import expand

try:
    import torch
    from .nets import AutoEncoder, CnnLstm, recon_error
except Exception:
    torch = None

_KEYWORDS = {  # fallback when the trained defect classifier is missing
    "Hydraulics": ["hydraulic"], "Landing gear": ["landing gear", "wheel", "tyre", "brake", "strut"],
    "Fuel": ["fuel"], "Engine": ["engine", "exhaust", "compressor", "turbine", "oil"],
    "Electrical": ["generator", "battery", "circuit", "wiring", "light", "bus"],
    "Environmental control": ["environmental", "cooling", "cabin", "cockpit", "oxygen", "duct"],
    "Avionics": ["radar", "navigation", "communication", "display", "computer", "gps", "autopilot"],
    "Airframe": ["crack", "corrosion", "rivet", "canopy", "skin", "panel", "dent"],
}


@lru_cache(maxsize=1)
def _load():
    import joblib
    b = {"metrics": {}}
    mp = c.RESULTS_DIR / "metrics.json"
    if mp.exists():
        b["metrics"] = json.loads(mp.read_text())
    if (c.MODEL_DIR / "rul_xgb.joblib").exists():
        b["xgb"] = joblib.load(c.MODEL_DIR / "rul_xgb.joblib")
    if torch and (c.MODEL_DIR / "rul_cnnlstm.pt").exists():
        ck = torch.load(c.MODEL_DIR / "rul_cnnlstm.pt", weights_only=False)
        net = CnnLstm(ck["n_feat"])
        net.load_state_dict(ck["state"])
        net.eval()
        b["cnn"] = {**ck, "model": net}
    if torch and (c.MODEL_DIR / "anomaly.pt").exists():
        ck = torch.load(c.MODEL_DIR / "anomaly.pt", weights_only=False)
        ae = AutoEncoder(ck["n_feat"])
        ae.load_state_dict(ck["state"])
        ae.eval()
        b["anomaly"] = {**ck, "model": ae}
    elif (c.MODEL_DIR / "anomaly.joblib").exists():
        b["anomaly"] = joblib.load(c.MODEL_DIR / "anomaly.joblib")
    if (c.MODEL_DIR / "defect_clf.joblib").exists():
        b["defect"] = joblib.load(c.MODEL_DIR / "defect_clf.joblib")
    return b


def reload():
    _load.cache_clear()


def available() -> bool:
    return "xgb" in _load()


def metrics() -> dict:
    return _load()["metrics"]


def _contributions(xgb_model, row: pd.DataFrame) -> np.ndarray:
    """SHAP values for one row (TreeSHAP). Falls back to XGBoost's built-in TreeSHAP if the shap package fails."""
    try:
        import shap
        return np.asarray(shap.TreeExplainer(xgb_model).shap_values(row))[0]
    except Exception:
        import xgboost as xgb
        return xgb_model.get_booster().predict(xgb.DMatrix(row), pred_contribs=True)[0][:-1]


def shap_top3(xgb_model, row: pd.DataFrame) -> list[dict]:
    contrib = _contributions(xgb_model, row)
    per_sensor = {}
    for name, v in zip(row.columns, contrib):
        per_sensor[name.split("_")[0]] = per_sensor.get(name.split("_")[0], 0.0) + float(v)
    top = sorted(per_sensor.items(), key=lambda kv: abs(kv[1]), reverse=True)[:3]
    out = []
    for s, impact in top:
        slope = float(row[f"{s}_slope"].iloc[0])
        direction = "rising" if slope > 1e-5 else "falling" if slope < -1e-5 else "steady"
        out.append({"sensor": s, "name": c.SENSOR_NAMES[s], "direction": direction, "impact_cycles": round(impact, 1),
                    "text": f"{c.SENSOR_NAMES[s]} {direction}"})
    return out


def anomaly_scores(X_scaled: np.ndarray) -> np.ndarray:
    b = _load().get("anomaly")
    if b is None:
        return np.zeros(len(X_scaled))
    err = recon_error(b["model"], X_scaled) if b["kind"] == "autoencoder" else -b["model"].score_samples(X_scaled)
    return np.clip(err / (2 * b["threshold"]), 0, 1)


def predict(window: pd.DataFrame) -> dict:
    """window: one engine's recent sensor rows (s1..s21), oldest first. Uses the last 30 cycles.

    Returns RUL in cycles (0-125), anomaly score (0-1), the top 3 SHAP reasons and model governance fields.
    """
    b = _load()
    if "xgb" not in b:
        raise RuntimeError("RUL model not found. Train the models first (make train).")
    if len(window) < 2:
        raise ValueError("At least 2 sensor cycles are needed for a prediction.")
    df = window.tail(c.WINDOW).reset_index(drop=True).assign(unit=1)
    scaler = b["xgb"]["scaler"]
    row = c.rolling_features(df, scaler).tail(1)
    rul = float(b["xgb"]["model"].predict(row)[0])
    used = b["xgb"]
    best = b["metrics"].get("rul", {}).get("best", "xgb")
    if best == "cnnlstm" and "cnn" in b:
        with torch.no_grad():
            rul = float(b["cnn"]["model"](torch.as_tensor(c.windows(df, scaler)[-1:]))[0]) * c.RUL_CAP
        used = b["cnn"]
    scores = anomaly_scores(c.scale(df, scaler).values)
    score = float(np.mean(scores[-5:]))  # 5-cycle average
    return {
        "rul_cycles": round(float(np.clip(rul, 0, c.RUL_CAP)), 1),
        "anomaly_score": round(score, 3), "anomaly_flag": score >= 0.5,
        "shap_top3": shap_top3(b["xgb"]["model"], row),  # explanation always comes from the XGBoost model
        "model_version": used["version"], "trained_on": used["trained_on"], "dataset": used["dataset"],
        "test_rmse": used["metrics"]["rmse"],
    }


def classify_defect(text: str) -> dict:
    """Suggest a defect category. The technician confirms or corrects it."""
    b = _load().get("defect")
    if b is None:
        t = expand(text)
        hits = [cat for cat, words in _KEYWORDS.items() if any(w in t for w in words)]
        return {"category": hits[0] if hits else "Airframe", "related": hits[1] if len(hits) > 1 else None,
                "confidence": None, "model_version": "keyword-fallback"}
    proba = b["model"].predict_proba([text])[0]
    order = np.argsort(proba)[::-1]
    classes = b["model"].classes_
    second = classes[order[1]] if proba[order[1]] >= 0.15 else None
    if second is None:  # e.g. a hydraulic leak at a landing-gear actuator touches two systems
        t = expand(text)
        second = next((cat for cat, words in _KEYWORDS.items() if cat != classes[order[0]] and any(w in t for w in words)), None)
    return {"category": str(classes[order[0]]), "related": str(second) if second else None,
            "confidence": round(float(proba[order[0]]), 3), "model_version": b["version"]}
