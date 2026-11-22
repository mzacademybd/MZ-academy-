"""Real-world actions the assistant can take on your behalf.

These run on YOUR computer (not on Anthropic's servers), and chat.py asks for
your permission before each one. Your email password never leaves this computer.

Email uses Gmail with an "App Password" (see README.md):
    GMAIL_ADDRESS        your Gmail / Google Workspace address
    GMAIL_APP_PASSWORD   16-character app password
"""

import email
import email.utils
import imaplib
import json
import os
import smtplib
import uuid
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.message import EmailMessage
from pathlib import Path

HERE = Path(__file__).parent
TASKS_FILE = HERE / "tasks.json"
OUTPUT_DIR = HERE / "outputs"

SMTP_HOST, SMTP_PORT = "smtp.gmail.com", 465
IMAP_HOST = "imap.gmail.com"


class ActionError(Exception):
    """A problem the assistant should be told about (shown as a tool error)."""


# --------------------------------------------------------------------------- helpers

def _gmail_login() -> tuple[str, str]:
    address = os.environ.get("GMAIL_ADDRESS")
    password = os.environ.get("GMAIL_APP_PASSWORD")
    if not address or not password:
        raise ActionError(
            "Email is not set up on this computer (GMAIL_ADDRESS / GMAIL_APP_PASSWORD "
            "missing). Tell the user to follow 'Email setup' in README.md."
        )
    return address, password.replace(" ", "")


def _as_list(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return [str(v).strip() for v in value if str(v).strip()]


def _send(msg: EmailMessage) -> None:
    address, password = _gmail_login()
    msg["From"] = address
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid()
    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            smtp.login(address, password)
            smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        raise ActionError("Gmail rejected the login. The app password may be wrong.")
    except (smtplib.SMTPException, OSError) as e:
        raise ActionError(f"Could not send email: {e}")


def _attach_local_files(msg: EmailMessage, filenames: list[str]) -> list[str]:
    attached = []
    for name in filenames:
        path = OUTPUT_DIR / Path(name).name
        if not path.exists():
            raise ActionError(
                f"Attachment '{name}' was not found. Save it to /mnt/session/outputs/ first."
            )
        msg.add_attachment(
            path.read_bytes(), maintype="application", subtype="octet-stream", filename=path.name
        )
        attached.append(path.name)
    return attached


def _load_tasks() -> list[dict]:
    if TASKS_FILE.exists():
        return json.loads(TASKS_FILE.read_text())
    return []


def _save_tasks(tasks: list[dict]) -> None:
    TASKS_FILE.write_text(json.dumps(tasks, indent=2, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- actions

def send_email(to, subject, body, cc=None, attachments=None) -> str:
    msg = EmailMessage()
    msg["To"] = ", ".join(_as_list(to))
    if cc:
        msg["Cc"] = ", ".join(_as_list(cc))
    msg["Subject"] = subject
    msg.set_content(body)
    attached = _attach_local_files(msg, _as_list(attachments))
    _send(msg)
    extra = f" with attachments {attached}" if attached else ""
    return f"Email sent to {msg['To']}{extra}."


def read_inbox(search="UNSEEN", limit=10) -> str:
    """search: Gmail search text (e.g. 'from:ceo@x.com', 'is:unread invoice')."""
    address, password = _gmail_login()
    limit = max(1, min(int(limit or 10), 25))
    try:
        with imaplib.IMAP4_SSL(IMAP_HOST, timeout=30) as imap:
            imap.login(address, password)
            imap.select("INBOX", readonly=True)  # read-only: never marks mail as read
            query = search or "is:unread"
            if query.upper() == "UNSEEN":
                query = "is:unread"
            status, data = imap.search(None, "X-GM-RAW", f'"{query}"')
            if status != "OK":
                raise ActionError(f"Inbox search failed for '{query}'.")
            ids = data[0].split()[-limit:][::-1]
            items = []
            for mid in ids:
                _, msg_data = imap.fetch(mid, "(BODY.PEEK[])")
                msg = email.message_from_bytes(msg_data[0][1])
                body = ""
                if msg.is_multipart():
                    for p in msg.walk():
                        if p.get_content_type() == "text/plain" and not p.get_filename():
                            body = p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8", "replace")
                            break
                else:
                    body = msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", "replace")
                items.append({
                    "from": str(make_header(decode_header(msg.get("From", "")))),
                    "subject": str(make_header(decode_header(msg.get("Subject", "")))),
                    "date": msg.get("Date", ""),
                    "preview": body.strip()[:1500],
                })
    except imaplib.IMAP4.error as e:
        raise ActionError(f"Could not read inbox: {e}")
    if not items:
        return f"No emails matched '{query}'."
    return json.dumps(items, indent=2, ensure_ascii=False)


def send_calendar_invite(title, start, duration_minutes, attendees,
                         description="", location="") -> str:
    """Emails a standard calendar invite (.ics) that works with Google, Outlook and Apple calendars."""
    try:
        start_dt = datetime.fromisoformat(start)
    except ValueError:
        raise ActionError("start must be ISO format with timezone, e.g. 2026-12-01T10:00:00+06:00")
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone(timedelta(hours=6)))  # default: Bangladesh time
    end_dt = start_dt + timedelta(minutes=int(duration_minutes))
    fmt = lambda d: d.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    address, _ = _gmail_login()
    people = _as_list(attendees)
    esc = lambda s: str(s).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    ics = "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//MZ Academy Assistant//EN", "METHOD:REQUEST",
        "BEGIN:VEVENT",
        f"UID:{uuid.uuid4()}@mz-assistant",
        f"DTSTAMP:{fmt(datetime.now(timezone.utc))}",
        f"DTSTART:{fmt(start_dt)}", f"DTEND:{fmt(end_dt)}",
        f"SUMMARY:{esc(title)}", f"DESCRIPTION:{esc(description)}", f"LOCATION:{esc(location)}",
        f"ORGANIZER:mailto:{address}",
        *[f"ATTENDEE;RSVP=TRUE;ROLE=REQ-PARTICIPANT:mailto:{p}" for p in people],
        "END:VEVENT", "END:VCALENDAR", "",
    ])
    msg = EmailMessage()
    msg["To"] = ", ".join(people)
    msg["Subject"] = f"Invitation: {title} — {start_dt.strftime('%a %d %b %Y, %I:%M %p')}"
    msg.set_content(f"{description}\n\nWhen: {start_dt.strftime('%A %d %B %Y, %I:%M %p %Z')} "
                    f"({duration_minutes} min)\nWhere: {location or '—'}")
    msg.add_attachment(ics.encode(), maintype="text", subtype="calendar",
                       filename="invite.ics", params={"method": "REQUEST"})
    _send(msg)
    return f"Calendar invite '{title}' sent to {', '.join(people)}."


def add_task(title, due="", priority="normal", notes="") -> str:
    tasks = _load_tasks()
    task = {"id": (max((t["id"] for t in tasks), default=0) + 1), "title": title, "due": due,
            "priority": priority, "notes": notes, "done": False,
            "created": datetime.now().strftime("%Y-%m-%d %H:%M")}
    tasks.append(task)
    _save_tasks(tasks)
    return f"Task #{task['id']} added: {title}"


def list_tasks(include_done=False) -> str:
    tasks = [t for t in _load_tasks() if include_done or not t["done"]]
    return json.dumps(tasks, indent=2, ensure_ascii=False) if tasks else "No open tasks."


def complete_task(task_id) -> str:
    tasks = _load_tasks()
    for t in tasks:
        if t["id"] == int(task_id):
            t["done"] = True
            _save_tasks(tasks)
            return f"Task #{t['id']} marked done: {t['title']}"
    raise ActionError(f"No task with id {task_id}.")


ACTIONS = {
    "send_email": send_email,
    "read_inbox": read_inbox,
    "send_calendar_invite": send_calendar_invite,
    "add_task": add_task,
    "list_tasks": list_tasks,
    "complete_task": complete_task,
}


import integrations  # noqa: E402  (Calendar, Drive, WhatsApp, Facebook)

ACTIONS.update(integrations.ACTIONS)


def run(name: str, tool_input: dict) -> str:
    if name not in ACTIONS:
        raise ActionError(f"Unknown action '{name}'.")
    try:
        return ACTIONS[name](**tool_input)
    except TypeError as e:
        raise ActionError(f"Wrong inputs for {name}: {e}")
    except integrations.IntegrationError as e:
        raise ActionError(str(e))
