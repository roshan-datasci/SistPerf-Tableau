"""Find your marks endpoints from a HAR file exported by your NORMAL Chrome (no automation, no Cloudflare problem).

1. Log in to the ERP in normal Chrome, F12 > Network, tick "Preserve log", pick Fetch/XHR.
2. Open the marks pages (each semester section, "My CAE Result", "Semester Result").
3. Network tab > download arrow > "Export HAR (sanitized)...". Save as erp.har in this folder.
4. python tools/har_to_endpoints.py erp.har --extra "YOUR NAME" "YOUR REGISTER NO" --delete
5. READ captures/endpoints.json, then share it.

Kept: URL path, request field NAMES with cleaned values (personal ids blanked), cleaned response samples.
Never read or written: headers, cookies, tokens, the login call. --delete removes the HAR afterwards.
Needs tools/sanitize_json.py next to this file. Never commit or share the HAR.
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sanitize_json import walk

SKIP = ("login", "collect", "getMarqueeNotifications", "dropdown", "getalljobs", "AllUserLogoutTimeUpdate",
        "HallticketSettings", "Sibiling", "MasterStudent/view", "ogout", "challenges")
OUT, MAX_CALLS = "captures/endpoints.json", 6

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("har"); ap.add_argument("--extra", nargs="*", default=[]); ap.add_argument("--delete", action="store_true")
    a = ap.parse_args()
    har = json.load(open(a.har, encoding="utf-8"))
    store = {}
    for e in har.get("log", {}).get("entries", []):
        req, resp = e.get("request", {}), e.get("response", {})
        url = req.get("url", "")
        if "/erp/api/" not in url or any(s in url for s in SKIP):
            continue
        txt = (resp.get("content") or {}).get("text")
        try:
            data = json.loads(txt)
        except Exception:
            continue
        path = url.split("/erp/api/", 1)[-1].split("?")[0]
        try:
            body = json.loads((req.get("postData") or {}).get("text") or "null")
        except Exception:
            body = None
        call = {"request": walk(body, a.extra, 3, False) if body is not None else None,
                "response_sample": walk(data, a.extra, 2, False)}
        entry = store.setdefault(path, {"method": req.get("method", "POST"), "calls": []})
        if call["request"] not in [c["request"] for c in entry["calls"]] and len(entry["calls"]) < MAX_CALLS:
            entry["calls"].append(call)
    os.makedirs("captures", exist_ok=True)
    json.dump(store, open(OUT, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    for p, v in store.items():
        print(f"captured: {p}  ({len(v['calls'])} different call(s))")
    print(f"\nSaved {len(store)} endpoints to {OUT}. READ it before sharing.")
    if a.delete:
        os.remove(a.har); print("Deleted", a.har)

if __name__ == "__main__":
    main()
