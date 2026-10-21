# Tracker

Checks a data source, detects new or changed marks, logs them in `data/private/marks_history.csv`
and updates `data/private/marks.csv`, which the dashboards read automatically.

| File | Purpose |
|---|---|
| `tracker.py` | run once or on a schedule; change detection and history |
| `adapters/fake.py` | test source (needs no login) |
| `adapters/sist_erp.py` | real SIST ERP: login and term list work; marks endpoints still to fill in |

## Try it without the ERP
```
python -m tracker.tracker --adapter fake      # run 3 times: first load, then new CAE 2, then a corrected mark
```

## Real ERP
Local use only, with your own login (password typed at runtime, never saved). Needs SIST's permission.
Once the marks endpoints are captured, put their paths in `MARKS_CALLS` in `adapters/sist_erp.py` and add the mapper.

## Windows scheduling (later)
Task Scheduler can run `python -m tracker.tracker --adapter sist` every few hours, but the real adapter asks for a
password, so unattended runs need a safe secret store. Decide that after the endpoints work.

## Rules
Never log or save tokens, passwords or raw ERP responses. Poll at most every 30 minutes.

## Alerts
`python -m tracker.tracker --adapter sist --notify desktop telegram email`
Put Telegram or SMTP details in `.env` (copy `.env.example`, never commit it). Desktop alerts use `plyer` if installed, otherwise a Windows balloon.

## Attendance and timetable (ERP fetch pending)
The dashboard already shows both from `data/private/attendance.csv` and `data/private/timetable.csv`
(columns in `data/sample/sample_attendance.csv` and `sample_timetable.csv`). To fetch them automatically, capture the
attendance and timetable pages with the HAR method (`tools/har_to_endpoints.py`) and send me the cleaned `endpoints.json`.
