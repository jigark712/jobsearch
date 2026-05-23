# Internship Notifier

## 1. What this does

A self-contained Python module that watches three job sources every 3 hours and posts to a Discord channel whenever a new summer 2026 AI/ML/SWE internship that's realistic for F-1 students gets posted. It deduplicates against a committed JSON file in this repo, so you never get the same listing twice across runs. It runs on GitHub Actions free tier with no server or database.

## 2. One-time setup

### Step 1: Create a Discord webhook

- Open Discord (desktop or https://discord.com/app)
- Create a server if you don't have one (`+` button in left sidebar → Create My Own → For me and my friends)
- Create a text channel (e.g. `#internships`)
- Right-click the channel → **Edit Channel** → **Integrations** → **Webhooks** → **Create Webhook**
- (Optional) name the webhook `Internship Notifier`
- Click **Copy Webhook URL** — looks like `https://discord.com/api/webhooks/12345/abcXYZ...`

### Step 2: Add GitHub secret

In your GitHub repo:
- Go to **Settings → Secrets and variables → Actions**
- Add one repository secret:
  - `DISCORD_WEBHOOK_URL` — the URL from Step 1

### Step 3: Initialize seen_ids.json

Already done — `internship_notifier/data/seen_ids.json` exists with `[]`. Just commit + push.

### Step 4: Test manually

- Go to the **Actions** tab in GitHub
- Find the **"Internship Notifier"** workflow
- Click **Run workflow** → confirm
- Check your Discord channel within 2 minutes — first run will silently mark old listings as seen and post a single "✅ Internship notifier is live" confirmation (backfill protection). Future runs will alert on genuinely new postings only.

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
export DISCORD_WEBHOOK_URL='https://discord.com/api/webhooks/...'
python internship_notifier/notifier.py
```
