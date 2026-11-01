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

# synthetic sync monitor data for the demo workbook
import datetime as _dt
sync = [["2026-10-21 18:30:12", "OK", "browser", 118, 118, 0, 0, ""], ["2026-10-22 07:05:41", "OK", "browser", 118, 0, 0, 0, ""],
        ["2026-10-22 19:12:03", "FAILED", "browser", 0, 0, 0, 0, "The ERP did not answer. Is the page still logged in?"],
        ["2026-10-22 19:20:55", "OK", "browser", 124, 6, 0, 0, ""], ["2026-10-24 08:41:30", "OK", "browser", 124, 0, 1, 0, ""],
        ["2026-10-26 18:02:18", "OK", "browser", 130, 6, 0, 0, ""], ["2026-10-27 06:55:09", "OK", "browser", 130, 0, 0, 2, ""]]
pd.DataFrame(sync, columns=["Time", "Status", "Source", "Records_Fetched", "New", "Changed", "Invalid", "Message"]).to_csv("data/sample/sample_sync_log.csv", index=False)
hist = [["2026-10-22 19:20:55", "NEW", 3, "S12BLH31", "Programming in Java", "CAE 1", None, 46, 50], ["2026-10-22 19:20:55", "NEW", 3, "S731BLH32", "Machine Learning Essentials", "CAE 1", None, 41, 50],
        ["2026-10-22 19:20:55", "NEW", 3, "SCSB1303", "Theory of Computation", "CAE 1", None, 44, 50], ["2026-10-24 08:41:30", "CHANGED", 3, "SCSB1303", "Theory of Computation", "CAE 1", 44, 45, 50],
        ["2026-10-26 18:02:18", "NEW", 3, "SMTB1304", "Matrices and Linear Algebra", "CAE 1", None, 38, 50], ["2026-10-26 18:02:18", "NEW", 3, "SISB4301", "Universal Human Values", "CAE 1", None, 43, 50]]
pd.DataFrame(hist, columns=["Time", "Event", "Semester", "Subject_Code", "Subject", "Assessment", "Old", "New", "Maximum"]).to_csv("data/sample/sample_change_history.csv", index=False)
