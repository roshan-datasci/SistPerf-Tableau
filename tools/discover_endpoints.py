"""Find which ERP API calls load your marks. Nothing is typed into this script and no secrets are recorded.

NOTE: Cloudflare may reject an automation-launched browser ("Verification failed"). If so, use tools/har_to_endpoints.py instead.

Setup (once):   pip install playwright
Run:            python tools/discover_endpoints.py

What happens:
  1. Chrome opens. YOU log in to the ERP yourself (Cloudflare check included). The script never sees your password.
  2. Click through the pages that show marks: the semester sections, "My CAE Result", "Semester Result".
  3. Close the Chrome window when done. Results are saved to captures/endpoints.json (git-ignored).

It records ONLY: the URL path, which fields the request sends (names, never values), and a cleaned sample of the
response. It never records headers, cookies, tokens or the login call. Personal fields are blanked, and anything you
enter at the name prompt is removed everywhere. READ captures/endpoints.json before sharing it.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sanitize_json import walk

SKIP = ("/login", "collect", "getMarqueeNotifications", "dropdown", "getalljobs", "AllUserLogoutTimeUpdate",
        "HallticketSettings", "Sibiling", "MasterStudent/view", "logout", "Logout")
OUT = "captures/endpoints.json"

def type_shape(o):
    if isinstance(o, dict):
        return {k: type_shape(v) for k, v in o.items()}
    if isinstance(o, list):
        return [type_shape(o[0])] if o else []
    return type(o).__name__

def record(store, url, method, post_data, resp_json, extras):
    path = url.split("/erp/api/", 1)[-1].split("?")[0]
    if any(s in url for s in SKIP) or path in store:
        return False
    try:
        body = json.loads(post_data) if post_data else None
    except Exception:
        body = None
    store[path] = {"method": method,
                   "request_fields": type_shape(body) if body is not None else None,   # names and types only
                   "response_sample": walk(resp_json, extras, 2, False)}
    return True

def save(store):
    os.makedirs("captures", exist_ok=True)
    json.dump(store, open(OUT, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

def main():
    from playwright.sync_api import sync_playwright
    raw = input("Your name and register number, comma separated (only used to remove them from the output): ")
    extras = [x.strip() for x in raw.split(",") if x.strip()]
    store = {}
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome", headless=False)
        except Exception:
            browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        def on_response(r):
            if "/erp/api/" not in r.url or r.request.method not in ("POST", "GET"):
                return
            try:
                data = r.json()
            except Exception:
                return
            if record(store, r.url, r.request.method, r.request.post_data, data, extras):
                print("captured:", r.url.split("/erp/api/", 1)[-1].split("?")[0])
                save(store)

        page.on("response", on_response)
        page.goto("https://erp.sathyabama.ac.in")
        print("Log in in the Chrome window, open the marks pages, then close the window.")
        try:
            while not page.is_closed():
                page.wait_for_timeout(500)
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass
    save(store)
    print(f"\nSaved {len(store)} endpoints to {OUT}. Open it and READ it before sharing.")

if __name__ == "__main__":
    main()
