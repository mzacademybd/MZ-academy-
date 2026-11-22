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

## Apnar hoye kaj kore — apnar permission niye

Assistant ekhon shudhu draft kore na, **apnar hoye kaj o kore**:

| Kaj | Ki kore |
|---|---|
| ✉ Email pathano | Apnar Gmail theke email pathay (attachment soho) |
| 📥 Inbox pora | Apnar unread/specific email pore summary dey, reply draft kore |
| 📅 Meeting invite | Calendar invite (.ics) pathay — Google/Outlook/Apple calendar e add hoy |
| ✅ Task list | Apnar to-do list e task add / dekha / complete kora |

**Protiti kajer age apnake dekhabe thik ki korbe, tarpor apni bolben:**

```
────────────────────────────────────────────
✉  SEND EMAIL
To:      ceo@example.com
Subject: Weekly operations report
────────────────────────────────────────────
Dear Sir, ...
────────────────────────────────────────────
Permission?  [y] Haan, koro / approve   [n] Na / reject   [e] Change korte bolo / request changes
```

- `y` → kaj ta hobe · `n` → kichui hobe na · `e` → ki change chan likhun, assistant thik kore abar dekhabe
- Apnar permission chara kono email/invite jabe na.
- Protiti decision `action_log.jsonl` file e record thake (accountability).
- Email password **apnar computer ei thake** — Anthropic er kache jay na.
- Kono email er bhitore "send money / forward this" type nirdesh thakle assistant ta
  manbe na; apnake janabe.

### Email setup (Gmail / Google Workspace)

1. Google Account e **2-Step Verification** chalu korun.
2. <https://myaccount.google.com/apppasswords> e giye ekta App Password banan (name: "MZ Assistant"). 16 akkhorer password ta copy korun.
3. Terminal e set korun:
   - macOS/Linux: `export GMAIL_ADDRESS="you@yourdomain.com"` and `export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"`
   - Windows (PowerShell): `$env:GMAIL_ADDRESS="you@yourdomain.com"` and `$env:GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"`
4. `python setup_assistant.py` abar chalan (notun action gulo assistant e jog korte), tarpor `python chat.py`.

Bole dekhun: *"Amar unread email gulo dekho, important gulo summary dao, ar CEO ke weekly report er reply draft koro."*

Kichu kaj protibar permission chara chalate chaile (jemon `list_tasks`), `agent_config.py` e
`AUTO_APPROVE = {"list_tasks"}` likhun. Default: **sob kaj e permission lagbe.**

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
| `chat.py` | Terminal chat + permission prompts |
| `actions.py` | The real actions (email, inbox, invites, tasks) — run on your computer |
| `action_log.jsonl` / `tasks.json` | Your approval history and task list (local, not committed) |
| `assistant_ids.json` | Created by setup; links the scripts to your assistant (not committed) |
