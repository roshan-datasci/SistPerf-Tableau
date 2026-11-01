# Security

Never commit: passwords, `.env`, cookies or session files, private exports, real-data databases, `.hyper` extracts, or Tableau workbooks containing real marks.

- Keep real data in `data/private/` (git-ignored).
- Enter passwords at runtime or keep them in a git-ignored `.env`. Never in code.
- Do not publish real data to Tableau Public: published data is downloadable.
- `.gitignore` only stops *future* adds. If a secret is ever committed, change/revoke it; deleting it in a later commit is not enough.
- Only automate access to an ERP if your institution permits it.

Before every commit run `git status` and check nothing under `data/private/` or any key/session file is staged.


## ERP responses
Raw ERP JSON can contain Aadhaar numbers, phone numbers, addresses and password hashes. Never commit or paste it. Run `python tools/sanitize_json.py` first and read the output. Never save HAR files or copy requests as cURL: they include your login token. The tracker keeps only the fields it needs (term, subject, marks) and never stores raw responses.

## If private files were committed or pushed by mistake
1. Install the safety check once: `python tools/install_hook.py` (it blocks commits that contain private files).
2. Undo the bad commit but keep your files: `git reset --soft <last good commit>` then `git reset`.
3. Fix `.gitignore` (append `GITIGNORE_ADD.txt`), run `git add .` and `python tools/check_private.py`. Commit only when it says OK.
4. If it was already pushed: `git push --force-with-lease origin main`. GitHub still keeps the old commit reachable by its hash for a while, so for certainty delete the repository and create it again, then push the clean history.
5. Treat anything that was pushed as exposed. Change any password or key that was in it.
