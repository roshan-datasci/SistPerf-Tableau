import pandas as pd
REQ = ["Student_ID", "Academic_Year", "Semester", "Subject", "Assessment", "Marks", "Maximum_Marks", "Date"]
REQ_SIST = ["Student_ID", "Academic_Year", "Term", "Semester", "Subject_Code", "Subject", "Assessment", "Marks", "Maximum_Marks", "Date"]
OK_OLD = ["CAE 1", "CAE 2", "Semester"]
OK_SIST = ["CAE 1", "CAE 2", "Internal", "Exam"]
ASM = {"cae1": "CAE 1", "cae 1": "CAE 1", "cae2": "CAE 2", "cae 2": "CAE 2", "semester": "Semester", "sem": "Semester", "end sem": "Semester", "internal": "Internal", "exam": "Exam", "external": "Exam"}

def validate(df, cfg=None):
    """Returns (clean_df, issues_df). Bad rows are dropped from clean_df and listed in issues."""
    sist = "Subject_Code" in df.columns   # SIST ERP schema vs. original schema
    req, ok = (REQ_SIST, OK_SIST) if sist else (REQ, OK_OLD)
    miss = [c for c in req if c not in df.columns]
    if miss:
        return df.iloc[0:0], pd.DataFrame([{"Check": "Missing columns", "Count": len(miss), "Detail": ", ".join(miss)}])
    d = df.copy()
    d["Assessment"] = d["Assessment"].astype(str).str.strip().str.lower().map(ASM).fillna(d["Assessment"])
    d["Marks"] = pd.to_numeric(d["Marks"], errors="coerce")
    d["Maximum_Marks"] = pd.to_numeric(d["Maximum_Marks"], errors="coerce")
    d["_date"] = pd.to_datetime(d["Date"], errors="coerce")
    checks = {
        "Missing or non-numeric marks": d["Marks"].isna() | d["Maximum_Marks"].isna(),
        "Negative marks": d["Marks"] < 0,
        "Marks above maximum": d["Marks"] > d["Maximum_Marks"],
        "Invalid maximum marks": d["Maximum_Marks"] <= 0,
        "Unknown assessment name": ~d["Assessment"].isin(ok),
        "Invalid date": d["_date"].isna(),
        "Duplicate record": d.duplicated(["Student_ID", "Semester", "Subject_Code" if sist else "Subject", "Assessment"], keep="first"),
        "Missing identifier": d[["Student_ID", "Semester", "Subject"]].isna().any(axis=1),
    }
    bad = pd.Series(False, index=d.index)
    out = []
    for name, m in checks.items():
        out.append({"Check": name, "Count": int(m.sum()), "Detail": "rows " + ", ".join(map(str, (d.index[m][:5] + 2).tolist())) if m.any() else ""})
        bad |= m
    out.append({"Check": "Completeness (valid rows %)", "Count": round(100 * (~bad).mean(), 1) if len(d) else 0, "Detail": ""})
    return d[~bad].drop(columns="_date"), pd.DataFrame(out)
