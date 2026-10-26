# Tracker

Checks a data source, detects new or changed marks, logs them in `data/private/marks_history.csv`
and updates `data/private/marks.csv`, which Tableau reads automatically.

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

## Real marks without a scripted login (recommended now)
The ERP changed its login (the old `MasterStudent/login` call returns 404 and browsers pass a Cloudflare check). So:
1. Log in to the ERP in your normal Chrome. F12 > Network > tick Preserve log > Fetch/XHR.
2. Click each semester section, then the My CAE Result tile and pick each semester.
3. Network > download arrow > Export HAR (sanitized) > save as erp.har in the project folder.
4. `python -m tracker.tracker --adapter har --har erp.har --delete-har [--notify desktop]`
New and changed marks are logged to data/private/marks_history.csv and Tableau reads data/private/marks.csv.

## Automatic fetch through your own logged-in Chrome (best option now)
1. `pip install playwright`  (it attaches to your Chrome; no extra browser download)
2. `python tools/open_erp_chrome.py`  -> log in to the ERP yourself, wait for the student page.
3. `python -m tracker.tracker --adapter browser [--notify desktop]`  -> marks for every term go to data/private/marks.csv.
Close that Chrome window afterwards. Repeat step 3 any time (the Chrome window must still be logged in).
Nothing types a password or bypasses the Cloudflare check.
