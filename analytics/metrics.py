import re
import numpy as np, pandas as pd
CAE = ["CAE 1", "CAE 2"]
A4 = CAE + ["Internal", "Exam"]

def sem_order(df):
    return sorted(df["Semester"].unique(), key=lambda s: int(re.findall(r"\d+", s)[0]) if re.findall(r"\d+", s) else 0)

def kpis(df):
    cent = df[df["Marks"] == df["Maximum_Marks"]]
    hi = df.loc[df["Pct"].idxmax()]
    return dict(
        current=df[df["Semester"] == sem_order(df)[-1]]["Pct"].mean(), overall=df["Pct"].mean(),
        cae1=df[df["Assessment"] == "CAE 1"]["Pct"].mean(), cae2=df[df["Assessment"] == "CAE 2"]["Pct"].mean(),
        subjects=df["Subject"].nunique(), sems_done=df[df["Assessment"] == "Exam"]["Semester"].nunique(),
        centum_total=len(cent), centum_cae=int(cent["Assessment"].isin(CAE).sum()),
        centum_sem=int((cent["Assessment"] == "Exam").sum()), n90=int((df["Pct"] >= 90).sum()),
        highest=f"{hi['Marks']:.0f}/{hi['Maximum_Marks']:.0f} · {hi['Subject']}")

def final_pct(int_eff, exam, cfg):
    """Final % = weighted Internal + Exam. Needs both; Int_eff falls back to the CAE average."""
    if pd.isna(int_eff) or pd.isna(exam):
        return np.nan
    wi, we = cfg["weights"]["Internal"], cfg["weights"]["Exam"]
    return (wi * int_eff + we * exam) / (wi + we)

def grade(p, cfg):
    for lo, letter, gp in cfg["grade_bands"]:
        if p >= lo:
            return letter, gp
    return "F", 0

def subject_table(df, cfg):
    w = df.pivot_table(index=["Semester", "Subject_Code", "Subject"], columns="Assessment", values="Pct", aggfunc="mean").reset_index()
    for c in A4:
        if c not in w:
            w[c] = np.nan
    w["Int_eff"] = w["Internal"].fillna(w[CAE].mean(axis=1))
    w["Average"] = w[A4].mean(axis=1)
    w["Improvement"] = w["CAE 2"] - w["CAE 1"]
    w["Internal→Exam gap"] = w["Exam"] - w["Int_eff"]
    w["Std Dev"] = w[A4].std(axis=1)
    w["Stability"] = np.where(w["Std Dev"].isna(), "-", np.where(w["Std Dev"] <= cfg["stable_sd"], "Consistent", "Variable"))
    w["Final %"] = [final_pct(i, e, cfg) for i, e in zip(w["Int_eff"], w["Exam"])]
    w["Grade"] = [grade(p, cfg)[0] if pd.notna(p) else "-" for p in w["Final %"]]

    def alert(r):
        if pd.notna(r["Internal→Exam gap"]) and r["Internal→Exam gap"] < -5:
            return "Exam well below internal"
        if pd.notna(r["Improvement"]) and r["Improvement"] < 0:
            return "CAE declined"
        return ""
    w["Alert"] = w.apply(alert, axis=1)
    return w

def _credit(code, cfg):
    return cfg["credits"].get(code, cfg["default_credits"])

def sgpa_table(sub, cfg):
    s = sub[sub["Final %"].notna()].copy()
    if s.empty:
        return pd.DataFrame(columns=["Semester", "SGPA"]), np.nan
    s["gp"] = s["Final %"].apply(lambda p: grade(p, cfg)[1])
    s["cr"] = s["Subject_Code"].map(lambda c: _credit(c, cfg))
    per = s.groupby("Semester").apply(lambda g: (g["gp"] * g["cr"]).sum() / g["cr"].sum(), include_groups=False).rename("SGPA").reset_index()
    return per, (s["gp"] * s["cr"]).sum() / s["cr"].sum()

def project_sgpa(cur, exam_by_subject, cfg):
    """cur: open-semester rows with Int_eff. exam_by_subject: {subject: exam %}"""
    gps, crs = [], []
    for _, r in cur.iterrows():
        gps.append(grade(final_pct(r["Int_eff"], exam_by_subject[r["Subject"]], cfg), cfg)[1]); crs.append(_credit(r["Subject_Code"], cfg))
    return float(np.dot(gps, crs) / sum(crs))

def required_uniform_exam(cur, target, cfg):
    for x in range(0, 101):
        if project_sgpa(cur, {s: x for s in cur["Subject"]}, cfg) >= target:
            return x
    return None
