import pandas as pd

def normalize(df):
    d = df.copy()
    for c in ["Student_ID", "Subject"]:
        d[c] = d[c].astype(str).str.strip()
    if "Subject_Code" not in d:
        d["Subject_Code"] = d["Subject"]
    d["Semester"] = "Sem " + d["Semester"].astype(str).str.replace("Sem", "", regex=False).str.strip()
    d["Date"] = pd.to_datetime(d["Date"])
    d["Pct"] = d["Marks"] / d["Maximum_Marks"] * 100   # CAE/50, lab/25 and exam/100 all compare fairly
    return d
