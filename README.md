# Gold and Silver Telegram Agent

A small Python automation that reads Goldmeter's per-gram 24K, 22K, 18K gold, and silver rates and sends them to one Telegram chat using Telegram's Bot API. Telegram bot messaging is free for this low-volume use. Groq is not needed: there is no LLM step in this workflow.

The parser uses Goldmeter's live India price summary, with a fallback to its dedicated rates table. It rejects redirects to other hosts and sends nothing if all four rates cannot be identified safely.

## Setup

1. Install Python 3.10 or newer.
2. Open a PowerShell terminal in this folder and create the virtual environment and install dependencies:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. In Telegram, open `@BotFather`, send `/newbot`, and follow its prompts. Copy the resulting token into `TELEGRAM_BOT_TOKEN` in `.env`. Never share the token or commit `.env`.
4. Open a chat with your new bot and send `/start` so the bot can message you.
5. Find your chat ID by running:

   ```powershell
   .\.venv\Scripts\python.exe main.py --show-chat-id
   ```

   Copy the matching numeric ID into `TELEGRAM_CHAT_ID` in `.env`.
6. Set `INTERVAL_HOURS` to the time between notifications in hours. It defaults to `24`.

The `.env` file is excluded from Git. The required settings are `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and optionally `INTERVAL_HOURS`. No bot token or chat ID is included in the project template.

## Run

Preview a fetched message without sending it:

```powershell
.\.venv\Scripts\python.exe main.py --dry-run
```

Send once after configuration:

```powershell
.\.venv\Scripts\python.exe main.py --once
```

Run continuously, sending immediately and then once every `INTERVAL_HOURS` (default `3`):

```powershell
.\.venv\Scripts\python.exe main.py
```

The dry run only fetches and previews rates. `--once` sends one Telegram message. Running without either option sends immediately and repeats every `INTERVAL_HOURS` (`3` hours by default; set it to `2` for every two hours).

For unattended Windows operation, create a Task Scheduler task with an **At log on** trigger and a **Start a program** action:

- **Program/script:** `C:\Users\POOJITHA\Documents\AI Agents 101\AI agent 101\.venv\Scripts\python.exe`
- **Add arguments:** `main.py`
- **Start in:** `C:\Users\POOJITHA\Documents\AI Agents 101\AI agent 101`

This starts one continuous process that sends immediately and then every three hours. Do not also create a repeating trigger for `main.py`, or multiple copies could send duplicate messages. The computer must remain awake and connected to the internet; the loop pauses while it is asleep or off.

## GitHub Actions Cloud Schedule

The workflow at `.github/workflows/gold-silver-rates.yml` runs at 17 minutes past every third hour (UTC), and can also be started manually from the repository's **Actions** tab. Unlike the local loop, each workflow run sends one message and then exits. The GitHub-hosted runner means your PC does not need to be on.

1. Create a **private** GitHub repository and push this project to it. Do not commit `.env`; it is ignored by Git. If a Telegram bot token was ever committed or shared, revoke it with `@BotFather` before continuing.
2. In the repository, open **Settings > Secrets and variables > Actions** and create these repository secrets:
   - `TELEGRAM_BOT_TOKEN`: the token from `@BotFather`.
   - `TELEGRAM_CHAT_ID`: your numeric Telegram chat ID.
3. Open **Actions**, enable workflows if GitHub prompts you, and run **Send gold and silver rates** once with **Run workflow** to test it.

The schedule uses UTC and GitHub may delay scheduled runs during heavy load. GitHub's standard hosted runners are free for public repositories; private repositories use the included minutes for your plan. GitHub Free currently includes 2,000 minutes per month, which is generally ample for a short job running every three hours, but check your account's current usage and limits.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The Telegram message contains these lines, with each price expressed per gram:

```text
Gold (24K): ₹<rate> per gram
Gold (22K): ₹<rate> per gram
Gold (18K): ₹<rate> per gram
Silver: ₹<rate> per gram
```

The parser does not reuse or guess missing rates. Check the dry-run output before enabling sends.
