"""One-time setup (safe to re-run).

Creates - or updates - your assistant on Anthropic's platform:
  1. an environment (the private sandbox where the assistant works with files)
  2. a memory store (long-term notes that persist between chats)
  3. the agent itself (model, instructions, tools)

The IDs are saved to assistant_ids.json so chat.py can find them.
Re-run this after editing agent_config.py to apply your changes.
"""

import json
from pathlib import Path

import anthropic

import agent_config as cfg

IDS_FILE = Path(__file__).with_name("assistant_ids.json")


def load_ids() -> dict:
    if IDS_FILE.exists():
        return json.loads(IDS_FILE.read_text())
    return {}


def save_ids(ids: dict) -> None:
    IDS_FILE.write_text(json.dumps(ids, indent=2) + "\n")


def main() -> None:
    client = anthropic.Anthropic()
    ids = load_ids()

    # 1. Environment
    if "environment_id" not in ids:
        env = client.beta.environments.create(
            name=cfg.ENVIRONMENT_NAME, config=cfg.ENVIRONMENT_CONFIG
        )
        ids["environment_id"] = env.id
        save_ids(ids)
        print(f"Created environment   {env.id}")
    else:
        print(f"Using environment     {ids['environment_id']}")

    # 2. Memory store (+ starter notes)
    if "memory_store_id" not in ids:
        store = client.beta.memory_stores.create(
            name=cfg.MEMORY_STORE_NAME, description=cfg.MEMORY_STORE_DESCRIPTION
        )
        ids["memory_store_id"] = store.id
        save_ids(ids)
        for path, content in cfg.SEED_MEMORIES.items():
            client.beta.memory_stores.memories.create(store.id, path=path, content=content)
        print(f"Created memory store  {store.id} (with {len(cfg.SEED_MEMORIES)} starter notes)")
    else:
        print(f"Using memory store    {ids['memory_store_id']}")

    # 3. Agent: create once, then update in place (each change = new version)
    agent_fields = dict(
        name=cfg.AGENT_NAME,
        model=cfg.MODEL,
        system=cfg.SYSTEM_PROMPT,
        tools=cfg.TOOLS,
    )
    if "agent_id" not in ids:
        agent = client.beta.agents.create(**agent_fields)
        print(f"Created agent         {agent.id} (version {agent.version})")
    else:
        agent = client.beta.agents.update(ids["agent_id"], **agent_fields)
        print(f"Updated agent         {agent.id} (now version {agent.version})")
    ids["agent_id"] = agent.id
    ids["agent_version"] = agent.version
    save_ids(ids)

    print("\nDone. Start chatting with:  python chat.py")


if __name__ == "__main__":
    try:
        main()
    except anthropic.AuthenticationError:
        raise SystemExit(
            "Your API key was rejected. Set ANTHROPIC_API_KEY (see README.md, step 2)."
        )
    except anthropic.APIConnectionError:
        raise SystemExit("Could not reach Anthropic. Check your internet connection.")
