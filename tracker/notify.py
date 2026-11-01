"""Alerts when a mark appears or changes. Secrets come from a git-ignored .env file (see .env.example).
Channels: desktop, telegram, email. send() never raises and never prints secrets."""
import json, os, smtplib, ssl, subprocess, urllib.parse, urllib.request
from email.message import EmailMessage

def load_env(path=".env"):
    if os.path.exists(path):
        for ln in open(path, encoding="utf-8"):
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

def format_events(events):
    lines = []
    for e in events:
        old = f"{e['Old']:g} -> " if e["Event"] == "CHANGED" and e.get("Old") == e.get("Old") and e.get("Old") is not None else ""
        lines.append(f"{e['Event']}: Sem {e['Semester']} - {e['Subject']} - {e['Assessment']}: {old}{e['New']:g}/{e['Maximum']:g}")
    return f"SistPerf: {len(lines)} mark update(s)\n" + "\n".join(lines)

def _desktop(msg):
    try:
        from plyer import notification
        notification.notify(title="SistPerf", message=msg[:250], timeout=10); return "ok"
    except Exception:
        pass
    if os.name == "nt":
        safe = msg.replace("'", " ").replace('"', " ").replace("\n", " | ")[:200]
        ps = ("Add-Type -AssemblyName System.Windows.Forms,System.Drawing; $n=New-Object System.Windows.Forms.NotifyIcon; "
              "$n.Icon=[System.Drawing.SystemIcons]::Information; $n.Visible=$true; "
              f"$n.ShowBalloonTip(8000,'SistPerf','{safe}',[System.Windows.Forms.ToolTipIcon]::Info); Start-Sleep 9; $n.Dispose()")
        subprocess.Popen(["powershell", "-NoProfile", "-Command", ps]); return "ok"
    return "no desktop notifier available (pip install plyer)"

def _telegram(msg):
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        return "missing TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID in .env"
    data = urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode()
    urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage", data), timeout=15)
    return "ok"

def _email(msg):
    e = os.environ; need = ["SMTP_HOST", "SMTP_USER", "SMTP_PASS", "ALERT_TO"]
    if any(not e.get(k) for k in need):
        return "missing " + ", ".join(k for k in need if not e.get(k)) + " in .env"
    m = EmailMessage(); m["Subject"] = "SistPerf mark update"; m["From"] = e["SMTP_USER"]; m["To"] = e["ALERT_TO"]; m.set_content(msg)
    port = int(e.get("SMTP_PORT", 465))
    if port == 465:
        s = smtplib.SMTP_SSL(e["SMTP_HOST"], port, context=ssl.create_default_context(), timeout=20)
    else:
        s = smtplib.SMTP(e["SMTP_HOST"], port, timeout=20); s.starttls(context=ssl.create_default_context())
    with s:
        s.login(e["SMTP_USER"], e["SMTP_PASS"]); s.send_message(m)
    return "ok"

def send(msg, channels):
    load_env(); out = {}
    for ch in channels:
        try:
            out[ch] = {"desktop": _desktop, "telegram": _telegram, "email": _email}[ch](msg)
        except Exception as ex:
            out[ch] = f"failed ({type(ex).__name__})"
    return out
