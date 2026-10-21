import math, re
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
    """Final % = 50% internal + 50% exam (regulation 14). Int_eff may be an estimate from CAEs."""
    if pd.isna(int_eff) or pd.isna(exam):
        return np.nan
    wi, we = cfg["weights"]["Internal"], cfg["weights"]["Exam"]
    return (wi * int_eff + we * exam) / (wi + we)

def grade(p, cfg, exam_pct=None):
    """Letter and grade points. RA if the exam is below the 30% minimum (regulation 15) or total is below 50."""
    if p < cfg["pass_total_pct"] or (exam_pct is not None and exam_pct < cfg["pass_exam_pct"]):
        return "RA", 0
    for lo, letter, gp in cfg["grade_bands"]:
        if p >= lo:
            return letter, gp
    return "RA", 0

def _internal_est(row, cfg):
    """Internal estimate before the real mark is published: CAE part (80%) + assignment part (20%)."""
    cae = [row[c] for c in CAE if pd.notna(row[c])]
    if not cae:
        return np.nan
    avg = float(np.mean(cae))
    a = cfg.get("assignment_marks", {}).get(row["Subject_Code"])
    ap = a / 10 * 100 if a is not None else avg
    k = cfg["cae_weight_of_internal"]
    return k * avg + (1 - k) * ap

def subject_table(df, cfg):
    w = df.pivot_table(index=["Semester", "Subject_Code", "Subject"], columns="Assessment", values="Pct", aggfunc="mean").reset_index()
    for c in A4:
        if c not in w:
            w[c] = np.nan
    w["Int_eff"] = [r["Internal"] if pd.notna(r["Internal"]) else _internal_est(r, cfg) for _, r in w.iterrows()]
    w["Average"] = w[A4].mean(axis=1)
    w["Improvement"] = w["CAE 2"] - w["CAE 1"]
    w["Internal→Exam gap"] = w["Exam"] - w["Int_eff"]
    w["Std Dev"] = w[A4].std(axis=1)
    w["Stability"] = np.where(w["Std Dev"].isna(), "-", np.where(w["Std Dev"] <= cfg["stable_sd"], "Consistent", "Variable"))
    w["Final %"] = [final_pct(i, e, cfg) for i, e in zip(w["Int_eff"], w["Exam"])]
    gr = [grade(p, cfg, e) if pd.notna(p) else ("-", np.nan) for p, e in zip(w["Final %"], w["Exam"])]
    w["Grade"], w["GP"] = [g[0] for g in gr], [g[1] for g in gr]

    def alert(r):
        if r["Grade"] == "RA":
            return "Arrear (RA)"
        if pd.notna(r["Internal→Exam gap"]) and r["Internal→Exam gap"] < -5:
            return "Exam well below internal"
        if pd.notna(r["Improvement"]) and r["Improvement"] < 0:
            return "CAE declined"
        return ""
    w["Alert"] = w.apply(alert, axis=1)
    return w

def _credit(code, cfg):
    return cfg["credits"].get(code, cfg["default_credits"])

def _cleared(sub, cfg):
    s = sub[sub["Final %"].notna() & (sub["Grade"] != "RA")].copy()   # RA excluded from GPA/CGPA (regulation 16)
    s["cr"] = s["Subject_Code"].map(lambda c: _credit(c, cfg))
    return s

def sgpa_table(sub, cfg):
    s = _cleared(sub, cfg)
    if s.empty:
        return pd.DataFrame(columns=["Semester", "SGPA"]), np.nan
    per = s.groupby("Semester").apply(lambda g: (g["GP"] * g["cr"]).sum() / g["cr"].sum(), include_groups=False).rename("SGPA").reset_index()
    return per, (s["GP"] * s["cr"]).sum() / s["cr"].sum()

def cgpa_parts(sub, cfg):
    s = _cleared(sub, cfg)
    return float((s["GP"] * s["cr"]).sum()), float(s["cr"].sum())

def classify(cgpa, cfg):
    for thr, label in cfg["classification"]:
        if cgpa >= thr:
            return label
    return "Below the 5.0 CGPA minimum for the degree"

def cgpa_needed(points, credits, target, cfg):
    """Average grade point needed on the remaining credits to end at the target CGPA."""
    total = cfg["total_credits_required"]
    return None if credits >= total else (target * total - points) / (total - credits)

def project_sgpa(cur, exam_by_subject, cfg):
    num = den = 0.0
    for _, r in cur.iterrows():
        e = exam_by_subject[r["Subject"]]
        letter, gp = grade(final_pct(r["Int_eff"], e, cfg), cfg, e)
        if letter != "RA":
            c = _credit(r["Subject_Code"], cfg); num += gp * c; den += c
    return float(num / den) if den else 0.0

def required_uniform_exam(cur, target, cfg):
    for x in range(0, 101):
        if project_sgpa(cur, {s: x for s in cur["Subject"]}, cfg) >= target:
            return x
    return None

def exam_needed(int_eff, cfg, target_final=None):
    """Exam % needed so the total reaches target_final (default: the 50% pass mark), never below the 30% exam minimum."""
    wi, we = cfg["weights"]["Internal"], cfg["weights"]["Exam"]
    t = cfg["pass_total_pct"] if target_final is None else target_final
    return max(cfg["pass_exam_pct"], (t * (wi + we) - wi * int_eff) / we)

def risk_table(cur, cfg):
    """Arrear-risk check for subjects whose exam is still pending."""
    rows = []
    for _, r in cur.iterrows():
        need = exam_needed(r["Int_eff"], cfg)
        mx = 25 if "lab" in r["Subject"].lower() else 50      # assumed exam maximum
        risk = "Unreachable" if need > 100 else "High" if need >= 75 else "Watch" if need >= 50 else "Low"
        rows.append({"Subject": r["Subject"], "Internal est. %": round(float(r["Int_eff"]), 1), "Min exam %": round(float(need), 1),
                     "Min exam marks": "-" if need > 100 else f"{math.ceil(round(need / 100 * mx, 6))}/{mx}", "Risk": risk})
    return pd.DataFrame(rows, columns=["Subject", "Internal est. %", "Min exam %", "Min exam marks", "Risk"])

def eligibility(cgpa, arrears, cfg):
    e = cfg["eligibility"]
    return [("Degree minimum CGPA", cgpa >= e["degree_min_cgpa"], f"CGPA {cgpa:.2f} vs the {e['degree_min_cgpa']} minimum (regulation 16)"),
            ("Study or training outside the institution", cgpa >= e["exposure_min_cgpa"] and arrears == 0,
             f"needs CGPA of at least {e['exposure_min_cgpa']} and no arrears (you: {cgpa:.2f}, arrears {arrears}) (regulation 12)")]
