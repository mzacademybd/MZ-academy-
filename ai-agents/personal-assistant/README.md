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
| 🗓 Google Calendar | Apnar schedule dekha, sorasori event + Google Meet link toiri |
| ☁ Google Drive | File khuje ber kora, Docs/Sheets pora, notun document Drive e upload |
| 💬 WhatsApp | Message pathano (Business API diye, othoba WhatsApp khule ready message) |
| 📣 Facebook Page | MZ Academy er Page e post (text, link, chhobi) |

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

### Google setup (Calendar + Drive) — ekbar

1. <https://console.cloud.google.com> e jan → notun Project banan (name: "MZ Assistant").
2. **APIs & Services → Library** theke **Google Calendar API** ar **Google Drive API** enable korun.
3. **Google Auth Platform → Branding** (OAuth consent screen) setup korun: app name din, User type
   **Internal** (Google Workspace hole) ba **External**. External hole **Audience → Test users** e
   nijer email add korun.
4. **Clients → Create client → Desktop app**. JSON download kore ei folder e
   `google_credentials.json` name e rakhun.
5. Chalan: `python connect_google.py` → browser khulbe → login kore **Allow** korun.

Bole dekhun: *"Ei shoptaher amar meeting gulo dekhao"*, *"Drive e 2026 budget file ta khuje summary dao"*.

### WhatsApp setup

- **Kono setup chara-i kaj kore:** assistant WhatsApp (web/desktop) khule message ready kore
  rakhbe — apni shudhu **Send** chapben.
- **Puro automatic chaile (WhatsApp Business Cloud API):** <https://developers.facebook.com> e
  app banan → WhatsApp product add korun → **Phone number ID** ar ekta **permanent access token**
  (System User token) nin, tarpor set korun:
  `WHATSAPP_PHONE_NUMBER_ID="..."` ar `WHATSAPP_TOKEN="..."`.
  Note: Meta er niyom onujayi, je 24 ghontar moddhe apnake message dey nai, take shudhu
  approved *template* message pathano jay.

### Facebook Page setup

1. <https://developers.facebook.com> e app banan (type: Business), **Pages** permission add korun
   (`pages_manage_posts`, `pages_read_engagement`).
2. **Graph API Explorer** e nijer Page select kore **Page access token** nin (long-lived/System
   User token nile bhalo — expire hoy na).
3. Set korun: `FACEBOOK_PAGE_ID="..."` ar `FACEBOOK_PAGE_TOKEN="..."`.

Bole dekhun: *"Amader notun AI course er jonno ekta Facebook post likho"* — assistant post ta
dekhabe, apni `y` dile tobei publish hobe.

> Sob setup er por `python setup_assistant.py` ekbar chalan, jate assistant notun kaj gulo jane.
> Je setup ta korben na, sei kaj ta assistant apnake bolbe "eta setup kora nai" ar draft kore
> dibe — onno sob kaj thik moto cholbe.

Kichu kaj protibar permission chara chalate chaile (jemon `list_tasks`), `agent_config.py` e
`AUTO_APPROVE = {"list_tasks"}` likhun. Default: **sob kaj e permission lagbe.**

## Telegram bot (phone theke assistant chalan)

`telegram_bot.py` apnar assistant ke Telegram bot e niye ashe. Kono kaj korar age bot
**✅ Approve / ❌ Reject / ✏️ Change** button pathay. Shudhu apni (owner) use korte parben.
Onno keu message dile bot use korte dey na.

**Mac e ekbar setup (Terminal e):**

```bash
git clone -b claude/ai-agents-wxqpi2 https://github.com/mzacademybd/MZ-academy-.git
cd MZ-academy-/ai-agents/personal-assistant
python3 -m pip install -r requirements.txt
cp .env.example .env
open -e .env          # ANTHROPIC_API_KEY ar TELEGRAM_BOT_TOKEN boshiye Save korun
python3 setup_assistant.py
python3 telegram_bot.py
```

1. Telegram e bot ke `/start` pathan. Bot apnar **Telegram ID** bolbe.
2. Seta `.env` e `TELEGRAM_OWNER_ID=...` te boshan. Terminal e `Ctrl + C` chepe bot thamiye din.
3. Auto-start chalu korun:

```bash
./install_mac_service.sh
```

Ekhon theke Mac restart holeo ba bot crash korleo bot **nije abar chalu hobe**. Bot cholar shomoy
Mac idle sleep e jabe na. Tobe laptop er lid bondho korle ba power off korle bot bondho thakbe.
Log dekhte: `logs/bot.log`. Auto-start bondho korte: `./install_mac_service.sh --remove`.

Bot er command: `/new` notun conversation · `/files` banano file · `/tasks` task list · `/help`

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
| `integrations.py` | Google Calendar, Google Drive, WhatsApp, Facebook Page actions |
| `telegram_bot.py` / `install_mac_service.sh` | Telegram bot with approval buttons; Mac auto-start |
| `.env.example` | Template for your private settings (copy to `.env`, never commit) |
| `connect_google.py` | One-time Google login (saves `google_token.json`, not committed) |
| `action_log.jsonl` / `tasks.json` | Your approval history and task list (local, not committed) |
| `assistant_ids.json` | Created by setup; links the scripts to your assistant (not committed) |
