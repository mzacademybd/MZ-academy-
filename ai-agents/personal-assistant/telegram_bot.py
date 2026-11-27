"""Your personal assistant on Telegram — every action needs your tap on ✅ Approve.

Run:   python telegram_bot.py
Auto-start on your Mac (survives restarts):   ./install_mac_service.sh

Settings come from the .env file in this folder (never commit it):
    TELEGRAM_BOT_TOKEN   from BotFather
    TELEGRAM_OWNER_ID    your numeric Telegram user id (the bot tells you it on /start)
    ANTHROPIC_API_KEY    plus GMAIL_*, FACEBOOK_*, WHATSAPP_* as in README.md

Only the owner can use the bot; everyone else is politely refused.
"""

import json
import os
import queue
import sys
import threading
import time
import traceback
from pathlib import Path

HERE = Path(__file__).parent


def load_env_file(path: Path = HERE / ".env") -> None:
    """Minimal .env loader: KEY=value lines; existing environment wins."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_env_file()

import anthropic  # noqa: E402
import requests  # noqa: E402

import agent_config as cfg  # noqa: E402
import chat  # noqa: E402  (reuses session, preview, action and file helpers)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
OWNER_ID = os.environ.get("TELEGRAM_OWNER_ID", "").strip()
API = f"https://api.telegram.org/bot{TOKEN}"
APPROVAL_TIMEOUT = 30 * 60  # seconds; unanswered approvals are rejected
MAX_MSG = 4000

HELP = (
    "🤖 Ami apnar personal assistant.\n\n"
    "Je kono kaj likhe pathan — email, meeting, task, Facebook post, WhatsApp…\n"
    "Kono kaj korar age ami ✅ Approve / ❌ Reject / ✏️ Change button pathabo.\n\n"
    "/new — notun conversation shuru\n"
    "/files — ami je file banayechi segulo pathao\n"
    "/tasks — apnar task list\n"
    "/help — ei message"
)


# ----------------------------------------------------------------------------- Telegram

def tg(method: str, **params):
    for attempt in range(4):
        try:
            r = requests.post(f"{API}/{method}", json=params, timeout=70)
            data = r.json()
        except (requests.RequestException, ValueError) as e:
            log(f"telegram {method} failed: {e}")
            time.sleep(2 ** attempt)
            continue
        if data.get("ok"):
            return data["result"]
        if data.get("error_code") == 429:
            time.sleep(data.get("parameters", {}).get("retry_after", 3))
            continue
        log(f"telegram {method} error: {data.get('description')}")
        return None
    return None


def send(chat_id, text: str, **extra):
    text = text or "…"
    msg = None
    for i in range(0, len(text), MAX_MSG):
        msg = tg("sendMessage", chat_id=chat_id, text=text[i:i + MAX_MSG],
                 disable_web_page_preview=True, **(extra if i + MAX_MSG >= len(text) else {}))
    return msg


def send_document(chat_id, path: Path) -> None:
    with path.open("rb") as fh:
        requests.post(f"{API}/sendDocument", data={"chat_id": chat_id},
                      files={"document": (path.name, fh)}, timeout=120)


def log(msg: str) -> None:
    print(time.strftime("%Y-%m-%d %H:%M:%S"), msg, flush=True)


# ----------------------------------------------------------------------------- Approvals

class Approvals:
    """Waits for the owner's button tap (or a typed change request)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._pending: dict[str, dict] = {}   # key -> {"event": Event, "choice":..., "feedback":...}
        self.awaiting_feedback: str | None = None

    def wait(self, chat_id, key: str, preview: str) -> tuple[str, str]:
        slot = {"event": threading.Event(), "choice": "n", "feedback": ""}
        with self._lock:
            self._pending[key] = slot
        keyboard = {"inline_keyboard": [[
            {"text": "✅ Approve", "callback_data": f"y|{key}"},
            {"text": "❌ Reject", "callback_data": f"n|{key}"},
            {"text": "✏️ Change", "callback_data": f"e|{key}"},
        ]]}
        send(chat_id, f"🔐 Permission chai:\n{preview}", reply_markup=keyboard)
        if not slot["event"].wait(APPROVAL_TIMEOUT):
            send(chat_id, "⏰ 30 minute e uttor paini — kaj ta bad dilam (rejected).")
        with self._lock:
            self._pending.pop(key, None)
            if self.awaiting_feedback == key:
                self.awaiting_feedback = None
        return slot["choice"], slot["feedback"]

    def on_button(self, choice: str, key: str) -> str:
        with self._lock:
            slot = self._pending.get(key)
            if not slot:
                return "Eta ar active nai."
            if choice == "e":
                self.awaiting_feedback = key
                return "Ki change chan likhe pathan ✏️"
            slot["choice"] = choice
            slot["event"].set()
            return "✅ Approved" if choice == "y" else "❌ Rejected"

    def has_pending(self) -> bool:
        with self._lock:
            return bool(self._pending)

    def on_text(self, text: str) -> bool:
        """If a change request is pending, use this text as the feedback."""
        with self._lock:
            key = self.awaiting_feedback
            slot = self._pending.get(key) if key else None
            if not slot:
                return False
            slot["choice"], slot["feedback"] = "e", text
            self.awaiting_feedback = None
            slot["event"].set()
            return True


# ----------------------------------------------------------------------------- Assistant

class Assistant:
    def __init__(self, approvals: Approvals):
        self.client = anthropic.Anthropic()
        self.approvals = approvals
        self.ids = chat.load_ids()

    def session_id(self, fresh: bool = False) -> str:
        if fresh or not self.ids.get("telegram_session_id"):
            self.ids["telegram_session_id"] = chat.start_session(self.client, self.ids)
            chat.IDS_FILE.write_text(json.dumps(self.ids, indent=2) + "\n")
        return self.ids["telegram_session_id"]

    def turn(self, chat_id, text: str) -> None:
        sid = self.session_id()
        to_send = [{"type": "user.message", "content": [{"type": "text", "text": text}]}]
        tg("sendChatAction", chat_id=chat_id, action="typing")
        while to_send is not None:
            pending_tools, pending_asks, outcome = [], [], None
            # Stream-first: open the stream, then send, so no event is missed.
            with self.client.beta.sessions.events.stream(session_id=sid) as stream:
                self.client.beta.sessions.events.send(session_id=sid, events=to_send)
                to_send = None
                for event in stream:
                    if event.type == "agent.message":
                        reply = "".join(b.text for b in event.content if b.type == "text").strip()
                        if reply:
                            send(chat_id, reply)
                    elif event.type == "agent.custom_tool_use":
                        pending_tools.append(event)
                    elif event.type == "agent.tool_use":
                        if getattr(event, "evaluated_permission", None) == "ask":
                            pending_asks.append(event)
                        else:
                            tg("sendChatAction", chat_id=chat_id, action="typing")
                    elif event.type == "session.error":
                        send(chat_id, f"⚠️ Error: {getattr(event, 'error', event)}")
                    elif event.type == "session.status_idle":
                        outcome = event.stop_reason.type
                        if outcome == "requires_action" and not (pending_tools or pending_asks):
                            continue  # the blocking events haven't arrived yet
                        break
                    elif event.type == "session.status_terminated":
                        outcome = "terminated"
                        break

            if outcome == "requires_action":
                # Stream is closed while we wait for the owner; reopened before replying.
                to_send = self.decide(chat_id, sid, pending_tools, pending_asks)
            elif outcome == "budget_reached":
                self.session_id(fresh=True)
                send(chat_id, "💰 Ei conversation er khoroch-seema shes. Notun conversation shuru "
                              "korlam — kaj ta abar likhe pathan.")
            elif outcome == "terminated":
                self.session_id(fresh=True)
                send(chat_id, "Conversation ta bondho hoye gechilo; notun ta shuru korlam. Abar pathan.")

    def decide(self, chat_id, sid, tools, asks) -> list[dict]:
        events = []
        for ev in tools:
            name, inp = ev.name, dict(ev.input or {})
            if name in cfg.AUTO_APPROVE:
                choice, feedback = "y", ""
            else:
                preview = chat.describe_action(name, inp).replace("─" * 60, "─" * 20)
                choice, feedback = self.approvals.wait(chat_id, ev.id, preview)
            result, is_error = chat.resolve_action(self.client, sid, name, inp, choice, feedback)
            if choice == "y":
                send(chat_id, ("❌ " if is_error else "✅ ") + result.splitlines()[0][:500])
            events.append({"type": "user.custom_tool_result", "custom_tool_use_id": ev.id,
                           "content": [{"type": "text", "text": result}], "is_error": is_error})
        for ev in asks:
            preview = f"⚙ Sandbox e '{ev.name}' chalate chai:\n{json.dumps(ev.input, indent=1)[:1500]}"
            choice, _ = self.approvals.wait(chat_id, ev.id, preview)
            events.append({"type": "user.tool_confirmation", "tool_use_id": ev.id,
                           "result": "allow" if choice == "y" else "deny"})
        return events

    def send_files(self, chat_id) -> None:
        sid = self.session_id()
        chat.download_files(self.client, sid, quiet=True)
        files = sorted(chat.OUTPUT_DIR.glob("*")) if chat.OUTPUT_DIR.exists() else []
        if not files:
            send(chat_id, "Ekhono kono file nai.")
        for f in files:
            if f.is_file():
                send_document(chat_id, f)


# ----------------------------------------------------------------------------- Main loop

def is_owner(user_id) -> bool:
    return bool(OWNER_ID) and str(user_id) == OWNER_ID


def worker(jobs: "queue.Queue", assistant: Assistant) -> None:
    while True:
        chat_id, text = jobs.get()
        try:
            if text == "/new":
                assistant.session_id(fresh=True)
                send(chat_id, "🆕 Notun conversation shuru. Ki korte hobe?")
            elif text == "/files":
                assistant.send_files(chat_id)
            elif text == "/tasks":
                import actions
                send(chat_id, "✅ Tasks:\n" + actions.list_tasks())
            else:
                assistant.turn(chat_id, text)
        except anthropic.AuthenticationError:
            send(chat_id, "⚠️ Anthropic API key kaj korche na. .env file e ANTHROPIC_API_KEY check korun.")
        except Exception as e:  # keep the bot alive no matter what
            log("turn failed:\n" + traceback.format_exc())
            send(chat_id, f"⚠️ Somossya hoyeche: {type(e).__name__}: {str(e)[:300]}\nAbar chesta korun.")
        finally:
            jobs.task_done()


def main() -> None:
    if not TOKEN:
        sys.exit("TELEGRAM_BOT_TOKEN missing. Put it in the .env file (see README.md).")
    me = tg("getMe")
    if not me:
        sys.exit("Telegram rejected the token. Check TELEGRAM_BOT_TOKEN in .env.")
    tg("deleteWebhook")  # we use polling
    log(f"Bot @{me['username']} is running. Owner id: {OWNER_ID or 'NOT SET'}")

    approvals = Approvals()
    assistant = Assistant(approvals) if OWNER_ID else None
    jobs: "queue.Queue" = queue.Queue()
    if assistant:
        threading.Thread(target=worker, args=(jobs, assistant), daemon=True).start()

    offset = None
    while True:
        updates = tg("getUpdates", timeout=50, offset=offset,
                     allowed_updates=["message", "callback_query"]) or []
        for u in updates:
            offset = u["update_id"] + 1
            if "callback_query" in u:
                cq = u["callback_query"]
                if not is_owner(cq["from"]["id"]):
                    tg("answerCallbackQuery", callback_query_id=cq["id"], text="Not allowed")
                    continue
                choice, _, key = cq.get("data", "").partition("|")
                note = approvals.on_button(choice, key)
                tg("answerCallbackQuery", callback_query_id=cq["id"], text=note)
                if choice in ("y", "n"):  # remove the buttons once decided
                    tg("editMessageReplyMarkup", chat_id=cq["message"]["chat"]["id"],
                       message_id=cq["message"]["message_id"], reply_markup={"inline_keyboard": []})
                if choice == "e":
                    send(cq["message"]["chat"]["id"], note)
                continue

            msg = u.get("message") or {}
            text = (msg.get("text") or "").strip()
            chat_id, user_id = msg.get("chat", {}).get("id"), msg.get("from", {}).get("id")
            if not text or chat_id is None:
                continue
            if not OWNER_ID:
                send(chat_id, f"Setup baki: apnar Telegram ID holo {user_id}.\n"
                              f".env file e likhun:  TELEGRAM_OWNER_ID={user_id}\n"
                              "tarpor bot abar chalu korun.")
                continue
            if not is_owner(user_id):
                send(chat_id, "🔒 Eta ekta private assistant. Dukkhito, apni use korte parben na.")
                continue
            if text in ("/start", "/help"):
                send(chat_id, HELP)
                continue
            if approvals.on_text(text):
                send(chat_id, "✏️ Thik ache, change ta assistant ke janalam.")
                continue
            if approvals.has_pending():
                send(chat_id, "👆 Age upor er ✅ Approve / ❌ Reject / ✏️ Change button chapun. "
                              "Ei message ta tar pore korbo.")
            elif not jobs.empty():
                send(chat_id, "⏳ Ager kaj ta cholche, eta tar porei korbo.")
            jobs.put((chat_id, text))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Stopped.")
