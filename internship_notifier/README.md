# Internship Notifier

## 1. What this does

A self-contained Python module that watches three job sources every 3 hours and pushes Telegram messages whenever a new summer 2026 AI/ML/SWE internship that's realistic for F-1 students gets posted. It deduplicates against a committed JSON file in this repo, so you never get the same listing twice across runs. It runs on GitHub Actions free tier with no server or database.

## 2. One-time setup

### Step 1: Create the Telegram bot

- Open Telegram and message **@BotFather**
- Send `/newbot`
- Follow prompts, give it any display name and any unique username (ending in `_bot`)
- Copy the API token BotFather gives you (looks like `1234567890:ABCDEFghijklmno...`)

### Step 2: Get your Telegram chat ID

- Message your new bot once (send it anything — a `hi` works)
- Open this URL in your browser (replace `TOKEN`):
  ```
  https://api.telegram.org/bot{TOKEN}/getUpdates
  ```
- Find `"chat": {"id": XXXXXXXXX}` in the JSON response
- That number is your chat ID

### Step 3: Add GitHub secrets

In your GitHub repo:
- Go to **Settings → Secrets and variables → Actions**
- Add two repository secrets:
  - `TELEGRAM_BOT_TOKEN` — the token from Step 1
  - `TELEGRAM_CHAT_ID` — the number from Step 2

### Step 4: Initialize seen_ids.json

Already done — `internship_notifier/data/seen_ids.json` exists with `[]`. Just commit + push.

### Step 5: Test manually

- Go to the **Actions** tab in GitHub
- Find the **"Internship Notifier"** workflow
- Click **Run workflow** → confirm
- Check your Telegram within 2 minutes — first run will likely send a batch (up to 10 listings)

## 3. Filters

A listing must pass all of these to be sent:

**Surfaced if:**
- Active and visible (SimplifyJobs only)
- Title contains one of: `ai`, `ml`, `machine learning`, `llm`, `nlp`, `applied scientist`, `research`, `data science`, `software engineer`, `backend`, `full stack`, `fullstack`, `platform`, `infrastructure`
- Category (SimplifyJobs only) is `Data Science, AI & Machine Learning` or `Software Engineering`

**Rejected if:**
- Sponsorship field says "Not available"
- Notes contain: `us citizen`, `no sponsorship`, `no cpt`, `no opt`, `security clearance`, `ts/sci`, etc.
- Title contains: `hardware`, `fpga`, `embedded`, `firmware`, `electrical`, `mechanical`, `civil`, `sales`, `marketing`, `finance`, `accounting`, `legal`, `hr `, `recruiter`
- Company name matches any entry in `REJECT_COMPANIES` (empty by default)

To tune: edit `internship_notifier/filters.py` directly. Lists are at the top.

## 4. Adjusting cron frequency

Edit `.github/workflows/internship_notifier.yml`:

```yaml
on:
  schedule:
    - cron: '0 */3 * * *'   # every 3 hours
```

Common alternatives:
- `'0 */1 * * *'` — every hour
- `'0 */6 * * *'` — every 6 hours
- `'0 13,21 * * *'` — twice a day, 9 AM and 5 PM ET

## 5. Muting a specific company

Edit `internship_notifier/filters.py` and add to `REJECT_COMPANIES`:

```python
REJECT_COMPANIES = ["Acme Corp", "BoringCo"]
```

Case-insensitive substring match.

## 6. Running locally

```bash
cd /path/to/repo
pip install -r internship_notifier/requirements.txt
export TELEGRAM_BOT_TOKEN=...
export TELEGRAM_CHAT_ID=...
python internship_notifier/notifier.py
```
