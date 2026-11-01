"""Open YOUR Chrome with a debugging port so SistPerf can read marks from the page you log in to.
You log in yourself (including the Cloudflare check). Nothing here types a password or bypasses anything.
Close this Chrome window when you are done: the debugging port lets programs on this PC control that window."""
import os, shutil, subprocess, sys, time, urllib.request

PORT = 9222

def port_open(port=PORT):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2).read()
        return True
    except Exception:
        return False

def chrome_path():
    for p in (r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
        if os.path.exists(p):
            return p
    return shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chrome")

def main():
    if port_open():
        print("Chrome with the debug port is ALREADY running. Use that window: log in to the ERP, then run\n  python -m tracker.tracker --adapter browser --export-tableau")
        return
    exe = chrome_path()
    if not exe:
        print("Chrome not found. Start it yourself with: chrome --remote-debugging-port=9222 --user-data-dir=<a new folder>"); sys.exit(1)
    profile = os.path.join(os.path.expanduser("~"), "SistPerfChrome")   # separate profile: Chrome requires one for the debug port
    subprocess.Popen([exe, "--remote-debugging-port=%d" % PORT, f"--user-data-dir={profile}", "https://erp.sathyabama.ac.in"])
    for _ in range(15):
        time.sleep(1)
        if port_open():
            print("Chrome is open and the debug port is READY.\n 1) Log in to the ERP yourself and wait for the student page.\n"
                  " 2) In a new terminal run:  python -m tracker.tracker --adapter browser --export-tableau")
            return
    print("Chrome opened, but the debug port is NOT open. This usually means another Chrome using the same profile was already running.\n"
          "Fix: close ALL Chrome windows, open Task Manager and end every 'chrome.exe', then run this script once more.")

if __name__ == "__main__":
    main()
