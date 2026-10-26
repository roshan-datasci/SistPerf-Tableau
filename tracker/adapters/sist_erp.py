"""SIST ERP adapter. Runs on YOUR computer with YOUR login. Needs permission from SIST.

- Login and term list work like your events app (MasterStudent/login, MasterStudent/view).
- Semester results: ResultMark/studentResult (InternalMark / ExternalMark / TotalMark per subject).
- CAE marks: CAEResult/studentCAEResult. Its row shape was not captured yet, so the mapper accepts several
  field names and, if it cannot find them, stops and lists the FIELD NAMES it saw (never values).
Never print, log or save the token, the password or raw responses.
Maximum marks are not in the data: assumed 50 internal + 50 exam, or 25 + 25 when the title contains "Lab".
"""
import getpass, json, os, re, ssl, sys, time, urllib.error, urllib.request
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

def ask_password(prompt="ERP password: "):
    """Hidden input that shows one * per key on Windows, so you can see that typing works. Never stored."""
    if os.name != "nt":
        return getpass.getpass(prompt)
    import msvcrt
    sys.stdout.write(prompt); sys.stdout.flush()
    chars = []
    while True:
        ch = msvcrt.getwch()
        if ch in ("\r", "\n"):
            sys.stdout.write("\n"); break
        if ch == "\x03":
            raise KeyboardInterrupt
        if ch in ("\b", "\x7f"):
            if chars:
                chars.pop(); sys.stdout.write("\b \b")
        elif ch in ("\x00", "\xe0"):
            msvcrt.getwch()          # arrow/function keys: ignore
        else:
            chars.append(ch); sys.stdout.write("*")
        sys.stdout.flush()
    return "".join(chars)

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
                    Subject_Code=it["SubjectCode"], Subject=title, Maximum_Marks=mx, Date=date.today().isoformat(),
                    Result=it.get("Result"), ERP_Total=_num(it["TotalMark"]) if it.get("TotalMark") not in (None, "") else None,
                    Max_Is_Assumed=1)   # the ERP does not send maximum marks for results
        for assess, key in (("Internal", "InternalMark"), ("Exam", "ExternalMark")):
            if it.get(key) not in (None, ""):
                out.append({**base, "Assessment": assess, "Marks": _num(it[key])})
    return out

CAE_DEFAULT_MAX = 50.0   # regulation 14: each CAE is out of 50. The ERP rows carry no maximum field.

def map_cae(items, term, student="ME", hint=""):
    out = []
    for it in items:
        vals = {k: _pick(it, v) for k, v in CAE_FIELDS.items()}
        if vals["cae"] is None and re.search(r"\d+", hint or ""):
            vals["cae"] = hint
        missing = [k for k in ("code", "cae", "obt") if vals[k] is None]
        if missing:
            raise MapperError(f"Could not find {missing} in a CAE row. Fields present: {sorted(it.keys())}. "
                              "Send me this list (names only) so I can map it.")
        n = re.search(r"\d+", str(vals["cae"]))
        try:
            obt = _num(vals["obt"])
        except ValueError:
            continue                      # absent / not a number: no mark to record
        if not n:
            continue                      # not a numbered CAE (e.g. an assignment row)
        mx = _num(vals["max"]) if vals["max"] is not None else CAE_DEFAULT_MAX
        if obt > mx:
            mx = 100.0                    # a mark above the assumed maximum: the paper must have been out of 100
        out.append(dict(Student_ID=student, Academic_Year=term["Academic_Year"], Term=term["Term"], Semester=term["Semester"],
                        Subject_Code=vals["code"], Subject=vals["title"] or vals["code"], Assessment=f"CAE {n.group()}",
                        Marks=obt, Maximum_Marks=mx, Date=date.today().isoformat(), Result=it.get("Result"), ERP_Total=None,
                        Max_Is_Assumed=0 if vals["max"] is not None else 1))
    return out

class SistErpAdapter(Adapter):
    def __init__(self, register_number=None):
        self.reg = register_number or input("Register number: ").strip()
        self._pw = ask_password("ERP password (shown as ****, not saved): ")
        self.token, self.student_id = None, None

    def _post(self, endpoint, body):
        headers = {"Content-Type": "application/json", "Accept": "application/json",
                   "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36",
                   "Origin": "https://erp.sathyabama.ac.in", "Referer": "https://erp.sathyabama.ac.in/student/view"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        last = ""
        for attempt in range(3):
            try:
                req = urllib.request.Request(f"{BASE}/{endpoint}", json.dumps(body).encode(), headers, method="POST")
                with urllib.request.urlopen(req, timeout=15, context=ssl.create_default_context()) as r:
                    return json.loads(r.read().decode("utf-8", "replace"))
            except urllib.error.HTTPError as e:
                msg = ""
                try:
                    msg = str(json.loads(e.read().decode("utf-8", "replace")).get("message", ""))[:120]
                except Exception:
                    pass
                last = f"HTTP {e.code}" + (f" - {msg}" if msg else "")
                if e.code in (401, 403):
                    raise ErpError(f"ERP rejected the request ({last}). Wrong password, or the ERP now blocks scripted logins (e.g. Cloudflare).")
                if 400 <= e.code < 500 and e.code != 429:
                    raise ErpError(f"ERP answered {last} for '{endpoint}'. The endpoint or request format may have changed.")
                time.sleep(2 * (attempt + 1))
            except (urllib.error.URLError, TimeoutError) as e:
                last = f"{type(e).__name__}: {getattr(e, 'reason', e)}"
                time.sleep(2 * (attempt + 1))
        raise ErpError(f"ERP unreachable ({last}).")

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
