"""Write the ACTUAL ERP data as Tableau-ready files. No estimates, no grades, no predictions: Tableau does the calculations.

  python scripts/export_for_tableau.py [--hyper]
  python -m tracker.tracker --adapter browser --export-tableau      # fetch + export in one go

Real data  -> data/private/tableau/   (git-ignored; keep real workbooks local, never on Tableau Public)
Sample data-> tableau/sample_data/    (synthetic; safe to publish)
Files: marks_long.csv, semester_results.csv, cae_marks.csv, credits.csv (you fill the Credits column once), attendance.csv (if present).
Maximum marks are not sent by the ERP for results, so Max_Is_Assumed = 1 marks the ones this project assumed (50, labs 25)."""
import argparse, os, re, sys
import pandas as pd
sys.path.insert(0, os.getcwd())
from data_pipeline.extract import load_csv
from data_pipeline.validate import validate

CURRICULUM = "data/curriculum_r2023_cse_ds.csv"     # SIST B.E. CSE (Data Science) Regulations 2023: credits and maximum marks per course
CURR_TOTALS = {1: 17, 2: 21, 3: 20, 4: 22, 5: 22, 6: 24, 7: 21, 8: 13}   # curriculum credit totals per semester

def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower().replace("&", "and")).strip()

def load_curriculum():
    if not os.path.exists(CURRICULUM):
        return {}, {}
    by_code, by_title = {}, {}
    for r in pd.read_csv(CURRICULUM, dtype=str).fillna("").to_dict("records"):
        by_code.setdefault(r["Course_Code"].replace(" ", "").upper(), r); by_title.setdefault(norm(r["Course_Title"]), r)
    return by_code, by_title

def find(code, title, cur):
    r = cur[0].get(str(code).replace(" ", "").upper())
    if r:
        return r, "code"
    r = cur[1].get(norm(title))
    return (r, "title") if r else (None, "")


def write_hyper(df, path):
    from tableauhyperapi import HyperProcess, Telemetry, Connection, CreateMode, TableDefinition, SqlType, TableName, Inserter
    def typ(s):
        return SqlType.double() if pd.api.types.is_float_dtype(s) else SqlType.big_int() if pd.api.types.is_integer_dtype(s) else SqlType.text()
    d = df.copy()
    for c in d.columns:
        if not (pd.api.types.is_float_dtype(d[c]) or pd.api.types.is_integer_dtype(d[c])):
            d[c] = d[c].astype(str)
    table = TableDefinition(TableName("Extract", "Extract"), [TableDefinition.Column(c, typ(d[c])) for c in d.columns])
    with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hp:
        with Connection(hp.endpoint, path, CreateMode.CREATE_AND_REPLACE) as con:
            con.catalog.create_schema("Extract"); con.catalog.create_table(table)
            with Inserter(con, table) as ins:
                ins.add_rows([[None if pd.isna(v) else v for v in r] for r in d.itertuples(index=False, name=None)]); ins.execute()

def run(hyper=False):
    real = os.path.exists("data/private/marks.csv")
    src = "data/private/marks.csv" if real else "data/sample/sample_sist.csv"
    out = "data/private/tableau" if real else "tableau/sample_data"
    os.makedirs(out, exist_ok=True)
    d, issues = validate(load_csv(src))
    for c, v in (("Result", None), ("ERP_Total", None), ("Max_Is_Assumed", 1)):
        if c not in d:
            d[c] = v
    d["Semester"] = pd.to_numeric(d["Semester"].astype(str).str.replace("Sem", "", regex=False).str.strip()).astype(int)
    d["Semester_Label"] = "Sem " + d["Semester"].astype(str)
    cur = load_curriculum()
    match = {(c, t): find(c, t, cur) for c, t in d[["Subject_Code", "Subject"]].drop_duplicates().itertuples(index=False)}
    mx, assumed = [], []
    for c, t, a, m, am in zip(d["Subject_Code"], d["Subject"], d["Assessment"], d["Maximum_Marks"], d["Max_Is_Assumed"]):
        row = match[(c, t)][0]
        if row is None:
            mx.append(m); assumed.append(am)
        elif a == "Internal" and row["CAE_Max"]:
            mx.append(float(row["CAE_Max"])); assumed.append(0)
        elif a == "Exam" and row["ESE_Max"]:
            mx.append(float(row["ESE_Max"])); assumed.append(0)
        else:
            mx.append(m); assumed.append(0 if a.startswith("CAE") else am)   # the ERP CAE page shows a maximum of 50
    d["Maximum_Marks"], d["Max_Is_Assumed"] = mx, assumed
    # credits: curriculum first; anything you typed into credits.csv wins; new subjects are added, nothing is overwritten
    cp = f"{out}/credits.csv"
    old = pd.read_csv(cp, dtype=str).fillna("") if os.path.exists(cp) else pd.DataFrame(columns=["Subject_Code", "Subject", "Credits", "Credits_Source"])
    mine = {c: v for c, v in zip(old["Subject_Code"], old["Credits"]) if v != ""}
    rows = []
    for (c, t), (m, how) in match.items():
        if c in mine:
            rows.append({"Subject_Code": c, "Subject": t, "Credits": mine[c], "Credits_Source": "your value"})
        else:
            rows.append({"Subject_Code": c, "Subject": t, "Credits": m["Credits"] if m else "",
                         "Credits_Source": {"code": "curriculum (code)", "title": "curriculum (matched by title: check the code)"}.get(how, "not found: fill in")})
    cr = pd.DataFrame(rows).sort_values("Subject_Code"); cr.to_csv(cp, index=False)
    cmap = dict(zip(cr["Subject_Code"], cr["Credits"]))
    d["Credits"] = pd.to_numeric(d["Subject_Code"].map(cmap), errors="coerce")
    d["Assessment_Order"] = d["Assessment"].map({"CAE 1": 1, "CAE 2": 2, "Internal": 3, "Exam": 4}).fillna(5).astype(int)
    per = d.drop_duplicates(["Semester", "Subject_Code"]).groupby("Semester")["Credits"].sum()
    for s, v in per.items():
        ref = CURR_TOTALS.get(int(s))
        print(f"Credits Sem {s}: {v:g}" + ("" if ref is None else f" (curriculum total {ref}" + (": matches)" if v == ref else ")")))
    miss = cr[cr["Credits"] == ""]
    if len(miss):
        print("No credits found for:", ", ".join(miss["Subject_Code"]), "-> fill them in credits.csv")
    d = d.rename(columns={"Date": "Fetched_On"})        # the date the data was fetched, NOT the exam date
    cols = ["Student_ID", "Academic_Year", "Term", "Semester", "Semester_Label", "Subject_Code", "Subject", "Assessment", "Assessment_Order",
            "Marks", "Maximum_Marks", "Max_Is_Assumed", "ERP_Total", "Result", "Credits", "Fetched_On"]
    d[cols].sort_values(["Student_ID", "Semester", "Subject_Code", "Assessment_Order"]).to_csv(f"{out}/marks_long.csv", index=False)
    ap = "data/private/attendance.csv" if real else "data/sample/sample_attendance.csv"
    if os.path.exists(ap):
        pd.read_csv(ap).to_csv(f"{out}/attendance.csv", index=False)
    print(f"Source: {src}\nWrote to {out}/: {sorted(os.listdir(out))}")
    if hyper:
        try:
            write_hyper(pd.read_csv(f"{out}/marks_long.csv"), f"{out}/marks.hyper"); print("Wrote marks.hyper")
        except ImportError:
            print("pip install tableauhyperapi to write a .hyper extract. The CSVs work in Tableau as they are.")
    return out

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--hyper", action="store_true"); run(ap.parse_args().hyper)

if __name__ == "__main__":
    main()
