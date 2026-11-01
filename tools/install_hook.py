"""Install the pre-commit safety check:  python tools/install_hook.py   (run once per clone)."""
import os, stat
hook = os.path.join(".git", "hooks", "pre-commit")
if not os.path.isdir(".git"):
    raise SystemExit("Run this from the project folder (the one containing .git).")
open(hook, "w", newline="\n").write("#!/bin/sh\nexec python tools/check_private.py\n")
os.chmod(hook, os.stat(hook).st_mode | stat.S_IEXEC)
print("Installed:", hook, "- commits that include private files will now be blocked.")
