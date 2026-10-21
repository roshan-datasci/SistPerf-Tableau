# SistPerf-Tableau

Academic performance analytics and live mark tracking for **Sathyabama Institute of Science and Technology (SIST)** students. Python backend + Streamlit dashboard + Tableau export.

> All demo data is **synthetic**. Real marks, passwords and tokens never go in this repo. Everything runs on your own computer.

## Features
| Feature | Status |
|---|---|
| Marks dashboard: averages, CAE vs Internal vs Exam, heatmap, trends, centums, consistency | Working |
| SIST rules: 50/50 internal-exam, RA if exam < 30% or total < 50%, A++ to RA grades, SGPA/CGPA, degree class | Working (`docs/regulations.md`) |
| Arrear-risk check, exam mark needed per grade, what-if and target planners (SGPA and CGPA) | Working |
| Eligibility checks (5.0 CGPA degree minimum; 6.0 and no arrears for outside exposure) | Working |
| Attendance: percent, classes you can still miss, classes needed to recover | Working on CSV/sample data; ERP fetch pending capture |
| Timetable and today's classes | Working on CSV/sample data; ERP fetch pending capture |
| Excel and PDF progress report | Working |
| Tableau export (CSVs, optional `.hyper`) | Working (`docs/tableau-guide.md`) |
| Experimental exam prediction vs a simple baseline | Working on pooled synthetic data |
| Automatic fetch of marks from the SIST ERP, change detection, history | Login, terms and results mapped; CAE mapping needs one probe run |
| Alerts (desktop, Telegram, email) on new or changed marks | Built; real delivery untested |

## Quick start
```
pip install -r requirements.txt
python scripts/make_sample_sist.py && python scripts/make_sample_extra.py
streamlit run app.py
```
Real data: `python -m tracker.tracker --adapter sist` (asks for your register number and password, hidden, never saved) writes `data/private/marks.csv`, which the app reads automatically. Check that SIST permits automated access to your own data first.

## Layout
`data_pipeline/` extract-validate-transform | `analytics/` metrics, attendance, prediction, report | `tracker/` ERP adapter, change detection, alerts | `tools/` sanitizer and endpoint finder | `scripts/` sample data and Tableau export | `docs/` regulations, data dictionary, security, Tableau guide

## Privacy
No passwords, cookies, `.env`, raw ERP responses, HAR files or real-data extracts are committed. See `docs/security.md`. Predictions and credit-based GPA figures are estimates; marks and rules come from the ERP and the regulations.
