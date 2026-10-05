"""Train every VAYU-READY model with fixed seeds.  Run:  python -m ml.train   (or: make train)

Outputs: models/rul_xgb.joblib, models/rul_cnnlstm.pt, models/anomaly.pt (or anomaly.joblib fallback),
models/defect_clf.joblib, results/metrics.json. Then ml.evaluate writes the report, charts and model cards.
"""
import json
import random
from datetime import date

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import IsolationForest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import FeatureUnion, Pipeline

from . import common as c
from .defect_data import CATEGORIES, expand, synthetic_defects

try:
    import torch
    from .nets import AutoEncoder, CnnLstm, recon_error
except Exception:  # PyTorch missing: the XGBoost model and Isolation Forest fallback still train
    torch = None

TODAY = date.today().isoformat()


def seed_everything():
    random.seed(c.SEED)
    np.random.seed(c.SEED)
    if torch:
        torch.manual_seed(c.SEED)
        torch.set_num_threads(4)


def split_units(train):
    """Validation split by engine, never by row."""
    units = np.array(sorted(train["unit"].unique()))
    rng = np.random.default_rng(c.SEED)
    val = set(rng.choice(units, size=max(len(units) // 5, 1), replace=False).tolist())
    return train["unit"].isin(val).values


def last_rows(df):
    return df.groupby("unit").tail(1).index.values


def test_metrics(pred, true_rul):
    true = np.minimum(true_rul, c.RUL_CAP)  # same cap as the training labels
    pred = np.clip(pred, 0, c.RUL_CAP)
    return {"rmse": round(c.rmse(pred, true), 3), "nasa_score": round(c.nasa_score(pred, true), 1)}


def train_xgb(train, test, true_rul, scaler, is_val):
    X = c.rolling_features(train, scaler)
    y = train["rul"].values
    model = xgb.XGBRegressor(n_estimators=800, max_depth=5, learning_rate=0.04, subsample=0.8, colsample_bytree=0.8,
                             min_child_weight=5, random_state=c.SEED, n_jobs=4, early_stopping_rounds=40)
    model.fit(X[~is_val], y[~is_val], eval_set=[(X[is_val], y[is_val])], verbose=False)
    Xt = c.rolling_features(test, scaler)
    pred_test = model.predict(Xt.iloc[np.flatnonzero(test.index.isin(last_rows(test)))])
    return model, test_metrics(pred_test, true_rul), model.predict(X)


def train_cnnlstm(train, test, true_rul, scaler, is_val):
    W = torch.as_tensor(c.windows(train, scaler))
    y = torch.as_tensor(train["rul"].values / c.RUL_CAP, dtype=torch.float32)
    va = torch.as_tensor(is_val.copy())
    model = CnnLstm(len(c.FEATS))
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = torch.nn.MSELoss()
    Wtr, ytr, Wva, yva = W[~va], y[~va], W[va], y[va]
    best, best_state, patience = float("inf"), None, 0
    gen = torch.Generator().manual_seed(c.SEED)
    for epoch in range(40):
        model.train()
        order = torch.randperm(len(Wtr), generator=gen)
        for i in range(0, len(order), 256):
            idx = order[i:i + 256]
            opt.zero_grad()
            loss = loss_fn(model(Wtr[idx]), ytr[idx])
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            val = float(loss_fn(model(Wva), yva))
        print(f"  cnn-lstm epoch {epoch + 1:2d}  val RMSE {val ** 0.5 * c.RUL_CAP:.2f} cycles")
        if val < best - 1e-5:
            best, best_state, patience = val, {k: v.clone() for k, v in model.state_dict().items()}, 0
        else:
            patience += 1
            if patience >= 6:  # early stopping
                break
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        Wt = torch.as_tensor(c.windows(test, scaler))[np.flatnonzero(test.index.isin(last_rows(test)))]
        pred_test = model(Wt).numpy() * c.RUL_CAP
        pred_train = np.concatenate([model(W[i:i + 4096]).numpy() for i in range(0, len(W), 4096)]) * c.RUL_CAP
    return model, test_metrics(pred_test, true_rul), pred_train


def first_alert_remaining(train, pred, is_val):
    """For each validation engine: cycles left when the first 'RUL < 25' alert fires."""
    out = {}
    df = train.assign(pred=pred)[is_val]
    for u, g in df.groupby("unit"):
        hit = g[g["pred"] < c.ALERT_RUL]
        if len(hit):
            out[u] = int(g["cycle"].max() - hit["cycle"].iloc[0])
    return out


def train_anomaly(train, scaler, is_val):
    X = c.scale(train, scaler).values
    frac = train.groupby("unit").cumcount() / train.groupby("unit")["cycle"].transform("count")
    healthy = (frac < 0.30).values  # first 30% of each engine's life is assumed healthy
    if torch:
        model = AutoEncoder(len(c.FEATS))
        opt = torch.optim.Adam(model.parameters(), lr=2e-3)
        H = torch.as_tensor(X[healthy & ~is_val])
        gen = torch.Generator().manual_seed(c.SEED)
        for _ in range(60):
            order = torch.randperm(len(H), generator=gen)
            for i in range(0, len(order), 256):
                b = H[order[i:i + 256]]
                opt.zero_grad()
                loss = ((model(b) - b) ** 2).mean()
                loss.backward()
                opt.step()
        model.eval()
        err = recon_error(model, X)
        kind = "autoencoder"
    else:
        model = IsolationForest(n_estimators=200, random_state=c.SEED).fit(X[healthy & ~is_val])
        err = -model.score_samples(X)
        kind = "isolation_forest"
    threshold = float(np.percentile(err[healthy], 99))
    score = np.clip(err / (2 * threshold), 0, 1)  # 0-1; the threshold sits at 0.5
    df = train.assign(score=score)[is_val]
    remaining = {}
    for u, g in df.groupby("unit"):
        smooth = g["score"].rolling(5, min_periods=5).mean()  # 5-cycle average so one noisy cycle does not fire
        hit = g[(smooth >= 0.5).values]
        if len(hit):
            remaining[u] = int(g["cycle"].max() - hit["cycle"].iloc[0])
    return model, kind, threshold, remaining


def train_defect():
    path = c.DATA_DIR / "maintnet" / "maintnet.csv"
    if path.exists():
        df = pd.read_csv(path)  # expected columns: text, category
        texts, labels, source = df["text"].tolist(), df["category"].tolist(), "MaintNet aviation logbook"
    else:
        pairs = synthetic_defects(200, c.SEED)
        texts, labels = [t for t, _ in pairs], [k for _, k in pairs]
        source = "200 synthetic defect sentences (MaintNet not found in data/maintnet/)"
    clf = Pipeline([
        ("tfidf", FeatureUnion([
            ("word", TfidfVectorizer(preprocessor=expand, ngram_range=(1, 2), sublinear_tf=True)),
            ("char", TfidfVectorizer(preprocessor=expand, analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True)),
        ])),
        ("lr", LogisticRegression(C=10, max_iter=2000, random_state=c.SEED)),
    ])
    cv = StratifiedKFold(5, shuffle=True, random_state=c.SEED)
    pred = cross_val_predict(clf, texts, labels, cv=cv)
    labels_sorted = sorted(set(labels))
    clf.fit(texts, labels)
    metrics = {
        "data": source, "samples": len(texts), "cv_accuracy": round(accuracy_score(labels, pred), 4),
        "labels": labels_sorted, "confusion_matrix": confusion_matrix(labels, pred, labels=labels_sorted).tolist(),
        "note": "5-fold cross-validated on template-generated sentences; real logbook text will score lower." if "synthetic" in source else "5-fold cross-validated.",
    }
    return clf, metrics


def train_ngafid():
    """Optional real-data check. Expects data/ngafid/flights.csv: numeric feature columns + 'label' (0 before, 1 after maintenance)."""
    path = c.DATA_DIR / "ngafid" / "flights.csv"
    if not path.exists():
        return {"skipped": "NGAFID-MC not found in data/ngafid/ - this optional model was not trained."}
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.model_selection import train_test_split
    df = pd.read_csv(path).dropna()
    X, y = df.drop(columns=["label"]).select_dtypes("number"), df["label"]
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=c.SEED, stratify=y)
    m = GradientBoostingClassifier(random_state=c.SEED).fit(Xtr, ytr)
    p = m.predict(Xte)
    joblib.dump({"model": m, "columns": list(X.columns)}, c.MODEL_DIR / "ngafid_clf.joblib")
    return {"accuracy": round(accuracy_score(yte, p), 4), "f1": round(f1_score(yte, p), 4),
            "note": "Shows the method also works on real general-aviation flight data."}


def main():
    seed_everything()
    c.MODEL_DIR.mkdir(parents=True, exist_ok=True)
    c.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    train, test, true_rul, dataset = c.load_fd001()
    train = c.add_rul(train)
    scaler = c.fit_scaler(train)  # min-max from training data only
    is_val = split_units(train)
    metrics = {"dataset": dataset, "trained_on": TODAY, "seed": c.SEED, "window": c.WINDOW, "rul_cap": c.RUL_CAP,
               "features": c.FEATS, "dropped_constant_sensors": c.CONSTANT, "rul": {}}

    print("Model 1a: XGBoost RUL baseline")
    xgb_model, m, pred_xgb = train_xgb(train, test, true_rul, scaler, is_val)
    version = f"rul-xgb-{TODAY}"
    lead = first_alert_remaining(train, pred_xgb, is_val)
    m.update(version=version, mean_lead_time_cycles=round(float(np.mean(list(lead.values()))), 1) if lead else None)
    metrics["rul"]["xgb"] = m
    joblib.dump({"model": xgb_model, "scaler": scaler, "version": version, "metrics": m, "dataset": dataset,
                 "trained_on": TODAY}, c.MODEL_DIR / "rul_xgb.joblib")
    print("  ", m)
    best_lead = lead

    if torch:
        print("Model 1b: CNN-LSTM RUL (main model)")
        net, m2, pred_net = train_cnnlstm(train, test, true_rul, scaler, is_val)
        version2 = f"rul-cnnlstm-{TODAY}"
        lead2 = first_alert_remaining(train, pred_net, is_val)
        m2.update(version=version2, mean_lead_time_cycles=round(float(np.mean(list(lead2.values()))), 1) if lead2 else None)
        metrics["rul"]["cnnlstm"] = m2
        torch.save({"state": net.state_dict(), "scaler": scaler, "version": version2, "metrics": m2, "dataset": dataset,
                    "trained_on": TODAY, "n_feat": len(c.FEATS)}, c.MODEL_DIR / "rul_cnnlstm.pt")
        print("  ", m2)
        if m2["rmse"] < m["rmse"]:
            best_lead = lead2
    else:
        metrics["rul"]["cnnlstm"] = {"skipped": "PyTorch is not installed"}
    ranked = {k: v["rmse"] for k, v in metrics["rul"].items() if "rmse" in v}
    metrics["rul"]["best"] = min(ranked, key=ranked.get)  # the API uses the better model
    metrics["rul"]["best_rmse"] = ranked[metrics["rul"]["best"]]

    print("Model 2: anomaly detection")
    an_model, kind, threshold, an_remaining = train_anomaly(train, scaler, is_val)
    both = [u for u in an_remaining if u in best_lead]
    earlier = [an_remaining[u] - best_lead[u] for u in both]
    metrics["anomaly"] = {
        "type": kind, "threshold_error": threshold, "version": f"anomaly-{kind}-{TODAY}",
        "mean_cycles_left_at_first_flag": round(float(np.mean(list(an_remaining.values()))), 1) if an_remaining else None,
        "mean_cycles_earlier_than_rul_alert": round(float(np.mean(earlier)), 1) if earlier else None,
        "engines_compared": len(both),
    }
    bundle = {"kind": kind, "threshold": threshold, "scaler": scaler, "version": metrics["anomaly"]["version"]}
    if kind == "autoencoder":
        torch.save({**bundle, "state": an_model.state_dict(), "n_feat": len(c.FEATS)}, c.MODEL_DIR / "anomaly.pt")
    else:
        joblib.dump({**bundle, "model": an_model}, c.MODEL_DIR / "anomaly.joblib")
    print("  ", metrics["anomaly"])

    print("Model 3: maintenance-need classifier (optional, NGAFID-MC)")
    metrics["ngafid"] = train_ngafid()
    print("  ", metrics["ngafid"])

    print("Model 4: defect text classifier")
    clf, dm = train_defect()
    dm["version"] = f"defect-tfidf-lr-{TODAY}"
    metrics["defect"] = dm
    joblib.dump({"model": clf, "version": dm["version"], "labels": CATEGORIES}, c.MODEL_DIR / "defect_clf.joblib")
    print("   accuracy", dm["cv_accuracy"])

    (c.RESULTS_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(f"Saved models to {c.MODEL_DIR} and metrics to {c.RESULTS_DIR / 'metrics.json'}")

    from . import evaluate
    evaluate.main()


if __name__ == "__main__":
    main()
