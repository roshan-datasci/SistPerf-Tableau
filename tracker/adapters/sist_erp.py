"""SIST ERP adapter. Runs on YOUR computer with YOUR login. Needs permission from SIST.

- Login and term list work like your events app (MasterStudent/login, MasterStudent/view).
- Semester results: ResultMark/studentResult (InternalMark / ExternalMark / TotalMark per subject).
- CAE marks: CAEResult/studentCAEResult. Its row shape was not captured yet, so the mapper accepts several
  field names and, if it cannot find them, stops and lists the FIELD NAMES it saw (never values).
Never print, log or save the token, the password or raw responses.
Maximum marks are not in the data: assumed 50 internal + 50 exam, or 25 + 25 when the title contains "Lab".
"""
import getpass, json, re, ssl, time, urllib.error, urllib.request
from datetime import date
from tracker.adapters.base import Adapter

BASE = "https://erp.sathyabama.ac.in/erp/api/v1.0"
CAE_EP, RES_EP = "CAEResult/studentCAEResult", "ResultMark/studentResult"
CAE_FIELDS = {   # lower-case candidate names
    "code": ["subjectcode", "coursecode", "code"],
    "title": ["subjectname", "subjecttitle", "coursename", "coursetitle", "subject", "title"],
    "cae": ["caeno", "caenumber", "caeid", "caetype", "caename", "cae", "assessmentno", "assessment", "examno"],
    "max": ["maxmark", "maxmarks", "maximummark", "maximummarks", "maxscore", "outof", "max"],
    "obt": ["obtainedmark", "obtainedmarks", "markobtained", "obtained", "scoredmark", "mark", "marks", "score"],
}

class ErpError(Exception):
    pass

class MapperError(Exception):
    pass

def _pick(item, names):
    low = {k.lower(): v for k, v in item.items()}
    for n in names:
        if low.get(n) not in (None, ""):
            return low[n]
    return None

def _rows(rd):
    return [r for _, rows in _groups(rd) for r in rows]

def _groups(rd):
    """(key, rows) pairs. A response may hold one list or one list per CAE (e.g. a key containing the CAE number)."""
    if isinstance(rd, list):
        return [("", rd)]
    if isinstance(rd, dict):
        return [(k, v) for k, v in rd.items() if isinstance(v, list)]
    return []

def _num(x):
    return float(str(x).strip())

def map_results(items, term, student="ME"):
    """studentResult rows -> Internal and Exam rows."""
    out = []
    for it in items:
        title = it.get("SubjectName", "")
        vals = [float(it[k]) for k in ("InternalMark", "ExternalMark") if it.get(k) not in (None, "")]
        mx = 25.0 if "lab" in title.lower() and max(vals or [0]) <= 25 else 50.0   # a lab with a mark above 25 must be out of 50
        base = dict(Student_ID=student, Academic_Year=term["Academic_Year"], Term=term["Term"], Semester=term["Semester"],
                    Subject_Code=it["SubjectCode"], Subject=title, Maximum_Marks=mx, Date=date.today().isoformat())
        for assess, key in (("Internal", "InternalMark"), ("Exam", "ExternalMark")):
            if it.get(key) not in (None, ""):
                out.append({**base, "Assessment": assess, "Marks": _num(it[key])})
    return out

def map_cae(items, term, student="ME", hint=""):
    out = []
    for it in items:
        vals = {k: _pick(it, v) for k, v in CAE_FIELDS.items()}
        if vals["cae"] is None and re.search(r"\d+", hint or ""):
            vals["cae"] = hint
        missing = [k for k in ("code", "cae", "obt", "max") if vals[k] is None]
        if missing:
            raise MapperError(f"Could not find {missing} in a CAE row. Fields present: {sorted(it.keys())}. "
                              "Send me this list (names only) so I can map it.")
        n = re.search(r"\d+", str(vals["cae"]))
        if not n:
            raise MapperError(f"CAE number not understood. Fields present: {sorted(it.keys())}")
        out.append(dict(Student_ID=student, Academic_Year=term["Academic_Year"], Term=term["Term"], Semester=term["Semester"],
                        Subject_Code=vals["code"], Subject=vals["title"] or vals["code"], Assessment=f"CAE {n.group()}",
                        Marks=_num(vals["obt"]), Maximum_Marks=_num(vals["max"]), Date=date.today().isoformat()))
    return out

class SistErpAdapter(Adapter):
    def __init__(self, register_number=None):
        self.reg = register_number or input("Register number: ").strip()
        self._pw = getpass.getpass("ERP password (hidden, not saved): ")
        self.token, self.student_id = None, None

    def _post(self, endpoint, body):
        headers = {"Content-Type": "application/json", "Accept": "application/json",
                   "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36",
                   "Origin": "https://erp.sathyabama.ac.in", "Referer": "https://erp.sathyabama.ac.in/student/view"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        for attempt in range(3):
            try:
                req = urllib.request.Request(f"{BASE}/{endpoint}", json.dumps(body).encode(), headers, method="POST")
                with urllib.request.urlopen(req, timeout=15, context=ssl.create_default_context()) as r:
                    return json.loads(r.read().decode("utf-8", "replace"))
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    raise ErpError("ERP rejected the request (wrong password, or access blocked).")
                time.sleep(2 * (attempt + 1))
            except (urllib.error.URLError, TimeoutError):
                time.sleep(2 * (attempt + 1))
        raise ErpError("ERP unreachable right now. Try again later.")

    def login(self):
        d = self._post("MasterStudent/login", {"RegisterNumber": self.reg, "Password": self._pw})
        if d.get("status") is not True:
            raise ErpError("ERP login failed: " + str(d.get("message", "unknown")))
        obj = (d.get("responseData") or {}).get("login") or d.get("responseData") or {}
        self.token, self.student_id = obj.get("accessToken"), obj.get("StudentId")
        self._pw = None   # drop the password from memory
        if not self.token:
            raise ErpError("Login worked but no token was returned.")

    def terms(self):
        """Only term labels are kept from the profile; everything else in that response is discarded."""
        d = self._post("MasterStudent/view", {"StudentId": int(self.student_id)})
        return [{"Academic_Year": t["AcademicYear"], "Term": t["AcademicMonth"], "Semester": t["Semester"], "AcademicMonthId": t["AcademicMonthId"]}
                for t in (d.get("responseData") or {}).get("studentAcademic", [])]

    def _body(self, t):
        return {"RegisterNumber": self.reg, "AcademicMonthId": t["AcademicMonthId"], "AcademicYear": t["Academic_Year"], "Semester": t["Semester"]}

    def fetch(self):
        if self.token is None:
            self.login()
        rows = []
        for t in self.terms():
            res = self._post(RES_EP, self._body(t))
            rows += map_results(_rows((res.get("responseData") or {}).get("SemResult")), t)
            cae = self._post(CAE_EP, self._body(t))
            for key, grp in _groups(cae.get("responseData")):
                rows += map_cae(grp, t, hint=key)
            time.sleep(1)   # polite
        return rows

    def probe(self):
        """Field NAMES (and non-personal values) of CAE responses, for mapping. Run once."""
        from tools.sanitize_json import walk
        if self.token is None:
            self.login()
        out = {}
        for t in self.terms():
            r = self._post(CAE_EP, self._body(t))
            out[f"Sem {t['Semester']} {t['Academic_Year']} {t['Term']}"] = walk(r.get("responseData"), [self.reg], 2, False)
        return out
