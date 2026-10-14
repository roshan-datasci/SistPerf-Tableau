"""Experimental Sem-N exam prediction. Trained on POOLED students (needs many students).
No leakage: features are CAE 1, CAE 2 and the student's PREVIOUS semester exam average only."""
import numpy as np, pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupShuffleSplit
from analytics.metrics import sem_order

def _wide(df):
    d = df.assign(Assessment=df["Assessment"].replace({"Semester": "Exam"}))
    w = d.pivot_table(index=["Student_ID", "Semester", "Subject"], columns="Assessment", values="Pct").reset_index()
    order = {s: i for i, s in enumerate(sem_order(df))}
    prev = df[df["Assessment"] == "Semester"].groupby(["Student_ID", "Semester"])["Pct"].mean().reset_index()
    prev["n"] = prev["Semester"].map(order) + 1
    w["n"] = w["Semester"].map(order)
    w = w.merge(prev[["Student_ID", "n", "Pct"]].rename(columns={"Pct": "prev_avg"}), on=["Student_ID", "n"], how="left")
    return w

def evaluate_and_predict(df, min_students=15):
    w = _wide(df)
    for c in ["CAE 1", "CAE 2", "Exam"]:
        if c not in w:
            w[c] = np.nan
    feats = ["CAE 1", "CAE 2", "prev_avg"]
    tr = w.dropna(subset=feats + ["Exam"])
    if tr["Student_ID"].nunique() < min_students:
        return None, None
    g = tr["Student_ID"]
    a, b = next(GroupShuffleSplit(1, test_size=0.25, random_state=0).split(tr, groups=g))
    m = Ridge(alpha=1.0).fit(tr.iloc[a][feats], tr.iloc[a]["Exam"])
    te = tr.iloc[b]
    base = te[["CAE 1", "CAE 2"]].mean(axis=1)
    pred = m.predict(te[feats])
    mae_b = float(np.mean(np.abs(te["Exam"] - base))); mae_m = float(np.mean(np.abs(te["Exam"] - pred)))
    rmse = float(np.sqrt(np.mean((te["Exam"] - pred) ** 2)))
    m = Ridge(alpha=1.0).fit(tr[feats], tr["Exam"])
    todo = w[w["Exam"].isna() & w[feats].notna().all(axis=1)]
    out = todo[["Student_ID", "Semester", "Subject"]].copy()
    out["Predicted"] = np.clip(m.predict(todo[feats]), 0, 100)
    out["Low"] = np.clip(out["Predicted"] - 1.28 * rmse, 0, 100)
    out["High"] = np.clip(out["Predicted"] + 1.28 * rmse, 0, 100)
    return dict(mae_baseline=mae_b, mae_model=mae_m, rmse=rmse, n_train=len(a), n_test=len(b)), out
