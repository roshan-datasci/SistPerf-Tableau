"""Generate SYNTHETIC marks (40 fake students). No real data."""
import numpy as np, pandas as pd
rng = np.random.default_rng(42)
SUBJ = {"Sem 1": ["Mathematics", "Python", "DBMS", "Statistics", "English", "Physics"],
        "Sem 2": ["Mathematics II", "Data Structures", "Operating Systems", "Probability", "Communication", "Electronics"],
        "Sem 3": ["Algorithms", "Machine Learning", "Networks", "Linear Algebra", "Cloud Basics", "Ethics"]}
DATES = {"Sem 1": ("2025-09-15", "2025-10-20", "2025-12-10"), "Sem 2": ("2026-02-10", "2026-03-15", "2026-05-20"),
         "Sem 3": ("2026-09-14", "2026-10-05", "2026-12-10")}
YEAR = {"Sem 1": "2025-26", "Sem 2": "2025-26", "Sem 3": "2026-27"}
rows = []
for i in range(1, 41):
    sid, ability = f"STU{i:03d}", rng.normal(72, 9)
    for sem, subs in SUBJ.items():
        for s in subs:
            base = ability + rng.normal(0, 6) + (2 if sem != "Sem 1" else 0)
            marks = [base - 3 + rng.normal(0, 4), base + 2 + rng.normal(0, 4), base + rng.normal(0, 5)]
            for a, m, d in zip(["CAE 1", "CAE 2", "Semester"], marks, DATES[sem]):
                if sem == "Sem 3" and a == "Semester":
                    continue  # exam not taken yet -> prediction target
                rows.append([sid, YEAR[sem], sem, s, a, int(np.clip(round(m), 30, 100)), 100, d])
pd.DataFrame(rows, columns=["Student_ID", "Academic_Year", "Semester", "Subject", "Assessment", "Marks", "Maximum_Marks", "Date"]) \
  .to_csv("data/sample/sample_marks.csv", index=False)
print("rows:", len(rows))
