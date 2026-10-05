"""Evaluate the saved models on the official test split and write results/report.md, charts and model cards.

Run:  python -m ml.evaluate
"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from . import common as c
from . import infer

LIMITS = "Trained on simulated NASA data; must be retrained on service data before real use. Advisory only."


def _predict_all(df, b):
    """RUL for every row of df using the model the API uses."""
    scaler = b["xgb"]["scaler"]
    if b["metrics"]["rul"]["best"] == "cnnlstm" and "cnn" in b:
        import torch
        with torch.no_grad():
            W = torch.as_tensor(c.windows(df, scaler))
            p = np.concatenate([b["cnn"]["model"](W[i:i + 4096]).numpy() for i in range(0, len(W), 4096)]) * c.RUL_CAP
    else:
        p = b["xgb"]["model"].predict(c.rolling_features(df, scaler))
    return np.clip(p, 0, c.RUL_CAP)


def model_cards(m):
    best = m["rul"]["best"]
    rul = m["rul"][best]
    return [
        {"name": "RUL prediction", "version": rul["version"],
         "purpose": "Estimates remaining useful life (in cycles, capped at 125) for each engine from the last 30 cycles of sensor data.",
         "data": m["dataset"], "trained_on": m["trained_on"],
         "metrics": {"Test RMSE (cycles)": rul["rmse"], "NASA score": rul["nasa_score"],
                     "Mean lead time of first RUL<25 alert (cycles)": rul.get("mean_lead_time_cycles"),
                     "Models compared": {k: v.get("rmse", v.get("skipped")) for k, v in m["rul"].items() if isinstance(v, dict)}},
         "limits": LIMITS, "approved_by": "Demo Chief Engineering Officer (fictional)", "alert_kind": "RUL"},
        {"name": "Anomaly detection", "version": m["anomaly"]["version"],
         "purpose": "Flags unusual sensor patterns before RUL drops. Score 0-1; flag at 0.5 (99th percentile of healthy data).",
         "data": m["dataset"] + " - first 30% of each training engine's life (assumed healthy)", "trained_on": m["trained_on"],
         "metrics": {"Type": m["anomaly"]["type"],
                     "Cycles left when the flag first fires (mean)": m["anomaly"]["mean_cycles_left_at_first_flag"],
                     "Cycles earlier than the RUL alert (mean)": m["anomaly"]["mean_cycles_earlier_than_rul_alert"]},
         "limits": LIMITS, "approved_by": "Demo Chief Engineering Officer (fictional)", "alert_kind": "ANOMALY"},
        {"name": "Defect text classifier", "version": m["defect"]["version"],
         "purpose": "Suggests a defect category from a technician's free-text entry. The technician confirms or corrects it.",
         "data": m["defect"]["data"], "trained_on": m["trained_on"],
         "metrics": {"Cross-validated accuracy": m["defect"]["cv_accuracy"], "Samples": m["defect"]["samples"]},
         "limits": m["defect"]["note"] + " A suggestion only; never used to decide airworthiness.",
         "approved_by": "Demo Chief Engineering Officer (fictional)", "alert_kind": None},
        {"name": "Maintenance-need classifier (optional)", "version": "ngafid" if "accuracy" in m["ngafid"] else "not trained",
         "purpose": "Classifies a real general-aviation flight as before or after maintenance, to show the method works on real flight data.",
         "data": "NGAFID-MC", "trained_on": m["trained_on"] if "accuracy" in m["ngafid"] else None,
         "metrics": m["ngafid"], "limits": "General-aviation data, not military aircraft. Not used by the application.",
         "approved_by": None, "alert_kind": None},
    ]


def main():
    infer.reload()
    b = infer._load()
    m = b["metrics"]
    out = c.RESULTS_DIR
    train, test, true_rul, _ = c.load_fd001(quiet=True)
    train = c.add_rul(train)
    true = np.minimum(true_rul, c.RUL_CAP)

    # 1. predicted vs true RUL on the test set (last cycle of each engine)
    last = test.groupby("unit").tail(1).index.values
    pred = _predict_all(test, b)[last]
    plt.figure(figsize=(5, 5))
    plt.scatter(true, pred, s=14, color="#0ea5e9")
    plt.plot([0, 125], [0, 125], color="#16a34a")
    plt.xlabel("True RUL (cycles)"); plt.ylabel("Predicted RUL (cycles)")
    plt.title(f"Test set: RMSE {c.rmse(pred, true):.2f} cycles")
    plt.tight_layout(); plt.savefig(out / "pred_vs_true.png", dpi=110); plt.close()

    # 2. RUL curve for 3 training engines, 3. anomaly score over time
    units = sorted(train["unit"].unique())[:3]
    sub = train[train["unit"].isin(units)].reset_index(drop=True)
    sub_pred = _predict_all(sub, b)
    sub_anom = infer.anomaly_scores(c.scale(sub, b["xgb"]["scaler"]).values)
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.6))
    fig2, ax2 = plt.subplots(1, 3, figsize=(13, 3.2))
    for i, u in enumerate(units):
        g = (sub["unit"] == u).values
        ax[i].plot(sub["cycle"][g], sub["rul"][g], color="#16a34a", label="True (capped at 125)")
        ax[i].plot(sub["cycle"][g], sub_pred[g], color="#0ea5e9", label="Predicted")
        ax[i].axhline(c.ALERT_RUL, color="#dc2626", ls="--", lw=1)
        ax[i].set_title(f"Engine {u}"); ax[i].set_xlabel("Cycle"); ax[i].set_ylabel("RUL (cycles)")
        ax2[i].plot(sub["cycle"][g], sub_anom[g], color="#f59e0b")
        ax2[i].axhline(0.5, color="#dc2626", ls="--", lw=1)
        ax2[i].set_title(f"Engine {u}"); ax2[i].set_xlabel("Cycle"); ax2[i].set_ylabel("Anomaly score (0-1)")
    ax[0].legend(fontsize=8)
    fig.tight_layout(); fig.savefig(out / "rul_curves.png", dpi=110); plt.close(fig)
    fig2.tight_layout(); fig2.savefig(out / "anomaly_score.png", dpi=110); plt.close(fig2)

    # 4. confusion matrix of the defect classifier
    cm, labels = np.array(m["defect"]["confusion_matrix"]), m["defect"]["labels"]
    plt.figure(figsize=(6.5, 5.5))
    plt.imshow(cm, cmap="Blues")
    plt.xticks(range(len(labels)), labels, rotation=45, ha="right"); plt.yticks(range(len(labels)), labels)
    for i in range(len(labels)):
        for j in range(len(labels)):
            plt.text(j, i, cm[i, j], ha="center", va="center", fontsize=8)
    plt.xlabel("Predicted"); plt.ylabel("True"); plt.title("Defect classifier (5-fold CV)")
    plt.tight_layout(); plt.savefig(out / "confusion_matrix.png", dpi=110); plt.close()

    cards = model_cards(m)
    (out / "model_cards.json").write_text(json.dumps(cards, indent=2))

    r = m["rul"]
    lines = [
        "# VAYU-READY model results", "",
        f"- Dataset: **{m['dataset']}**", f"- Trained on: {m['trained_on']} (random seed {m['seed']})",
        f"- Features: {len(m['features'])} sensors (constant sensors dropped: {', '.join(m['dropped_constant_sensors'])}); the cycle column is never used.",
        "", "## Model 1: RUL prediction", "",
        "| Model | Test RMSE (cycles) | NASA score | Mean lead time of first RUL<25 alert |", "|---|---|---|---|",
    ]
    for k in ("xgb", "cnnlstm"):
        v = r.get(k, {})
        lines.append(f"| {k} | {v.get('rmse', v.get('skipped', '-'))} | {v.get('nasa_score', '-')} | {v.get('mean_lead_time_cycles', '-')} |")
    lines += ["", f"The API uses **{r['best']}** (RMSE {r['best_rmse']}). True RUL is capped at 125 for scoring, the same as the training labels.",
              "", "![Predicted vs true](pred_vs_true.png)", "", "![RUL curves](rul_curves.png)", "",
              "## Model 2: anomaly detection", "",
              f"- Type: {m['anomaly']['type']}; threshold = 99th percentile of healthy reconstruction error.",
              f"- The flag first fires with {m['anomaly']['mean_cycles_left_at_first_flag']} cycles left on average, "
              f"which is {m['anomaly']['mean_cycles_earlier_than_rul_alert']} cycles earlier than the RUL<25 alert "
              f"(validation engines: {m['anomaly']['engines_compared']}).",
              "", "![Anomaly score](anomaly_score.png)", "",
              "## Model 3: maintenance-need classifier (NGAFID-MC, optional)", "", f"- {json.dumps(m['ngafid'])}", "",
              "## Model 4: defect text classifier", "",
              f"- Data: {m['defect']['data']}", f"- Cross-validated accuracy: {m['defect']['cv_accuracy']}", f"- {m['defect']['note']}",
              "", "![Confusion matrix](confusion_matrix.png)", "", "## Model cards", ""]
    for card in cards:
        lines += [f"### {card['name']} ({card['version']})", "", f"- Purpose: {card['purpose']}", f"- Data: {card['data']}",
                  f"- Metrics: {json.dumps(card['metrics'])}", f"- Limits: {card['limits']}", f"- Approved by: {card['approved_by']}", ""]
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out / 'report.md'}, 4 charts and model_cards.json")


if __name__ == "__main__":
    main()
