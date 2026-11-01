"""Stops you from committing private files. Installed as a git pre-commit hook by tools/install_hook.py.

  python tools/check_private.py            # checks what is staged right now (exit 1 = blocked)
  python tools/check_private.py --tracked  # lists private files that are ALREADY tracked by git"""
import re, subprocess, sys

BLOCK = [r"(^|/)data/private/", r"(^|/)\.env($|\.)(?!example)", r"\.har$", r"\.hyper$", r"\.tde$", r"\.twbx?$", r"\.twbr$", r"(^|/)hyperd\.log$",
         r"(^|/)captures/", r"(^|/)logs/", r"cookies\.json$", r"storage_state\.json$", r"(^|/)marks(_history)?\.csv$", r"SistPerf_Live", r"\.(db|sqlite3?)$"]
ALLOW = [r"(^|/)data/private/\.gitkeep$", r"(^|/)\.env\.example$", r"(^|/)tableau/sample_data/", r"(^|/)data/sample/", r"(^|/)scripts/hyper_templates/"]

def git(*a):
    return subprocess.run(["git", *a], capture_output=True, text=True).stdout.splitlines()

def bad(files):
    return [f for f in files if any(re.search(p, f) for p in BLOCK) and not any(re.search(p, f) for p in ALLOW)]

def main():
    tracked = "--tracked" in sys.argv
    files = git("ls-files") if tracked else git("diff", "--cached", "--name-only", "--diff-filter=ACMR")
    hits = bad(files)
    if not hits:
        print("OK: no private files " + ("tracked." if tracked else "staged.")); return 0
    print("\nBLOCKED: these look like PRIVATE files:\n" + "\n".join("  " + h for h in hits))
    print("\nDo not commit them. Unstage with:  git restore --staged <file>   (and make sure .gitignore lists them)\n" if not tracked else
          "\nRemove from git (keeps them on your disk):  git rm -r --cached <path>\n")
    return 1

if __name__ == "__main__":
    sys.exit(main())
