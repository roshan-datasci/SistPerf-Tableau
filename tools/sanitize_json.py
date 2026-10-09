"""Strip personal data from a JSON response BEFORE you paste it anywhere.

Usage (Windows, from the project folder):
  1. Copy the response JSON (DevTools > Response > right-click > Copy).
  2. python tools/sanitize_json.py --extra "YOUR NAME" "YOUR REGISTER NO"
  3. The cleaned JSON is printed AND copied to your clipboard. Check it, then paste.

Other ways:
  python tools/sanitize_json.py response.json
  python tools/sanitize_json.py --max-items 2      # keep only first 2 rows of each list
  python tools/sanitize_json.py --keys-only        # show structure, no values at all

It is a safety net, not a guarantee. ALWAYS read the output before pasting.
"""
import argparse, json, re, sys

KEY_RE = re.compile(
    r"(pass|pwd|hash|token|secret|otp|aadh?a?a?r|\bpan\b|pan$|^pan|mobile|phone|contact|landline|fax|"
    r"e?mail|dob|birth|address|city|pincode|state|photo|image|url|attachment|certificate|"
    r"studentname|fathername|mothername|guardianname|middlename|^name$|referredby|"
    r"registernumber|rollnumber|studentid|admisisonid|admissionid|identityid|appno|applicationno|"
    r"income|medical|bloodgroup|religion|community|nationality|scholarship|room|hostel)", re.I)
VAL_PATTERNS = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "REDACTED_EMAIL"),
    (re.compile(r"https?://\S+"), "REDACTED_URL"),
    (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "REDACTED_PAN"),
    (re.compile(r"\b[0-9a-fA-F]{32,}\b"), "REDACTED_HASH"),
    (re.compile(r"(?<!\d)\+?\d[\d\s-]{8,}\d(?!\d)"), "REDACTED_NUMBER"),
]

def clean_str(s, extras):
    for pat, rep in VAL_PATTERNS:
        s = pat.sub(rep, s)
    for e in extras:
        if e:
            s = re.sub(re.escape(e), "REDACTED", s, flags=re.I)
    return s

def walk(o, extras, max_items, keys_only, key=""):
    if isinstance(o, dict):
        return {k: walk(v, extras, max_items, keys_only, k) for k, v in o.items()}
    if isinstance(o, list):
        return [walk(v, extras, max_items, keys_only, key) for v in o[:max_items]]
    if keys_only:
        return "..."
    if KEY_RE.search(key or ""):
        return "REDACTED"
    if isinstance(o, str):
        return clean_str(o, extras)
    if isinstance(o, (int, float)) and not isinstance(o, bool) and len(str(int(o))) >= 9 and float(o).is_integer():
        return "REDACTED_NUMBER"
    return o

def read_input(path):
    if path:
        return open(path, encoding="utf-8").read()
    try:
        import tkinter
        r = tkinter.Tk(); r.withdraw(); txt = r.clipboard_get(); r.destroy(); return txt
    except Exception:
        print("Could not read the clipboard. Pass a file: python tools/sanitize_json.py response.json"); sys.exit(1)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?")
    ap.add_argument("--extra", nargs="*", default=[], help="words to always remove (your name, register number)")
    ap.add_argument("--max-items", type=int, default=3)
    ap.add_argument("--keys-only", action="store_true")
    a = ap.parse_args()
    try:
        data = json.loads(read_input(a.file))
    except json.JSONDecodeError as e:
        print("That is not valid JSON:", e); sys.exit(1)
    out = json.dumps(walk(data, a.extra, a.max_items, a.keys_only), indent=2, ensure_ascii=False)
    print(out)
    try:
        import tkinter
        r = tkinter.Tk(); r.withdraw(); r.clipboard_clear(); r.clipboard_append(out); r.update(); r.destroy()
        print("\n--- cleaned JSON copied to clipboard. READ IT before pasting. ---")
    except Exception:
        pass

if __name__ == "__main__":
    main()
