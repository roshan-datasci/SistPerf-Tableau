# Tableau guide

1. Run `python scripts/export_for_tableau.py` (add `--hyper` for an extract).
2. In Tableau: Connect > Text file, and add `marks_long.csv`, `subject_summary.csv`, `semester_summary.csv`, `kpis.csv`, and `attendance.csv` / `predictions.csv` if present. Join on `Student_ID` (+ `Semester`, `Subject_Code`).
3. Real-data exports are in `data/private/tableau/`. **Keep those workbooks local.** Only the synthetic `tableau/sample_data/` may go to Tableau Public.

## Suggested sheets
KPI tiles (from `kpis.csv`), CAE 1 vs CAE 2 bars, subject heatmap (Semester x Subject, colour = Final %), semester trend line with SGPA, grade distribution, attendance vs minimum, prediction vs actual (when available).

## Calculated fields
- Improvement: `[CAE 2] - [CAE 1]` (already in `subject_summary.csv`)
- Internal to exam gap: `[Exam] - [Int_eff]`
- Centum: `IF [Marks] = [Maximum_Marks] THEN 1 ELSE 0 END` on `marks_long.csv`
- Arrear flag: `[Grade] = "RA"`
Percentages are already normalised in `Pct`, so CAE/50, lab/25 and exam/50 compare fairly.
