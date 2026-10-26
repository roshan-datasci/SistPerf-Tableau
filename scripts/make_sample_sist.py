"""Generate SYNTHETIC marks in the SIST ERP shape (40 fake students, no real data).

Shape copied from the ERP screens:
  - Current term shows CAE marks, out of 50 per subject (lab subjects out of 25).
  - Past terms show only Internal and Exam marks (no separate CAEs).
  - Terms are labelled like '2026-2027 OCT-NOV', with a semester number.
ASSUMPTION (confirm against real data): theory = 50 internal + 50 exam, lab = 25 + 25.
"""
import numpy as np, pandas as pd
rng = np.random.default_rng(7)
# (code, title, is_lab)
SUBJ = {
 1: ("2025-2026", "OCT-NOV", [("SHSB1101","Technical English",0),("SMTB1103","Calculus and Numerical Methods",0),("SPHB1101","Physics",0),("SEEB1101","Electrical & Electronics Engineering",0),("S11BLH11","Programming in C",0),("SPHB2101","Physics Lab",1)]),
 2: ("2025-2026", "APR-MAY", [("S731BLH22","Data Structures & Algorithms",0),("SCYB2101","Chemistry Lab",1),("SCYB1101","Chemistry",0),("S11BLH21","Programming in Python",0),("SCSB1232","Exploratory Data Analysis",0),("SMTB1212","Discrete Structures",0),("SCSB1231","Data and Information Science",0)]),
 3: ("2026-2027", "OCT-NOV", [("S12BLH31","Programming in Java",0),("S731BLH32","Machine Learning Essentials",0),("SCSB1303","Theory of Computation",0),("SCSBOB1301","Computer Architecture and Organization",0),("SISB4301","Universal Human Values",0),("SMTB1304","Matrices and Linear Algebra",0)]),
}
DATES = {1: ("2025-12-05", "2025-12-20"), 2: ("2026-05-08", "2026-05-25"), 3: ("2026-10-12", None)}
rows = []
for i in range(1, 41):
    sid, ability = f"STU{i:03d}", rng.normal(78, 9)
    for sem, (yr, term, subs) in SUBJ.items():
        for code, title, lab in subs:
            mx = 25 if lab else 50
            base = ability + rng.normal(0, 7)
            def mk(pct): return int(np.clip(round(pct / 100 * mx), 0.3 * mx, mx))
            if sem < 3:
                rows.append([sid, yr, term, sem, code, title, "Internal", mk(base + 4 + rng.normal(0, 5)), mx, DATES[sem][0]])
                rows.append([sid, yr, term, sem, code, title, "Exam", mk(base + rng.normal(0, 8)), mx, DATES[sem][1]])
            else:
                rows.append([sid, yr, term, sem, code, title, "CAE 1", mk(base + rng.normal(0, 6)), mx, DATES[3][0]])
df = pd.DataFrame(rows, columns=["Student_ID","Academic_Year","Term","Semester","Subject_Code","Subject","Assessment","Marks","Maximum_Marks","Date"])
k = ["Student_ID", "Semester", "Subject_Code"]
df["ERP_Total"] = df.groupby(k)["Marks"].transform(lambda s: s.sum() if len(s) == 2 else float("nan"))
mx = df.groupby(k)["Maximum_Marks"].transform("sum")
ex = df["Marks"].where(df["Assessment"] == "Exam"); exm = df["Maximum_Marks"].where(df["Assessment"] == "Exam")
exr = ex.groupby([df[c] for c in k]).transform("max") / exm.groupby([df[c] for c in k]).transform("max")
df["Result"] = ["PASS" if a == "CAE 1" else ("Pass" if (e >= 0.3 and t / m >= 0.5) else "Fail") for a, e, t, m in zip(df["Assessment"], exr, df["ERP_Total"], mx)]
df["Max_Is_Assumed"] = 1
df.to_csv("data/sample/sample_sist.csv", index=False)
print("rows:", len(rows))
