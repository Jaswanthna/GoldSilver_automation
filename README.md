# Gold and Silver Telegram Agent

A small Python automation that sends configured data to one Telegram chat using Telegram's Bot API. By default, it reads Goldmeter's per-gram 24K, 22K, 18K gold, and silver rates. Telegram bot messaging is free for this low-volume use. Groq is not needed: there is no LLM step in this workflow.

By default, the parser uses Goldmeter's live India price summary, with a fallback to its dedicated rates table. It rejects redirects and sends nothing if all four rates cannot be identified safely. An optional JSON configuration lets you use another HTTPS HTML or JSON source and define the Telegram message with placeholders.

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
6. Optionally set `INTERVAL_HOURS` to the time between checks in hours. It defaults to `3`.

The `.env` file is excluded from Git. The required settings are `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`; `INTERVAL_HOURS` and `MESSAGE_SOURCE_CONFIG` are optional. No bot token or chat ID is included in the project template.

The first successful scheduled run sends the current rates and saves them as the baseline. Each later run compares the latest prices with that saved baseline: if any price changed, it sends the full rate message; otherwise, it sends `No change in the price`. The baseline is updated only after Telegram accepts the message. Dry runs preview the message without sending it or changing the baseline. Local runs save state in the ignored `.last_prices.json` file. GitHub Actions restores and updates that state through its cache between scheduled runs.

## Configure another source and message

The existing Goldmeter workflow remains the default. To use a different source, copy [`examples/message-source.example.json`](./examples/message-source.example.json) to a local JSON file (for example, `message-source.json`) and set this in `.env`:

```text
MESSAGE_SOURCE_CONFIG=message-source.json
```

Replace the example URL and fields with those from the source you actually want to use. The example uses a JSON API. A JSON field's `path` uses JSON Pointer syntax, such as `/data/price`. `compare_fields` lists which extracted values count as prices for change detection; keep changing metadata such as `updated_at` out of this list. For an HTML page, set `"format": "html"` and define each field with a CSS `selector`; an optional `pattern` can extract a single capture group from that element's text. For example:

```json
{
  "url": "https://your-site.example/current",
  "format": "html",
  "fields": {
    "price": {
      "selector": "#current-price",
      "pattern": "₹\\s*([0-9,]+)"
    }
  },
  "template": "Current price: ₹{{price}}"
}
```

The template can use `{{field_name}}` placeholders for configured fields. A field that cannot be found, parsed, or is empty causes the run to fail without sending a message. The fetcher requires HTTPS, checks the expected response type, and refuses redirects. The generic mode fetches the page/API response directly; it does not run JavaScript or automatically infer where data is on arbitrary websites. Prefer an official API/feed where available, and verify that the source's update time is represented if freshness matters. Run `--dry-run` to verify the extracted values and rendered message before enabling sends. Remove `MESSAGE_SOURCE_CONFIG` to return to the built-in Goldmeter workflow.

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

The dry run fetches and previews the message that would be sent without changing the saved baseline. The first successful run sends the full rates; subsequent runs send the full rates only if prices changed, or `No change in the price` if they did not. `--once` sends one Telegram message. Running without either option sends immediately and repeats every `INTERVAL_HOURS` (`3` hours by default; set it to `2` for every two hours).

For unattended Windows operation, create a Task Scheduler task with an **At log on** trigger and a **Start a program** action:

- **Program/script:** `.\AI Agents 101\AI agent 101\.venv\Scripts\python.exe`
- **Add arguments:** `main.py`
- **Start in:** `.\AI Agents 101\AI agent 101`

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
