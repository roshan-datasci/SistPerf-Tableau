"""Fetch marks, detect new/changed ones, keep a history, refresh the data the dashboards read.

  python -m tracker.tracker --adapter fake            # test run (run it 3 times to see changes)
  python -m tracker.tracker --adapter browser         # real marks via the Chrome you logged in to (tools/open_erp_chrome.py)
  python -m tracker.tracker --adapter har --har erp.har   # real marks from an exported HAR
  python -m tracker.tracker --adapter sist --every 180   # repeat every 3 hours (minimum 30)
"""
import argparse, os, random, time
from datetime import datetime
import pandas as pd
from data_pipeline.validate import validate

KEY = ["Student_ID", "Semester", "Subject_Code", "Assessment"]
STORE, HISTORY = "data/private/marks.csv", "data/private/marks_history.csv"

def run_once(adapter, store=STORE, history=HISTORY):
    raw = pd.DataFrame(adapter.fetch())
    new, issues = validate(raw)
    bad = int(issues[issues["Check"] != "Completeness (valid rows %)"]["Count"].sum())
    if bad:
        print(f"{bad} invalid rows were skipped (see data quality checks).")
    old = pd.read_csv(store) if os.path.exists(store) else pd.DataFrame(columns=new.columns)
    m = new.merge(old[KEY + ["Marks", "Maximum_Marks", "Date"]], on=KEY, how="left", suffixes=("", "_old"))
    added = m[m["Marks_old"].isna()]
    changed = m[m["Marks_old"].notna() & ((m["Marks"] != m["Marks_old"]) | (m["Maximum_Marks"] != m["Maximum_Marks_old"]))]
    now = datetime.now().isoformat(timespec="seconds")
    events = [(now, "NEW", r) for _, r in added.iterrows()] + [(now, "CHANGED", r) for _, r in changed.iterrows()]
    ev = []
    if events:
        h = pd.DataFrame([{"Time": t, "Event": e, "Semester": r["Semester"], "Subject_Code": r["Subject_Code"], "Subject": r["Subject"],
                           "Assessment": r["Assessment"], "Old": r.get("Marks_old"), "New": r["Marks"], "Maximum": r["Maximum_Marks"]} for t, e, r in events])
        ev = h.to_dict("records")
        os.makedirs(os.path.dirname(history), exist_ok=True)
        h.to_csv(history, mode="a", header=not os.path.exists(history), index=False)
        for t, e, r in events:
            old_txt = f"{r['Marks_old']:g} -> " if e == "CHANGED" else ""
            print(f"[{e}] Sem {r['Semester']} · {r['Subject']} · {r['Assessment']}: {old_txt}{r['Marks']:g}/{r['Maximum_Marks']:g}")
    else:
        print("No new or changed marks.")
    same = m["Marks_old"].notna() & (m["Marks"] == m["Marks_old"]) & (m["Maximum_Marks"] == m["Maximum_Marks_old"])
    new = new.copy(); new["Date"] = m["Date"].where(~same, m["Date_old"]).values   # keep the first-seen date of unchanged marks
    final = pd.concat([x for x in (old, new) if len(x)]).drop_duplicates(KEY, keep="last")
    os.makedirs(os.path.dirname(store), exist_ok=True); final.to_csv(store, index=False)
    return len(added), len(changed), ev

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", choices=["fake", "browser", "har", "sist"], default="fake")
    ap.add_argument("--har", help="HAR file exported from your own logged-in Chrome (with --adapter har)")
    ap.add_argument("--delete-har", action="store_true", help="delete the HAR file after importing it")
    ap.add_argument("--every", type=int, help="minutes between checks (minimum 30)")
    ap.add_argument("--notify", nargs="*", choices=["desktop", "telegram", "email"], default=[], help="alert channels for new/changed marks")
    ap.add_argument("--export-tableau", action="store_true", help="after fetching, rewrite the Tableau data files (data/private/tableau/)")
    ap.add_argument("--probe", action="store_true", help="show CAE response field names (sist adapter) and exit")
    a = ap.parse_args()
    if a.adapter == "fake":
        from tracker.adapters.fake import FakeAdapter; ad = FakeAdapter()
    elif a.adapter == "browser":
        from tracker.adapters.browser import BrowserAdapter; ad = BrowserAdapter()
    elif a.adapter == "har":
        if not a.har or not os.path.exists(a.har):
            print("Give an existing HAR file: --har erp.har"); return
        from tracker.adapters.har import HarAdapter; ad = HarAdapter(a.har)
    else:
        from tracker.adapters.sist_erp import SistErpAdapter; ad = SistErpAdapter()
    if a.probe:
        import json; print(json.dumps(ad.probe(), indent=2)); return
    while True:
        try:
            res = run_once(ad)
            if a.export_tableau:
                from scripts import export_for_tableau as TX
                TX.run()
            if a.notify and res[2]:
                from tracker import notify
                for ch, r in notify.send(notify.format_events(res[2]), a.notify).items():
                    print(f"alert via {ch}: {r}")
        except (NotImplementedError, ValueError) as e:
            print(e); break
        except Exception as e:
            print("Check failed:", e)
        if a.adapter == "har":
            if a.delete_har:
                os.remove(a.har); print("Deleted", a.har)
            break
        if not a.every:
            break
        time.sleep(max(a.every, 30) * 60 + random.randint(0, 120))   # polite, jittered polling

if __name__ == "__main__":
    main()
