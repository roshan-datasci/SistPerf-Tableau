"""Write Tableau-ready CSVs (and optionally a .hyper extract) from the same data the app uses.

  python scripts/export_for_tableau.py            # real data if data/private/marks.csv exists, else the synthetic sample
  python scripts/export_for_tableau.py --hyper    # also write marks.hyper (needs: pip install tableauhyperapi)

Real data goes to data/private/tableau/ (git-ignored). Sample data goes to tableau/sample_data/ (safe to publish).
Never publish real-data extracts to Tableau Public: published data can be downloaded.
"""
import argparse, os, sys
import pandas as pd, yaml
sys.path.insert(0, os.getcwd())
from data_pipeline.extract import load_csv
from data_pipeline.validate import validate
from data_pipeline.transform import normalize
from analytics import metrics as M, attendance as A
from analytics.prediction import evaluate_and_predict

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

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--hyper", action="store_true"); a = ap.parse_args()
    cfg = yaml.safe_load(open("config.yaml"))
    real = os.path.exists("data/private/marks.csv")
    src = "data/private/marks.csv" if real else "data/sample/sample_sist.csv"
    out = "data/private/tableau" if real else "tableau/sample_data"
    os.makedirs(out, exist_ok=True)
    clean, issues = validate(load_csv(src), cfg)
    df = normalize(clean)
    df.assign(Date=df["Date"].dt.strftime("%Y-%m-%d")).to_csv(f"{out}/marks_long.csv", index=False)
    subs, sg, kp = [], [], []
    for sid, g in df.groupby("Student_ID"):
        t = M.subject_table(g, cfg); t.insert(0, "Student_ID", sid); subs.append(t)
        per, cg = M.sgpa_table(t, cfg); per.insert(0, "Student_ID", sid); per["CGPA_so_far"] = cg; sg.append(per)
        k = M.kpis(g); kp += [{"Student_ID": sid, "Metric": n, "Value": v} for n, v in k.items()]
    pd.concat(subs).to_csv(f"{out}/subject_summary.csv", index=False)
    pd.concat(sg).to_csv(f"{out}/semester_summary.csv", index=False)
    pd.DataFrame(kp).to_csv(f"{out}/kpis.csv", index=False)
    met, pred = evaluate_and_predict(df)
    if pred is not None:
        pred.to_csv(f"{out}/predictions.csv", index=False)
    apath = "data/private/attendance.csv" if real else "data/sample/sample_attendance.csv"
    if os.path.exists(apath):
        att = pd.read_csv(apath); parts = []
        for sid, g in (att.groupby("Student_ID") if "Student_ID" in att else [("ME", att)]):
            t = A.table(g, cfg); t.insert(0, "Student_ID", sid); parts.append(t)
        pd.concat(parts).to_csv(f"{out}/attendance.csv", index=False)
    print(f"Source: {src}\nWrote CSVs to {out}/: {sorted(os.listdir(out))}")
    if a.hyper:
        try:
            write_hyper(pd.read_csv(f"{out}/marks_long.csv"), f"{out}/marks.hyper"); print("Wrote marks.hyper")
        except ImportError:
            print("pip install tableauhyperapi to write a .hyper extract. The CSVs work in Tableau as they are.")

if __name__ == "__main__":
    main()
