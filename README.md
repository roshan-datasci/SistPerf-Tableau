# SistPerf-Tableau

Academic performance analytics and live mark tracking for **Sathyabama Institute of Science and Technology (SIST)** students, built with **Tableau** and a **Python** backend.

> Status: planning and setup. All demo data is **synthetic**. Real marks and credentials never go in this repo.

## What it will do
- Track CAE 1, CAE 2 and semester marks across subjects and semesters
- Dashboards: overview, CAE comparison, subject heatmap, consistency, centums, SGPA/CGPA, what-if, prediction
- Backend that checks an authorised data source on a schedule, detects new or changed marks and refreshes the Tableau data
- Experimental prediction of semester exam marks, compared against a simple baseline

## How it fits together
```
Authorised source (manual export / SIST ERP adapter)
  -> Python: extract -> validate -> transform -> change detection
  -> data/private/*.csv / *.hyper   (git-ignored)
  -> Tableau dashboards   (+ optional Streamlit app)
```

## Repository layout
| Folder | Purpose |
|---|---|
| `data/sample/` | Synthetic demo data (safe to publish) |
| `data/private/` | Real data. **Git-ignored** |
| `data_pipeline/` | extract, validate, transform |
| `analytics/` | metrics and prediction |
| `tracker/` | scheduled fetch, change history, alerts |
| `tools/` | helper scripts, e.g. `sanitize_json.py` to strip personal data before sharing a response |
| `tableau/` | workbooks and Tableau notes |
| `notebooks/` | exploration |
| `docs/` | architecture, data dictionary, security |

## Scope
Built for SIST students. Grading rules in `config.yaml` should follow the SIST scheme, and the ERP adapter targets the SIST student portal. It only runs locally with your own login, and only if the university permits automated access.

## Data format
`Student_ID, Academic_Year, Semester, Subject, Assessment, Marks, Maximum_Marks, Date`
Assessment is `CAE 1`, `CAE 2` or `Semester`.

## Privacy
No passwords, cookies, `.env` files, private exports or real-data Tableau extracts are committed. See `docs/security.md`.

## Roadmap
1 Repo setup, 2 Synthetic data, 3 Python processing, 4 EDA, 5 Tableau dashboards, 6 Prediction, 7 Advanced analytics, 8 Authorised data integration, 9 Final portfolio.

Educational and portfolio project. Predictions are estimates, not guarantees.
