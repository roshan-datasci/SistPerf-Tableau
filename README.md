# SistPerf-Tableau

A **Tableau** dashboard for Sathyabama Institute of Science and Technology (SIST) students, fed by your actual ERP marks. Python only fetches the marks and prepares the data; Tableau does all calculations and visualisation.

> Demo data is **synthetic**. Real marks, passwords and tokens never go in this repo. Everything runs on your own computer.

## How it works
1. `tools/open_erp_chrome.py` opens your Chrome. You log in to the ERP yourself.
2. `python -m tracker.tracker --adapter browser --export-tableau` reads your marks from that session, keeps a change history, and writes Tableau-ready data.
3. `python scripts/build_tableau_workbook.py` generates `tableau/SistPerf_Live.twbx` (6 dashboards, 18 sheets, all calculated fields, built-in extract). Open it in Tableau Desktop Public Edition.
4. After new marks: repeat step 2, then Data > marks_long > Refresh Extract in Tableau.

See `docs/tableau.md` for the dashboards, fields and rules.

## Layout
`tracker/` ERP fetch, change detection, alerts | `scripts/` Tableau data export and workbook generator | `data_pipeline/` validation | `data/curriculum_r2023_cse_ds.csv` credits and maxima | `tableau/` workbooks and demo data | `tools/` helpers | `docs/`

## Privacy
No passwords, cookies, `.env`, raw ERP responses, HAR files or real-data workbooks are committed (see `docs/security.md`). Use Tableau Public only for the synthetic demo workbook.

Educational and portfolio project. Planned later: attendance dashboard, what-if calculator, prediction versus actual.
