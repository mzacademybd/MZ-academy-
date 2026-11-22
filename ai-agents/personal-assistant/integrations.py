"""Google Calendar, Google Drive, WhatsApp and Facebook Page actions.

Like actions.py, these run on YOUR computer after you approve them in chat.py.
Credentials stay on this computer.

Setup (see README.md):
  Google  -> put google_credentials.json here, then run:  python connect_google.py
  WhatsApp Cloud API (optional) -> WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID
        (without these, WhatsApp opens a ready-to-send chat in your browser instead)
  Facebook Page -> FACEBOOK_PAGE_ID, FACEBOOK_PAGE_TOKEN
"""

import os
import urllib.parse
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
OUTPUT_DIR = HERE / "outputs"
GOOGLE_CLIENT_FILE = HERE / "google_credentials.json"
GOOGLE_TOKEN_FILE = HERE / "google_token.json"
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",  # create/read your events
    "https://www.googleapis.com/auth/drive.readonly",    # search & read your Drive files
    "https://www.googleapis.com/auth/drive.file",        # upload files the assistant makes
]
BD_TZ = timezone(timedelta(hours=6))
GRAPH = f"https://graph.facebook.com/{os.environ.get('META_GRAPH_VERSION', 'v26.0')}"


class IntegrationError(Exception):
    pass


# ============================================================================ Google

def google_service(api: str, version: str):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError:
        raise IntegrationError("Google libraries missing. Run: pip install -r requirements.txt")
    if not GOOGLE_TOKEN_FILE.exists():
        raise IntegrationError(
            "Google is not connected on this computer. Tell the user to run "
            "'python connect_google.py' (see README.md, Google setup)."
        )
    creds = Credentials.from_authorized_user_file(str(GOOGLE_TOKEN_FILE), GOOGLE_SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            from google.auth.exceptions import RefreshError
            try:
                creds.refresh(Request())
            except RefreshError:
                raise IntegrationError(
                    "Google login is no longer valid. Tell the user to run 'python connect_google.py' again."
                )
            GOOGLE_TOKEN_FILE.write_text(creds.to_json())
        else:
            raise IntegrationError("Google login expired. Run 'python connect_google.py' again.")
    return build(api, version, credentials=creds, cache_discovery=False)


def _google_call(request):
    from googleapiclient.errors import HttpError
    try:
        return request.execute()
    except HttpError as e:
        raise IntegrationError(f"Google API error {e.status_code}: {e.reason}")


def _parse_time(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise IntegrationError("Times must be ISO format, e.g. 2026-12-01T10:00:00+06:00")
    return dt if dt.tzinfo else dt.replace(tzinfo=BD_TZ)


def calendar_list_events(days_ahead=7, search="") -> str:
    cal = google_service("calendar", "v3")
    now = datetime.now(timezone.utc)
    res = _google_call(cal.events().list(
        calendarId="primary", timeMin=now.isoformat(),
        timeMax=(now + timedelta(days=int(days_ahead or 7))).isoformat(),
        singleEvents=True, orderBy="startTime", maxResults=50, q=search or None,
    ))
    items = res.get("items", [])
    if not items:
        return "No events found."
    lines = []
    for ev in items:
        start = ev["start"].get("dateTime", ev["start"].get("date"))
        who = ", ".join(a["email"] for a in ev.get("attendees", [])[:6])
        lines.append(f"- {start} | {ev.get('summary', '(no title)')}"
                     + (f" | {ev['location']}" if ev.get("location") else "")
                     + (f" | with {who}" if who else "") + f" | id={ev['id']}")
    return "\n".join(lines)


def calendar_create_event(title, start, duration_minutes, attendees=None,
                          description="", location="", add_meet_link=False) -> str:
    cal = google_service("calendar", "v3")
    start_dt = _parse_time(start)
    body = {
        "summary": title,
        "description": description,
        "location": location,
        "start": {"dateTime": start_dt.isoformat()},
        "end": {"dateTime": (start_dt + timedelta(minutes=int(duration_minutes))).isoformat()},
        "attendees": [{"email": a} for a in (attendees or [])],
    }
    kwargs = {}
    if add_meet_link:
        body["conferenceData"] = {"createRequest": {"requestId": os.urandom(8).hex(),
                                                    "conferenceSolutionKey": {"type": "hangoutsMeet"}}}
        kwargs["conferenceDataVersion"] = 1
    ev = _google_call(cal.events().insert(calendarId="primary", body=body,
                                          sendUpdates="all" if attendees else "none", **kwargs))
    meet = ev.get("hangoutLink")
    return (f"Event created: {title} at {start_dt.strftime('%a %d %b %Y %I:%M %p')}. "
            f"Link: {ev.get('htmlLink')}" + (f" | Meet: {meet}" if meet else ""))


def drive_search(query, limit=10) -> str:
    drive = google_service("drive", "v3")
    safe = str(query).replace("\\", "\\\\").replace("'", "\\'")
    res = _google_call(drive.files().list(
        q=f"(name contains '{safe}' or fullText contains '{safe}') and trashed = false",
        pageSize=max(1, min(int(limit or 10), 25)),
        fields="files(id,name,mimeType,modifiedTime,webViewLink)", orderBy="modifiedTime desc",
    ))
    files = res.get("files", [])
    if not files:
        return f"No Drive files matched '{query}'."
    return "\n".join(f"- {f['name']} | {f['mimeType'].split('.')[-1]} | modified {f['modifiedTime'][:10]}"
                     f" | id={f['id']} | {f.get('webViewLink', '')}" for f in files)


def drive_read_file(file_id) -> str:
    drive = google_service("drive", "v3")
    meta = _google_call(drive.files().get(fileId=file_id, fields="name,mimeType"))
    mime = meta["mimeType"]
    exports = {
        "application/vnd.google-apps.document": "text/plain",
        "application/vnd.google-apps.spreadsheet": "text/csv",
        "application/vnd.google-apps.presentation": "text/plain",
    }
    if mime in exports:
        data = _google_call(drive.files().export(fileId=file_id, mimeType=exports[mime]))
    elif mime.startswith("text/") or mime in ("application/json", "text/csv"):
        data = _google_call(drive.files().get_media(fileId=file_id))
    else:
        return (f"'{meta['name']}' is a {mime} file; only Google Docs/Sheets/Slides and text "
                "files can be read as text.")
    text = data.decode("utf-8", "replace") if isinstance(data, bytes) else str(data)
    limit = 60_000
    note = f"\n\n[Truncated: showing first {limit} of {len(text)} characters]" if len(text) > limit else ""
    return f"# {meta['name']}\n\n{text[:limit]}{note}"


def drive_upload_file(filename, folder_id="", convert_to_google_format=True) -> str:
    from googleapiclient.http import MediaFileUpload
    path = OUTPUT_DIR / Path(filename).name
    if not path.exists():
        raise IntegrationError(f"'{filename}' not found. Save it to /mnt/session/outputs/ first.")
    convert = {".docx": "application/vnd.google-apps.document",
               ".md": "application/vnd.google-apps.document",
               ".txt": "application/vnd.google-apps.document",
               ".xlsx": "application/vnd.google-apps.spreadsheet",
               ".csv": "application/vnd.google-apps.spreadsheet",
               ".pptx": "application/vnd.google-apps.presentation"}
    body = {"name": path.stem if convert_to_google_format and path.suffix in convert else path.name}
    if convert_to_google_format and path.suffix in convert:
        body["mimeType"] = convert[path.suffix]
    if folder_id:
        body["parents"] = [folder_id]
    mimetype = "text/plain" if path.suffix in (".md", ".txt") else None
    drive = google_service("drive", "v3")
    f = _google_call(drive.files().create(body=body, media_body=MediaFileUpload(str(path), mimetype=mimetype),
                                          fields="id,name,webViewLink"))
    return f"Uploaded to Google Drive: {f['name']} — {f.get('webViewLink')}"


# ============================================================================ Meta

def _graph_post(path: str, token: str, **kwargs) -> dict:
    import requests
    try:
        r = requests.post(f"{GRAPH}/{path}", headers={"Authorization": f"Bearer {token}"},
                          timeout=60, **kwargs)
    except requests.RequestException as e:
        raise IntegrationError(f"Could not reach Meta: {e}")
    data = r.json() if r.content else {}
    if r.status_code >= 400 or "error" in data:
        msg = data.get("error", {}).get("message", r.text[:300])
        raise IntegrationError(f"Meta API error {r.status_code}: {msg}")
    return data


def _normalise_phone(number: str) -> str:
    digits = "".join(ch for ch in str(number) if ch.isdigit())
    if digits.startswith("01") and len(digits) == 11:  # Bangladesh local format 01XXXXXXXXX
        digits = "88" + digits
    if len(digits) < 10:
        raise IntegrationError(f"'{number}' doesn't look like a full phone number.")
    return digits


def whatsapp_send(to, message) -> str:
    phone = _normalise_phone(to)
    token = os.environ.get("WHATSAPP_TOKEN")
    phone_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
    if token and phone_id:
        _graph_post(f"{phone_id}/messages", token, json={
            "messaging_product": "whatsapp", "to": phone, "type": "text",
            "text": {"body": message, "preview_url": True},
        })
        return f"WhatsApp message sent to +{phone} via WhatsApp Business."
    # No Business API: open WhatsApp with the message ready; the user presses Send.
    url = f"https://wa.me/{phone}?text={urllib.parse.quote(message)}"
    opened = webbrowser.open(url)
    return (f"Opened WhatsApp for +{phone} with the message ready — the user must press Send."
            + ("" if opened else f" (Could not open a browser; link: {url})"))


def facebook_page_post(message, link="", image_filename="") -> str:
    page_id = os.environ.get("FACEBOOK_PAGE_ID")
    token = os.environ.get("FACEBOOK_PAGE_TOKEN")
    if not page_id or not token:
        raise IntegrationError("Facebook Page is not set up (FACEBOOK_PAGE_ID / FACEBOOK_PAGE_TOKEN). "
                               "Tell the user to follow 'Facebook Page setup' in README.md.")
    if image_filename:
        path = OUTPUT_DIR / Path(image_filename).name
        if not path.exists():
            raise IntegrationError(f"Image '{image_filename}' not found in outputs.")
        with path.open("rb") as fh:
            data = _graph_post(f"{page_id}/photos", token, data={"caption": message},
                               files={"source": (path.name, fh)})
    else:
        payload = {"message": message}
        if link:
            payload["link"] = link
        data = _graph_post(f"{page_id}/feed", token, data=payload)
    post_id = data.get("post_id") or data.get("id", "")
    return f"Posted to the Facebook Page. https://www.facebook.com/{post_id}"


ACTIONS = {
    "calendar_list_events": calendar_list_events,
    "calendar_create_event": calendar_create_event,
    "drive_search": drive_search,
    "drive_read_file": drive_read_file,
    "drive_upload_file": drive_upload_file,
    "whatsapp_send": whatsapp_send,
    "facebook_page_post": facebook_page_post,
}

# Actions that need files from the session downloaded to ./outputs first.
NEEDS_OUTPUT_FILES = {"drive_upload_file", "facebook_page_post"}
