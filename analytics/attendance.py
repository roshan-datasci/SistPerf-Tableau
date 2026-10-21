"""Attendance maths. Input rows: Subject_Code, Subject, Type (Theory/Practical), Present, Total."""
import math
import pandas as pd

def stats(present, total, min_pct):
    """(percent, classes you can still miss, consecutive classes needed to recover). None = cannot recover."""
    if not total:
        return float("nan"), None, None
    t = min_pct / 100
    pct = present / total * 100
    if pct >= min_pct:
        return pct, max(0, math.floor(round(present / t - total, 9))), 0
    need = None if t >= 1 else math.ceil(round((t * total - present) / (1 - t), 9))
    return pct, 0, need

def table(att, cfg):
    mins = cfg["attendance"]
    rows = []
    for _, r in att.iterrows():
        prac = str(r["Type"]).lower().startswith("prac")
        mn = mins["practical_min"] if prac else mins["theory_min"]
        pct, safe, need = stats(float(r["Present"]), float(r["Total"]), mn)
        status = "OK" if pct >= mn else "Below minimum"
        if status == "OK" and safe == 0:
            status = "No margin"
        rows.append({"Subject_Code": r["Subject_Code"], "Subject": r["Subject"], "Type": "Practical" if prac else "Theory",
                     "Present": int(r["Present"]), "Total": int(r["Total"]), "Percent": round(pct, 1), "Required %": mn,
                     "Status": status, "Can still miss": safe, "Classes needed": "cannot recover" if need is None else need})
    return pd.DataFrame(rows)
