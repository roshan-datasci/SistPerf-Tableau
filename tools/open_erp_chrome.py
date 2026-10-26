"""Open YOUR Chrome with a debugging port so SistPerf can read marks from the page you log in to.
You log in yourself (including the Cloudflare check). Nothing here types a password or bypasses anything.
Close this Chrome window when you are done: the debugging port lets programs on this PC control that window."""
import os, shutil, subprocess, sys

def chrome_path():
    for p in (r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
        if os.path.exists(p):
            return p
    return shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chrome")

def main():
    exe = chrome_path()
    if not exe:
        print("Chrome not found. Start it yourself with: chrome --remote-debugging-port=9222 --user-data-dir=<a new folder>"); sys.exit(1)
    profile = os.path.join(os.path.expanduser("~"), "SistPerfChrome")   # separate profile: Chrome requires one for the debug port
    subprocess.Popen([exe, "--remote-debugging-port=9222", f"--user-data-dir={profile}", "https://erp.sathyabama.ac.in"])
    print("Chrome opened. 1) Log in to the ERP yourself. 2) Wait until the student page (Profile / semester sections) is showing.\n"
          "3) In a new terminal run:  python -m tracker.tracker --adapter browser")

if __name__ == "__main__":
    main()
