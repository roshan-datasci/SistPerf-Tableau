import pandas as pd

def normalize(df):
    d = df.copy()
    for c in ["Student_ID", "Semester", "Subject"]:
        d[c] = d[c].astype(str).str.strip()
    d["Date"] = pd.to_datetime(d["Date"])
    d["Pct"] = d["Marks"] / d["Maximum_Marks"] * 100   # normalised so CAE/50 vs exam/100 compare fairly
    return d
