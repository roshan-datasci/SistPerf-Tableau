import re
import numpy as np, pandas as pd
A3 = ["CAE 1", "CAE 2", "Exam"]   # "Exam" = semester exam (avoids clash with the Semester column)

def wts(cfg):
    return {("Exam" if k == "Semester" else k): v for k, v in cfg["weights"].items()}

def sem_order(df):
    return sorted(df["Semester"].unique(), key=lambda s: int(re.findall(r"\d+", s)[0]) if re.findall(r"\d+", s) else 0)

def kpis(df):
    if df.empty:
        return {}
    cent = df[df["Marks"] == df["Maximum_Marks"]]
    hi = df.loc[df["Pct"].idxmax()]
    return dict(
        current=df[df["Semester"] == sem_order(df)[-1]]["Pct"].mean(), overall=df["Pct"].mean(),
        cae1=df[df["Assessment"] == "CAE 1"]["Pct"].mean(), cae2=df[df["Assessment"] == "CAE 2"]["Pct"].mean(),
        subjects=df["Subject"].nunique(), sems_done=df[df["Assessment"] == "Semester"]["Semester"].nunique(),
        centum_total=len(cent), centum_cae=int(cent["Assessment"].isin(["CAE 1", "CAE 2"]).sum()),
        centum_sem=int((cent["Assessment"] == "Semester").sum()), n90=int((df["Pct"] >= 90).sum()),
        highest=f"{hi['Marks']:.0f} · {hi['Subject']}")

def final_pct(row, wt):
    num = den = 0.0
    for a, w in wt.items():
        if pd.notna(row.get(a)):
            num += w * row[a]; den += w
    return num / den if den else np.nan

def grade(p, cfg):
    for lo, letter, gp in cfg["grade_bands"]:
        if p >= lo:
            return letter, gp
    return "F", 0

def subject_table(df, cfg):
    d = df.assign(Assessment=df["Assessment"].replace({"Semester": "Exam"}))
    w = d.pivot_table(index=["Semester", "Subject"], columns="Assessment", values="Pct", aggfunc="mean").reset_index()
    for c in A3:
        if c not in w:
            w[c] = np.nan
    w["Average"] = w[A3].mean(axis=1)
    w["Improvement"] = w["CAE 2"] - w["CAE 1"]
    w["CAE→Exam gap"] = w["Exam"] - w[["CAE 1", "CAE 2"]].mean(axis=1)
    w["Std Dev"] = w[A3].std(axis=1)
    w["Stability"] = np.where(w["Std Dev"].isna(), "-", np.where(w["Std Dev"] <= cfg["stable_sd"], "Consistent", "Variable"))
    w["Final %"] = w.apply(lambda r: final_pct(r, wts(cfg)), axis=1)
    w["Grade"] = [grade(p, cfg)[0] if pd.notna(r) else "-" for p, r in zip(w["Final %"], w["Exam"])]

    def alert(r):
        if pd.notna(r["Exam"]) and pd.notna(r["CAE 2"]) and r["Exam"] < r["CAE 2"] - 2:
            return "Exam below CAE 2"
        if pd.notna(r["Improvement"]) and r["Improvement"] < 0:
            return "CAE declined"
        return ""
    w["Alert"] = w.apply(alert, axis=1)
    return w

def sgpa_table(sub, cfg):
    s = sub[sub["Exam"].notna()].copy()
    if s.empty:
        return pd.DataFrame(columns=["Semester", "SGPA"]), np.nan
    s["gp"] = s["Final %"].apply(lambda p: grade(p, cfg)[1])
    s["cr"] = s["Subject"].map(lambda x: cfg["credits"].get(x, cfg["default_credits"]))
    per = s.groupby("Semester").apply(lambda g: (g["gp"] * g["cr"]).sum() / g["cr"].sum(), include_groups=False).rename("SGPA").reset_index()
    return per, (s["gp"] * s["cr"]).sum() / s["cr"].sum()

def project_sgpa(cur, exam_by_subject, cfg):
    """cur: rows with CAE 1 / CAE 2 for the open semester. exam_by_subject: {subject: exam %}"""
    gps, crs = [], []
    for _, r in cur.iterrows():
        f = final_pct({"CAE 1": r["CAE 1"], "CAE 2": r["CAE 2"], "Exam": exam_by_subject[r["Subject"]]}, wts(cfg))
        gps.append(grade(f, cfg)[1]); crs.append(cfg["credits"].get(r["Subject"], cfg["default_credits"]))
    return float(np.dot(gps, crs) / sum(crs))

def required_uniform_exam(cur, target, cfg):
    for x in range(0, 101):
        if project_sgpa(cur, {s: x for s in cur["Subject"]}, cfg) >= target:
            return x
    return None
