"""Reads your marks through the Chrome window YOU logged in to (started with tools/open_erp_chrome.py).

How: attach to that Chrome, reload the ERP page, note which marks requests the page itself makes (and the session headers
it uses, kept in memory only), then ask the same two marks endpoints for every term from inside the page.
It never types or stores a password, never solves or bypasses the Cloudflare check, reads only your own marks, and waits
1 second between calls. Needs:  pip install playwright   (no extra browser download: it attaches to your Chrome)."""
import json, time
from tracker.adapters.base import Adapter
from tracker.adapters import sist_erp as S
from tracker.adapters.har import MONTH

BASE = "https://erp.sathyabama.ac.in/erp/api/v1.0/"
AUTH_HEADERS = ("authorization", "access-token", "token")
JS_PROFILE = """async ({url, headers, body}) => {
  const r = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json', 'Accept': 'application/json', ...headers}, body: JSON.stringify(body)});
  const d = await r.json(); const rd = d.responseData || {}; const si = (rd.StudentInfo || [])[0] || {};
  return {reg: si.RegisterNumber, terms: (rd.studentAcademic || []).map(t => ({AcademicYear: t.AcademicYear, AcademicMonthId: t.AcademicMonthId, Semester: t.Semester}))}; }"""
JS = """async ({url, headers, body}) => {
  const r = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json', 'Accept': 'application/json', ...headers}, body: JSON.stringify(body)});
  return await r.json(); }"""

class BrowserAdapter(Adapter):
    def __init__(self, port=9222):
        self.port = port

    def fetch(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise ValueError("Run:  pip install playwright")
        with sync_playwright() as p:
            try:
                browser = p.chromium.connect_over_cdp(f"http://localhost:{self.port}")
            except Exception:
                raise ValueError("Could not reach Chrome. Run  python tools/open_erp_chrome.py  first, log in, then try again.")
            page = next((pg for c in browser.contexts for pg in c.pages if "erp.sathyabama.ac.in" in pg.url and "login" not in pg.url), None)
            if page is None:
                raise ValueError("No logged-in ERP tab found. Log in in the Chrome window that was opened, then try again.")
            return self.collect(page)

    def collect(self, page):
        seen = {"headers": {}, "terms": {}}
        profile_body = None
        reqs = []

        def on_req(r):          # only record here: Playwright cannot answer questions while it is dispatching an event
            if "/erp/api/" in r.url:
                reqs.append(r)

        page.on("request", on_req)
        page.reload(); page.wait_for_load_state("networkidle"); page.wait_for_timeout(3000)
        page.remove_listener("request", on_req)
        for r in reqs:
            if not seen["headers"]:
                h = r.headers
                if not any(h.get(k) for k in AUTH_HEADERS):
                    try:
                        h = r.all_headers()
                    except Exception:
                        pass
                for k in AUTH_HEADERS:
                    if h.get(k):
                        seen["headers"][k] = h[k]
            if "MasterStudent/view" in r.url and profile_body is None:
                try:
                    pb = json.loads(r.post_data or "{}")
                    if "StudentId" in pb:
                        profile_body = pb
                except Exception:
                    pass
            if "studentResult" in r.url or "studentCAEResult" in r.url:
                try:
                    b = json.loads(r.post_data or "{}")
                except Exception:
                    continue
                if {"AcademicYear", "AcademicMonthId", "Semester"} <= set(b):
                    seen["terms"][(b["AcademicYear"], b["AcademicMonthId"], b["Semester"])] = b
        if not seen["headers"]:
            raise ValueError("Could not see the page's session headers. Press F5 in the Chrome window (student page, logged in), then run again.")
        if profile_body:      # only the register number and term list leave the page; the rest of the profile is discarded in the browser
            try:
                info = page.evaluate(JS_PROFILE, {"url": BASE + "MasterStudent/view", "headers": seen["headers"], "body": profile_body})
            except Exception:
                info = {}
            for t in info.get("terms") or []:
                if info.get("reg") and t.get("AcademicYear"):
                    seen["terms"].setdefault((t["AcademicYear"], t["AcademicMonthId"], t["Semester"]),
                                             {"RegisterNumber": info["reg"], "AcademicYear": t["AcademicYear"],
                                              "AcademicMonthId": t["AcademicMonthId"], "Semester": t["Semester"]})
        if not seen["terms"]:
            raise ValueError("Could not read your term list from the ERP. Make sure you are logged in on the student page "
                             "(erp.sathyabama.ac.in/student/view), press F5 in that window, then run again.")
        rows = []
        for b in sorted(seen["terms"].values(), key=lambda x: x["Semester"]):
            term = {"Academic_Year": b["AcademicYear"], "Term": MONTH.get(b["AcademicMonthId"], str(b["AcademicMonthId"])), "Semester": b["Semester"]}
            for ep, kind in ((S.RES_EP, "result"), (S.CAE_EP, "cae")):
                try:
                    data = page.evaluate(JS, {"url": BASE + ep, "headers": seen["headers"], "body": b})
                except Exception as e:
                    raise ValueError(f"The ERP did not answer {ep} for Sem {b['Semester']} ({type(e).__name__}). Is the page still logged in?")
                rd = (data or {}).get("responseData") or {}
                if kind == "result":
                    rows += S.map_results(S._rows(rd.get("SemResult") if isinstance(rd, dict) else []), term)
                else:
                    for key, grp in S._groups(rd):
                        rows += S.map_cae(grp, term, hint=key)
                time.sleep(1)
        return rows
