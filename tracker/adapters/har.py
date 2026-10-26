"""Read marks from a HAR file exported by YOUR OWN logged-in Chrome. No login, no password, no scripting of the ERP.

Only these two calls are read, and only their request fields (year, term id, semester) and marks:
  ResultMark/studentResult   and   CAEResult/studentCAEResult
Headers, cookies and tokens in the HAR are never read. The register number in the request is ignored.
"""
import base64, json
from tracker.adapters.base import Adapter
from tracker.adapters import sist_erp as S

MONTH = {1: "APR-MAY", 2: "OCT-NOV"}   # AcademicMonthId, as in the ERP term list

class HarAdapter(Adapter):
    def __init__(self, path):
        self.path = path

    def fetch(self):
        har = json.load(open(self.path, encoding="utf-8"))
        rows, calls = [], 0
        for e in har.get("log", {}).get("entries", []):
            url = e.get("request", {}).get("url", "")
            kind = "result" if "ResultMark/studentResult" in url else "cae" if "CAEResult/studentCAEResult" in url else None
            if not kind:
                continue
            try:
                body = json.loads(e["request"]["postData"]["text"])
                c = e["response"].get("content", {}); txt = c.get("text")
                if c.get("encoding") == "base64":
                    txt = base64.b64decode(txt).decode("utf-8", "replace")
                data = json.loads(txt)
            except Exception:
                continue
            term = {"Academic_Year": body["AcademicYear"], "Term": MONTH.get(body.get("AcademicMonthId"), str(body.get("AcademicMonthId"))),
                    "Semester": body["Semester"]}
            rd = data.get("responseData") or {}
            calls += 1
            if kind == "result":
                rows += S.map_results(S._rows(rd.get("SemResult") if isinstance(rd, dict) else []), term)
            else:
                for key, grp in S._groups(rd):
                    rows += S.map_cae(grp, term, hint=key)
        if not calls:
            raise ValueError("No marks requests found in the HAR. Open each semester section and the My CAE Result page "
                             "(choose each semester) in Chrome before exporting.")
        return rows
