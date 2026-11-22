# MZ Academy – Personal AI Assistant

Your own AI executive assistant, powered by Claude (Opus 5.5) and **hosted by
Anthropic** (Claude Managed Agents). It helps with operations, team development,
communications, training content and career coaching, and it **remembers** your
preferences and projects between chats.

| What it does | Examples |
|---|---|
| Operations | SOPs, policies, reports, KPI summaries, meeting agendas & minutes |
| Team development | Training plans, onboarding checklists, review notes, job descriptions |
| Communication | Emails and announcements to staff, students, partners, parents |
| Teaching | Course outlines, lesson plans, workshops, quizzes, slide outlines |
| Career coaching | CV/LinkedIn reviews, interview prep, career roadmaps |
| Files | Saves documents (.md, .docx, .xlsx, .csv) you can download |

## How it works

- **Agent**: Claude with your instructions (`agent_config.py`).
- **Sandbox**: a private workspace on Anthropic's servers where it writes files.
- **Memory**: long-term notes that carry across chats (you can view/edit them in the Console).
- You talk to it with `chat.py` from your computer's terminal.

## Setup (about 10 minutes, once)

**1. Install Python 3.10+** from <https://www.python.org/downloads/>, then in this folder run:

```bash
pip install -r requirements.txt
```

**2. Get an API key**

1. Go to <https://console.anthropic.com>, sign up, and add billing credit (Settings → Billing).
2. Settings → API Keys → **Create Key**. Copy it.
3. Make it available to the scripts (don't paste it into any file you share):
   - macOS/Linux: `export ANTHROPIC_API_KEY="sk-ant-..."`
   - Windows (PowerShell): `$env:ANTHROPIC_API_KEY="sk-ant-..."`

**3. Create your assistant**

```bash
python setup_assistant.py
```

**4. Chat**

```bash
python chat.py              # new chat
python chat.py --continue   # resume the last chat
```

Inside a chat: type normally; `/files` downloads documents it made into `outputs/`; `/quit` exits.

## Try asking

- "Draft an SOP for new-student enrollment, from enquiry to first class."
- "Write a 4-week onboarding plan for a new trainer. Save it as a Word file."
- "Turn these meeting notes into minutes with action items, owners and dates: …"
- "Create a 6-session course outline: *AI tools for creative designers*."
- "Remember that our weekly ops meeting is Sunday 10am, and I prefer bullet-point reports."

## Customising

Edit `agent_config.py`, then run `python setup_assistant.py` again — it **updates** the
same assistant (a new version) rather than making a new one.

- **Instructions/personality**: `SYSTEM_PROMPT`
- **Speed vs depth**: `MODEL` effort `"low"`, `"medium"`, `"high"` (default), `"xhigh"`
- **Spending cap per chat**: `SESSION_BUDGET_CENTS` (default `"500"` = $5)
- **Web research**: off by default. To enable, set `web_search`/`web_fetch` to
  `"enabled": True` in `TOOLS`, and in `ENVIRONMENT_CONFIG` either list the websites it may
  use in `"allowed_hosts": [...]`, or set `"networking": {"type": "unrestricted"}` (gives the
  sandbox full internet access — keep sensitive files out of it). Environment changes
  apply to a new environment: delete `environment_id` from `assistant_ids.json` and re-run setup.

## Costs & privacy

- You pay Anthropic per use: model tokens (Opus 5.5: $4 / $20 per million input/output
  tokens) plus a small sandbox runtime charge (~$0.08/hour while a chat is active).
  Typical everyday chats cost cents; the per-chat cap stops runaway spend.
- Managed Agents is a **beta** service. Chat history and memories are stored in your
  Anthropic account until you delete them (Console → Managed Agents).
- Never ask it to store passwords or keys in memory.

## Files

| File | Purpose |
|---|---|
| `agent_config.py` | Everything you'd want to change |
| `setup_assistant.py` | Creates/updates the assistant (safe to re-run) |
| `chat.py` | Terminal chat |
| `assistant_ids.json` | Created by setup; links the scripts to your assistant (not committed) |
