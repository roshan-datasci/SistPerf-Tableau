"""Turn a table copied from the SIST ERP into SistPerf CSV rows (no login, no scraping).

1. In the ERP, select a marks table (drag from its first row to its last), Ctrl+C.
2. Run, from the project folder (the table is read from your clipboard):

   CAE table of a term:
     python tools/import_pasted.py cae --year 2026-2027 --term OCT-NOV --semester 3

   Semester result table (Examination / Internal / Total columns):
     python tools/import_pasted.py result --year 2025-2026 --term APR-MAY --semester 2

   Or read from a text file instead of the clipboard:  ... --file table.txt

Rows are merged into data/private/marks.csv (git-ignored). Re-importing a table updates it.
Maximum marks are NOT shown for past terms, so they are assumed: 50 + 50 for theory and
25 + 25 for subjects with "Lab" in the title. Change with --max-internal / --max-exam.
"""
import argparse, re, sys, os
from datetime import date
import pandas as pd

KEY = ["Student_ID", "Semester", "Subject_Code", "Assessment"]
CAE_RE = re.compile(r"^(\d+)\s+(\S+)\s+(.+?)\s+(\d+)\s+(\d+)\s+(\d+(?:\.\d+)?)\s+(\w+)$")
RES_RE = re.compile(r"^(\d+)\s+(\S+)\s+(.+?)\s+(\d+)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)\s+(\w+)$")

def read_text(path):
    if path:
        return open(path, encoding="utf-8").read()
    import tkinter
    r = tkinter.Tk(); r.withdraw(); t = r.clipboard_get(); r.destroy(); return t

def join_wrapped(text):
    """Copied cells can wrap onto extra lines; glue lines that do not start with a serial number."""
    out = []
    for ln in (re.sub(r"[\t ]+", " ", l).strip() for l in text.splitlines()):
        if not ln:
            continue
        if re.match(r"^\d+ ", ln) or not out:
            out.append(ln)
        else:
            out[-1] += " " + ln
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["cae", "result"])
    ap.add_argument("--year", required=True); ap.add_argument("--term", required=True); ap.add_argument("--semester", type=int, required=True)
    ap.add_argument("--student-id", default="ME"); ap.add_argument("--file")
    ap.add_argument("--max-cae", type=float, default=50)
    ap.add_argument("--max-internal", type=float, default=50); ap.add_argument("--max-exam", type=float, default=50)
    ap.add_argument("--out", default="data/private/marks.csv")
    a = ap.parse_args()
    rows, skipped = [], []
    for ln in join_wrapped(read_text(a.file)):
        if a.kind == "cae":
            m = CAE_RE.match(ln)
            if not m:
                if not re.search(r"S\.?No|Subject", ln): skipped.append(ln)
                continue
            _, code, title, n, mx, ob, _res = m.groups()
            rows.append([code, title, f"CAE {n}", float(ob), float(mx)])
        else:
            m = RES_RE.match(ln)
            if not m:
                if not re.search(r"S\.?No|Subject|Marks", ln): skipped.append(ln)
                continue
            _, code, title, sem, ex, it, tot, _res = m.groups()
            lab = "lab" in title.lower()
            mi, me = (a.max_internal / 2, a.max_exam / 2) if lab else (a.max_internal, a.max_exam)
            if abs(float(ex) + float(it) - float(tot)) > 0.01:
                print(f"WARNING {code}: exam + internal != total"); 
            if float(ex) > me or float(it) > mi:
                print(f"WARNING {code}: a mark is above the assumed maximum ({me:g}/{mi:g}); use --max-exam / --max-internal")
            rows += [[code, title, "Internal", float(it), mi], [code, title, "Exam", float(ex), me]]
    if not rows:
        print("No marks rows recognised. Select the table body and copy again."); 
        for s in skipped[:5]: print("  skipped:", s[:80])
        sys.exit(1)
    new = pd.DataFrame(rows, columns=["Subject_Code", "Subject", "Assessment", "Marks", "Maximum_Marks"])
    new.insert(0, "Student_ID", a.student_id); new["Academic_Year"] = a.year; new["Term"] = a.term
    new["Semester"] = a.semester; new["Date"] = date.today().isoformat()   # import date, not the exam date
    cols = ["Student_ID", "Academic_Year", "Term", "Semester", "Subject_Code", "Subject", "Assessment", "Marks", "Maximum_Marks", "Date"]
    new = new[cols]
    if os.path.exists(a.out):
        old = pd.read_csv(a.out); new = pd.concat([old, new]).drop_duplicates(KEY, keep="last")
    os.makedirs(os.path.dirname(a.out), exist_ok=True); new.to_csv(a.out, index=False)
    print(f"Imported {len(rows)} rows ({len(skipped)} lines skipped). Saved to {a.out}")
    for s in skipped[:5]: print("  skipped:", s[:80])

if __name__ == "__main__":
    main()
