"""Chat with your personal assistant in the terminal.

    python chat.py              start a new conversation
    python chat.py --continue   pick up your last conversation

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

import agent_config as cfg

HERE = Path(__file__).parent
IDS_FILE = HERE / "assistant_ids.json"
OUTPUT_DIR = HERE / "outputs"


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


def download_files(client: anthropic.Anthropic, session_id: str) -> None:
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
        print("No files yet. Ask the assistant to save a document.")
        return
    for f in files:
        dest = OUTPUT_DIR / Path(f.filename).name
        client.beta.files.download(f.id).write_to_file(dest)
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
