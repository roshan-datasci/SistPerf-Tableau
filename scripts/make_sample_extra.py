"""SYNTHETIC attendance and timetable samples (no real data)."""
import numpy as np, pandas as pd
rng = np.random.default_rng(11)
SUBJ = [("S12BLH31", "Programming in Java"), ("S731BLH32", "Machine Learning Essentials"), ("SCSB1303", "Theory of Computation"),
        ("SCSBOB1301", "Computer Architecture and Organization"), ("SISB4301", "Universal Human Values"), ("SMTB1304", "Matrices and Linear Algebra")]
rows = []
for i in range(1, 41):
    for code, name in SUBJ:
        tot = int(rng.integers(36, 46)); rows.append([f"STU{i:03d}", code, name, "Theory", int(min(tot, round(tot * rng.normal(0.87, 0.07)))), tot])
    tot = 12; rows.append([f"STU{i:03d}", "SCSL1301", "Programming Lab", "Practical", int(tot - rng.choice([0, 0, 0, 1, 2])), tot])
pd.DataFrame(rows, columns=["Student_ID", "Subject_Code", "Subject", "Type", "Present", "Total"]).to_csv("data/sample/sample_attendance.csv", index=False)
slots = [("09:00", "09:50"), ("09:50", "10:40"), ("11:00", "11:50"), ("11:50", "12:40"), ("13:30", "14:20"), ("14:20", "15:10")]
tt = []
for d, day in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]):
    for p, (a, b) in enumerate(slots):
        if day == "Friday" and p >= 4:
            tt.append([day, p + 1, a, b, "SCSL1301", "Programming Lab", "Practical"]); continue
        c, n = SUBJ[(d * 2 + p) % 6]; tt.append([day, p + 1, a, b, c, n, "Theory"])
pd.DataFrame(tt, columns=["Day", "Period", "Start", "End", "Subject_Code", "Subject", "Type"]).to_csv("data/sample/sample_timetable.csv", index=False)
print(len(rows), "attendance rows;", len(tt), "timetable rows")
