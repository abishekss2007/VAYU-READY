"""Shared data loading and feature code for the VAYU-READY ML pipeline.

ISO 13374 blocks: Data Acquisition (loading) and Data Manipulation (scaling, windows).
"""
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))
MODEL_DIR = Path(os.getenv("MODEL_DIR", ROOT / "models"))
RESULTS_DIR = Path(os.getenv("RESULTS_DIR", ROOT / "results"))

SEED = 42
RUL_CAP = 125
WINDOW = 30
ALERT_RUL = 25
OPS = ["op_setting_1", "op_setting_2", "op_setting_3"]
SENSORS = [f"s{i}" for i in range(1, 22)]
COLS = ["unit", "cycle"] + OPS + SENSORS
CONSTANT = ["s1", "s5", "s6", "s10", "s16", "s18", "s19"]  # flat in FD001, carry no information
FEATS = [s for s in SENSORS if s not in CONSTANT]           # the cycle column is never a feature

SENSOR_NAMES = {
    "s1": "Fan inlet temperature", "s2": "LPC outlet temperature", "s3": "HPC outlet temperature",
    "s4": "LPT outlet temperature", "s5": "Fan inlet pressure", "s6": "Bypass-duct pressure",
    "s7": "HPC outlet pressure", "s8": "Fan speed", "s9": "Core speed", "s10": "Engine pressure ratio",
    "s11": "HPC outlet static pressure", "s12": "Fuel flow ratio", "s13": "Corrected fan speed",
    "s14": "Corrected core speed", "s15": "Bypass ratio", "s16": "Burner fuel-air ratio",
    "s17": "Bleed enthalpy", "s18": "Demanded fan speed", "s19": "Demanded corrected fan speed",
    "s20": "HPT coolant bleed", "s21": "LPT coolant bleed",
}

DOWNLOAD_HELP = """
NASA C-MAPSS FD001 files were not found in {dir}.
Download "Turbofan Engine Degradation Simulation Data Set" (CMAPSSData.zip) from the NASA
Prognostics Center of Excellence data repository:
  https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/
and place train_FD001.txt, test_FD001.txt and RUL_FD001.txt in {dir}.
Using a SYNTHETIC FD001-like degradation data set instead so the demo still runs.
"""

# (start value, change by end of life, noise) for a synthetic FD001-like engine
_SYNTH = {
    "s1": (518.67, 0, 0), "s2": (641.8, 1.8, 0.4), "s3": (1585.0, 17.0, 5.0), "s4": (1400.0, 30.0, 6.0),
    "s5": (14.62, 0, 0), "s6": (21.61, 0, 0), "s7": (554.4, -3.1, 0.7), "s8": (2388.03, 0.22, 0.05),
    "s9": (9050.0, 45.0, 8.0), "s10": (1.3, 0, 0), "s11": (47.2, 1.1, 0.2), "s12": (522.0, -2.6, 0.6),
    "s13": (2388.03, 0.22, 0.05), "s14": (8135.0, 25.0, 8.0), "s15": (8.40, 0.12, 0.03), "s16": (0.03, 0, 0),
    "s17": (392.0, 5.0, 1.2), "s18": (2388.0, 0, 0), "s19": (100.0, 0, 0), "s20": (38.9, -0.6, 0.15),
    "s21": (23.35, -0.36, 0.09),
}


def _synth_engine(rng, unit, life):
    t = np.arange(1, life + 1)
    a = rng.uniform(4.0, 5.0)
    wear = (np.exp(a * t / life) - 1) / (np.exp(a) - 1)  # slow at first, fast near failure
    df = pd.DataFrame({"unit": unit, "cycle": t})
    df["op_setting_1"] = rng.normal(0, 0.002, life)
    df["op_setting_2"] = rng.normal(0, 0.0003, life)
    df["op_setting_3"] = 100.0
    for s, (base, delta, noise) in _SYNTH.items():
        offset = rng.normal(0, noise * 0.5) if noise else 0
        df[s] = base + offset + delta * wear * rng.uniform(0.85, 1.15) + (rng.normal(0, noise, life) if noise else 0)
    return df


def synthetic_fd001(seed=SEED):
    rng = np.random.default_rng(seed)
    train = pd.concat([_synth_engine(rng, u, int(rng.integers(130, 360))) for u in range(1, 101)], ignore_index=True)
    tests, ruls = [], []
    for u in range(1, 101):
        life = int(rng.integers(130, 360))
        cut = int(rng.integers(31, life - 7))
        tests.append(_synth_engine(rng, u, life).iloc[:cut])
        ruls.append(life - cut)
    return train, pd.concat(tests, ignore_index=True), np.array(ruls)


def load_fd001(quiet=False):
    """Returns (train, test, true_rul, dataset_name)."""
    d = DATA_DIR / "cmapss"
    files = [d / "train_FD001.txt", d / "test_FD001.txt", d / "RUL_FD001.txt"]
    if all(f.exists() for f in files):
        read = lambda f: pd.read_csv(f, sep=r"\s+", header=None, names=COLS)  # noqa: E731
        return read(files[0]), read(files[1]), np.loadtxt(files[2]), "NASA C-MAPSS FD001"
    if not quiet:
        print(DOWNLOAD_HELP.format(dir=d))
    train, test, rul = synthetic_fd001()
    return train, test, rul, "SYNTHETIC FD001-like (NASA files missing)"


def add_rul(train):
    last = train.groupby("unit")["cycle"].transform("max")
    return train.assign(rul=(last - train["cycle"]).clip(upper=RUL_CAP))


def fit_scaler(train):
    return {"min": train[FEATS].min().to_dict(), "max": train[FEATS].max().to_dict()}


def scale(df, scaler):
    lo = pd.Series(scaler["min"])
    span = (pd.Series(scaler["max"]) - lo).replace(0, 1)
    return ((df[FEATS] - lo) / span).astype("float32")


def rolling_features(df, scaler):
    """Mean, standard deviation and slope of each sensor over the last 30 cycles (per engine).

    Rows must be ordered by unit and cycle. Row position inside the engine is used only to
    measure the slope; it is never passed to the model as a feature.
    """
    x = scale(df, scaler).astype("float64")
    units = df["unit"].values
    parts = []
    for u in pd.unique(units):
        b = x[units == u].reset_index(drop=True)
        t = pd.Series(np.arange(len(b), dtype="float64"))
        mean = b.rolling(WINDOW, min_periods=1).mean()
        std = b.rolling(WINDOW, min_periods=2).std().fillna(0)
        t_mean = t.rolling(WINDOW, min_periods=1).mean()
        t_var = t.rolling(WINDOW, min_periods=1).var(ddof=0).replace(0, np.nan)
        xt_mean = b.mul(t, axis=0).rolling(WINDOW, min_periods=1).mean()
        slope = (xt_mean - mean.mul(t_mean, axis=0)).div(t_var, axis=0).fillna(0)
        parts.append(pd.concat([mean.add_suffix("_mean"), std.add_suffix("_std"), slope.add_suffix("_slope")], axis=1))
    return pd.concat(parts, ignore_index=True).astype("float32")


def windows(df, scaler):
    """30-cycle windows for the CNN-LSTM, one per row (short histories are padded with the first row)."""
    x = scale(df, scaler).values
    units = df["unit"].values
    out = np.empty((len(df), WINDOW, len(FEATS)), dtype="float32")
    start = 0
    for u in pd.unique(units):
        n = int((units == u).sum())
        block = x[start:start + n]
        padded = np.vstack([np.repeat(block[:1], WINDOW - 1, axis=0), block])
        out[start:start + n] = np.lib.stride_tricks.sliding_window_view(padded, WINDOW, axis=0).transpose(0, 2, 1)
        start += n
    return out


def nasa_score(pred, true):
    """NASA asymmetric score: late predictions (pred > true) are penalised more than early ones."""
    d = np.asarray(pred) - np.asarray(true)
    return float(np.sum(np.where(d < 0, np.exp(-d / 13) - 1, np.exp(d / 10) - 1)))


def rmse(pred, true):
    return float(np.sqrt(np.mean((np.asarray(pred) - np.asarray(true)) ** 2)))
