"""Experimental exam prediction. Trained on POOLED students (needs many students).
No leakage: features are the internal estimate (Internal, or CAE average if not yet published)
and the student's PREVIOUS semester exam average. Caveat: at prediction time the internal estimate
comes from CAEs, which may differ from the final Internal mark."""
import numpy as np, pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupShuffleSplit
from analytics.metrics import sem_order, A4, CAE

def _wide(df):
    w = df.pivot_table(index=["Student_ID", "Semester", "Subject"], columns="Assessment", values="Pct").reset_index()
    for c in A4:
        if c not in w:
            w[c] = np.nan
    w["Int_eff"] = w["Internal"].fillna(w[CAE].mean(axis=1))
    order = {s: i for i, s in enumerate(sem_order(df))}
    prev = df[df["Assessment"] == "Exam"].groupby(["Student_ID", "Semester"])["Pct"].mean().reset_index()
    prev["n"] = prev["Semester"].map(order) + 1
    w["n"] = w["Semester"].map(order)
    return w.merge(prev[["Student_ID", "n", "Pct"]].rename(columns={"Pct": "prev_avg"}), on=["Student_ID", "n"], how="left")

def evaluate_and_predict(df, min_students=15):
    w = _wide(df)
    feats = ["Int_eff", "prev_avg"]
    tr = w.dropna(subset=feats + ["Exam"])
    if tr["Student_ID"].nunique() < min_students:
        return None, None
    a, b = next(GroupShuffleSplit(1, test_size=0.25, random_state=0).split(tr, groups=tr["Student_ID"]))
    m = Ridge(alpha=1.0).fit(tr.iloc[a][feats], tr.iloc[a]["Exam"])
    te = tr.iloc[b]
    pred = m.predict(te[feats])
    mae_b = float(np.mean(np.abs(te["Exam"] - te["Int_eff"])))
    mae_m = float(np.mean(np.abs(te["Exam"] - pred)))
    rmse = float(np.sqrt(np.mean((te["Exam"] - pred) ** 2)))
    m = Ridge(alpha=1.0).fit(tr[feats], tr["Exam"])
    todo = w[w["Exam"].isna() & w[feats].notna().all(axis=1)]
    out = todo[["Student_ID", "Semester", "Subject"]].copy()
    out["Predicted"] = np.clip(m.predict(todo[feats]), 0, 100)
    out["Low"] = np.clip(out["Predicted"] - 1.28 * rmse, 0, 100)
    out["High"] = np.clip(out["Predicted"] + 1.28 * rmse, 0, 100)
    return dict(mae_baseline=mae_b, mae_model=mae_m, rmse=rmse, n_train=len(a), n_test=len(b)), out
