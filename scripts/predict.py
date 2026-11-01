"""Exam-mark predictions per student, with honest back-testing. Written to predictions.csv for Tableau.

For every subject whose exam is still pending (Forecast) and for every past subject (Backtest):
  predicted exam % = f(average of its CAEs), trained ONLY on earlier semesters (no look-ahead).
Model choice per student: linear regression on the CAE average vs. the plain 'exam = CAE average' baseline, picked by
leave-one-out error. The range is +/- 1.28 x that error (about an 80% interval). With very little history it uses the baseline
and a wide range. These are estimates, not results."""
import datetime, numpy as np, pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import LeaveOneOut, cross_val_predict

COLS = ["Student_ID", "Kind", "Semester", "Semester_Label", "Subject_Code", "Subject", "Series", "Pct", "Low", "High", "Error",
        "Method", "Trained_On", "N_Train", "Run_At"]

def _frame(d):
    p = d.assign(Pct=d["Marks"] / d["Maximum_Marks"]).pivot_table(index=["Semester", "Subject_Code", "Subject"], columns="Assessment", values="Pct").reset_index()
    for c in ("CAE 1", "CAE 2", "Internal", "Exam"):
        if c not in p:
            p[c] = np.nan
    p["x"] = p[["CAE 1", "CAE 2"]].mean(axis=1)
    return p

def _fit(train, x_test):
    """returns predictions, low, high, method"""
    n = len(train)
    if n >= 6:
        X, y = train[["x"]].values, train["Exam"].values
        loo = cross_val_predict(LinearRegression(), X, y, cv=LeaveOneOut())
        mae_m, mae_b = np.abs(y - loo).mean(), np.abs(y - X[:, 0]).mean()
        if mae_m < mae_b:
            rmse = float(np.sqrt(np.mean((y - loo) ** 2)))
            pred = LinearRegression().fit(X, y).predict(np.asarray(x_test).reshape(-1, 1))
            return pred, 1.28 * rmse, f"Linear regression on CAE average (leave-one-out error {mae_m * 100:.1f} pts)"
        rmse = float(np.sqrt(np.mean((y - X[:, 0]) ** 2)))
        return np.asarray(x_test), 1.28 * rmse, f"CAE average baseline (leave-one-out error {mae_b * 100:.1f} pts)"
    if n >= 2:
        rmse = float(np.sqrt(np.mean((train["Exam"].values - train["x"].values) ** 2)))
        return np.asarray(x_test), max(0.10, 1.28 * rmse), f"CAE average baseline (only {n} past subjects)"
    return np.asarray(x_test), 0.15, "CAE average baseline (no history yet)"

def predict_student(d, sid, run_at):
    f = _frame(d)
    rows = []
    for s in sorted(f["Semester"].unique()):
        train = f[(f["Semester"] < s) & f["Exam"].notna() & f["x"].notna()]
        test = f[(f["Semester"] == s) & f["x"].notna()]
        if test.empty or (s == f["Semester"].min()):
            continue
        pred, spread, method = _fit(train, test["x"].values)
        trained = "no earlier semesters" if train.empty else (f"Sem {int(train['Semester'].min())}" if train["Semester"].nunique() == 1 else f"Sem {int(train['Semester'].min())}-{int(train['Semester'].max())}")
        for (_, r), p in zip(test.iterrows(), pred):
            p = float(np.clip(p, 0, 1)); lo, hi = float(np.clip(p - spread, 0, 1)), float(np.clip(p + spread, 0, 1))
            known = pd.notna(r["Exam"])
            base = dict(Student_ID=sid, Kind="Backtest" if known else "Forecast", Semester=int(s), Semester_Label=f"Sem {int(s)}", Subject_Code=r["Subject_Code"],
                        Subject=r["Subject"], Method=method, Trained_On=trained, N_Train=len(train), Run_At=run_at)
            rows.append({**base, "Series": "Predicted", "Pct": p, "Low": lo, "High": hi, "Error": (float(r["Exam"]) - p) if known else np.nan})
            if known:
                rows.append({**base, "Series": "Actual", "Pct": float(r["Exam"]), "Low": np.nan, "High": np.nan, "Error": np.nan})
    return rows

def make_predictions(marks):
    run_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    rows = []
    for sid, d in marks.groupby("Student_ID"):
        rows += predict_student(d, sid, run_at)
    return pd.DataFrame(rows, columns=COLS)
