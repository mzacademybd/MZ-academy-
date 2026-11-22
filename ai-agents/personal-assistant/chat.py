"""Chat with your personal assistant in the terminal.

    python chat.py              start a new conversation
    python chat.py --continue   pick up your last conversation

Whenever the assistant wants to act for you (send an email, a meeting invite,
read your inbox, change your tasks) it shows you exactly what it will do and
waits for your  y / n / e  answer. Every decision is logged to action_log.jsonl.

Commands while chatting:
    /files   download files the assistant created (saved to ./outputs/)
    /quit    end the chat
"""

import argparse
import json
import sys
import time
from pathlib import Path

import anthropic

import actions
import agent_config as cfg
import integrations

HERE = Path(__file__).parent
IDS_FILE = HERE / "assistant_ids.json"
OUTPUT_DIR = HERE / "outputs"
ACTION_LOG = HERE / "action_log.jsonl"


def load_ids() -> dict:
    if not IDS_FILE.exists():
        sys.exit("Assistant not set up yet. Run:  python setup_assistant.py")
    return json.loads(IDS_FILE.read_text())


def start_session(client: anthropic.Anthropic, ids: dict) -> str:
    session = client.beta.sessions.create(
        agent=ids["agent_id"],  # latest version of your agent
        environment_id=ids["environment_id"],
        title=f"Chat {time.strftime('%Y-%m-%d %H:%M')}",
        resources=[
            {
                "type": "memory_store",
                "memory_store_id": ids["memory_store_id"],
                "access": "read_write",
                "instructions": "The user's long-term notes. Check before starting; update with durable learnings.",
            }
        ],
        budget={
            "type": "limit",
            "max_list_cost": {"amount": cfg.SESSION_BUDGET_CENTS, "currency": "USD"},
        },
    )
    return session.id


def ask_permission(event) -> bool:
    """The sandbox wants to run something it couldn't auto-approve: ask you."""
    print(f"\n[The assistant wants to use '{event.name}']")
    print(json.dumps(event.input, indent=2)[:1500])
    try:
        return input("Allow? [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


def describe_action(name: str, inp: dict) -> str:
    """Plain-language preview of what the assistant wants to do."""
    line = "─" * 60
    if name == "send_email":
        parts = [f"✉  SEND EMAIL", f"To:      {', '.join(actions._as_list(inp.get('to')))}"]
        if inp.get("cc"):
            parts.append(f"Cc:      {', '.join(actions._as_list(inp.get('cc')))}")
        parts.append(f"Subject: {inp.get('subject', '')}")
        if inp.get("attachments"):
            parts.append(f"Attach:  {', '.join(inp['attachments'])}")
        parts += [line, inp.get("body", "")]
    elif name == "send_calendar_invite":
        parts = ["📅  SEND MEETING INVITE",
                 f"Title:     {inp.get('title')}",
                 f"Start:     {inp.get('start')}  ({inp.get('duration_minutes')} min)",
                 f"Attendees: {', '.join(actions._as_list(inp.get('attendees')))}",
                 f"Location:  {inp.get('location') or '—'}",
                 line, inp.get("description", "")]
    elif name == "calendar_create_event":
        parts = ["📅  CREATE GOOGLE CALENDAR EVENT",
                 f"Title:     {inp.get('title')}",
                 f"Start:     {inp.get('start')}  ({inp.get('duration_minutes')} min)",
                 f"Attendees: {', '.join(inp.get('attendees') or []) or '— (only you)'}",
                 f"Location:  {inp.get('location') or '—'}"
                 + ("   + Google Meet link" if inp.get("add_meet_link") else ""),
                 line, inp.get("description", "")]
    elif name == "whatsapp_send":
        parts = [f"💬  WHATSAPP MESSAGE to {inp.get('to')}", line, inp.get("message", "")]
    elif name == "facebook_page_post":
        parts = ["📣  PUBLIC POST ON YOUR FACEBOOK PAGE (everyone can see this)"]
        if inp.get("image_filename"):
            parts.append(f"Image: {inp['image_filename']}")
        if inp.get("link"):
            parts.append(f"Link:  {inp['link']}")
        parts += [line, inp.get("message", "")]
    elif name == "drive_upload_file":
        parts = [f"☁  UPLOAD TO GOOGLE DRIVE: {inp.get('filename')}"]
    elif name == "read_inbox":
        parts = [f"📥  READ INBOX   search: {inp.get('search')}   (up to {inp.get('limit') or 10} emails)"]
    else:
        parts = [f"⚙  {name.upper()}", json.dumps(inp, indent=2, ensure_ascii=False)]
    return f"\n{line}\n" + "\n".join(parts) + f"\n{line}"


def log_action(name: str, inp: dict, decision: str, result: str) -> None:
    entry = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "action": name, "input": inp,
             "decision": decision, "result": result[:500]}
    with ACTION_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def handle_action(client: anthropic.Anthropic, session_id: str, event) -> None:
    """The assistant wants to act on your behalf: ask you, then run it (or not)."""
    name, inp = event.name, dict(event.input or {})
    is_error = False

    if name in cfg.AUTO_APPROVE:
        choice = "y"
    else:
        print(describe_action(name, inp))
        print("Permission?  [y] Haan, koro / approve   [n] Na / reject   [e] Change korte bolo / request changes")
        try:
            choice = input("> ").strip().lower()[:1]
        except EOFError:
            choice = "n"

    if choice == "y":
        decision = "approved"
        try:
            if (name == "send_email" and inp.get("attachments")) or (
                name in integrations.NEEDS_OUTPUT_FILES
                and (inp.get("filename") or inp.get("image_filename"))
            ):
                download_files(client, session_id, quiet=True)
            result = actions.run(name, inp)
            print(f"✓ {result.splitlines()[0][:200]}")
        except actions.ActionError as e:
            result, is_error = str(e), True
            print(f"✗ {result}")
    elif choice == "e":
        decision = "changes_requested"
        try:
            feedback = input("Ki change korte hobe? / What should change? ").strip()
        except EOFError:
            feedback = ""
        result = ("The user did NOT approve this action yet. They asked for these changes: "
                  f"{feedback or '(no details)'}. Revise and ask again.")
    else:
        decision = "rejected"
        result = "The user REJECTED this action. Do not retry it unchanged; ask what they want instead."
        print("✗ Rejected — kichu kora hoyni.")

    log_action(name, inp, decision, result)
    client.beta.sessions.events.send(
        session_id=session_id,
        events=[{
            "type": "user.custom_tool_result",
            "custom_tool_use_id": event.id,
            "content": [{"type": "text", "text": result}],
            "is_error": is_error,
        }],
    )


def run_turn(client: anthropic.Anthropic, session_id: str, text: str) -> None:
    """Send one message and print the reply as it arrives."""
    with client.beta.sessions.events.stream(session_id=session_id) as stream:
        client.beta.sessions.events.send(
            session_id=session_id,
            events=[{"type": "user.message", "content": [{"type": "text", "text": text}]}],
        )
        print("\nAssistant: ", end="", flush=True)
        for event in stream:
            if event.type == "agent.message":
                for block in event.content:
                    if block.type == "text":
                        print(block.text, end="", flush=True)
            elif event.type == "agent.custom_tool_use":
                handle_action(client, session_id, event)
            elif event.type == "agent.tool_use":
                if getattr(event, "evaluated_permission", None) == "ask":
                    allowed = ask_permission(event)
                    client.beta.sessions.events.send(
                        session_id=session_id,
                        events=[{
                            "type": "user.tool_confirmation",
                            "tool_use_id": event.id,
                            "result": "allow" if allowed else "deny",
                        }],
                    )
                else:
                    print(f"\n  · working ({event.name})…", end="", flush=True)
            elif event.type == "session.error":
                print(f"\n[error] {getattr(event, 'error', event)}")
            elif event.type == "session.status_idle":
                reason = event.stop_reason.type
                if reason == "requires_action":
                    continue  # waiting on a permission answer above
                if reason == "budget_reached":
                    print(
                        "\n[This chat reached its spending cap "
                        f"(${int(cfg.SESSION_BUDGET_CENTS) / 100:.2f}). Start a new chat.]"
                    )
                print()
                return
            elif event.type == "session.status_terminated":
                print("\n[Session ended]")
                return


def download_files(client: anthropic.Anthropic, session_id: str, quiet: bool = False) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    files = []
    for _ in range(3):  # files can take a few seconds to appear
        files = list(
            client.beta.files.list(scope_id=session_id, betas=["managed-agents-2026-04-01"])
        )
        if files:
            break
        time.sleep(2)
    if not files:
        if not quiet:
            print("No files yet. Ask the assistant to save a document.")
        return
    for f in files:
        dest = OUTPUT_DIR / Path(f.filename).name
        client.beta.files.download(f.id).write_to_file(dest)
        if not quiet:
            print(f"  saved {dest.relative_to(HERE)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--continue", dest="resume", action="store_true", help="resume your last chat")
    args = parser.parse_args()

    client = anthropic.Anthropic()
    ids = load_ids()

    if args.resume and ids.get("last_session_id"):
        session_id = ids["last_session_id"]
        print("Continuing your last chat.")
    else:
        session_id = start_session(client, ids)
        ids["last_session_id"] = session_id
        IDS_FILE.write_text(json.dumps(ids, indent=2) + "\n")

    print("Your assistant is ready. Type a message (/files to download, /quit to exit).")
    print(f"View this chat in the Console: https://platform.claude.com/workspaces/default/sessions/{session_id}")

    while True:
        try:
            text = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text in ("/quit", "/exit"):
            break
        if text == "/files":
            download_files(client, session_id)
            continue
        try:
            run_turn(client, session_id, text)
        except anthropic.RateLimitError:
            print("\n[Too many requests right now. Wait a moment and try again.]")
        except anthropic.APIStatusError as e:
            print(f"\n[API error {e.status_code}: {e.message}]")
        except anthropic.APIConnectionError:
            print("\n[Connection problem. Check your internet and try again.]")

    print("Goodbye. Use  python chat.py --continue  to pick up where you left off.")


if __name__ == "__main__":
    try:
        main()
    except anthropic.AuthenticationError:
        sys.exit("Your API key was rejected. Set ANTHROPIC_API_KEY (see README.md, step 2).")
