# Setup guide

## 1. Install

```bash
cd "/Users/Asus/Documents/job search/code system/job_search_system"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:
- `ANTHROPIC_API_KEY` — your Anthropic key
- `OWNER_EMAIL` — `jigar.work712@gmail.com`
- `JOB_TRACKER_SHEET_ID` — the ID from your Google Sheet URL (between `/d/` and `/edit`)

## 2. Run end-to-end once

```bash
source .venv/bin/activate
python scripts/run_ingest_tier1.py     # ingest from Greenhouse / Lever / Ashby / Workday / GitHub repos
python scripts/run_digest.py --no-email --print   # build today's digest, print to stdout, skip email
```

The digest file is written to `data/digests/YYYY-MM-DD.md` either way.

## 3. Hook up Gmail (M4)

1. Create a Gmail label called `job-applications`.
2. Create filters that auto-label confirmation emails:
   - Sender contains `no-reply@greenhouse.io`, `@lever.co`, `@ashbyhq.com`, `@myworkdayjobs.com`, etc.
   - Subject contains `application` / `we received` / `interview` / `online assessment`
3. Create a Google Cloud OAuth client (Desktop App type). Download JSON to `.secrets/gmail_oauth_client.json`.
4. Run once interactively to authorize:
   ```bash
   python scripts/run_gmail_watcher.py
   ```
   Browser opens. Approve. Token saved to `.secrets/gmail_oauth_token.json`.

## 4. Hook up Google Sheet (M4)

1. Create a Google Sheet called "Job Tracker". The script creates the worksheet + headers on first run.
2. Create a Google Cloud Service Account, download its JSON key to `.secrets/google_service_account.json`.
3. Share your sheet with the service-account email (found in the JSON).
4. Put the sheet ID into `.env` as `JOB_TRACKER_SHEET_ID`.
5. Set `GOOGLE_APPLICATION_CREDENTIALS=./.secrets/google_service_account.json` in `.env`.

## 5. Hook up Tier 2 sources (M5)

### Jobright
Log into jobright.ai, open DevTools → Application → Cookies, copy the session cookie value.
Save to `.secrets/jobright_session.txt` (one line, just the cookie value).

### Handshake (BU)
Log into `bu.joinhandshake.com`, copy your session cookie. Save to
`.secrets/handshake_session.txt`. Re-export weekly (Handshake invalidates often).

### Twitter watch (Nitter)
Edit `config/companies.yaml` → `twitter_x.watchlist_accounts` and add Twitter handles
(no `@` prefix) of founders, recruiters, eng leads at your target companies.

### LinkedIn RSS
LinkedIn does NOT publish RSS for arbitrary jobs. For verified company pages
that do offer RSS, add the URL to `config/companies.yaml` → `linkedin.rss_feeds`.

## 6. Schedule (M7)

Two options.

### Option A — Local Mac launchd

Create `~/Library/LaunchAgents/com.jigar.jobsearch.tier1.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.jigar.jobsearch.tier1</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/Asus/Documents/job search/code system/job_search_system/.venv/bin/python</string>
    <string>/Users/Asus/Documents/job search/code system/job_search_system/scripts/run_ingest_tier1.py</string>
  </array>
  <key>StartInterval</key><integer>14400</integer>  <!-- every 4h -->
  <key>StandardOutPath</key><string>/Users/Asus/Documents/job search/code system/job_search_system/data/logs/launchd-tier1.log</string>
  <key>StandardErrorPath</key><string>/Users/Asus/Documents/job search/code system/job_search_system/data/logs/launchd-tier1.err</string>
</dict>
</plist>
```

Load it:
```bash
launchctl load ~/Library/LaunchAgents/com.jigar.jobsearch.tier1.plist
```

Repeat for the other cron-style entrypoints:

| Plist | Script | Interval |
|---|---|---|
| `com.jigar.jobsearch.tier1` | `run_ingest_tier1.py` | 4h (14400) |
| `com.jigar.jobsearch.tier2` | `run_ingest_tier2.py` | 1d (86400) |
| `com.jigar.jobsearch.twitter` | `run_ingest_twitter.py` | 2h (7200) |
| `com.jigar.jobsearch.digest` | `run_digest.py` | Daily at 6:30 AM ET (use `StartCalendarInterval` instead of `StartInterval`) |
| `com.jigar.jobsearch.gmail` | `run_gmail_watcher.py` | 2h (7200) |
| `com.jigar.jobsearch.retro` | `run_weekly_retro.py` | Sunday 6 PM (StartCalendarInterval) |

### Option B — GitHub Actions cron

Push the repo (excluding `.env` and `.secrets/`) to a private GitHub repo.
Add all `.env` vars + `.secrets/*` files as GitHub Action Secrets, then add `.github/workflows/jobsearch.yml`:

```yaml
on:
  schedule:
    - cron: "0 */4 * * *"   # tier1 every 4h
    - cron: "30 10 * * *"   # digest 6:30 AM ET = 10:30 UTC
    - cron: "0 22 * * 0"    # weekly retro Sunday 6 PM ET = 22 UTC
jobs:
  ingest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          JOB_TRACKER_SHEET_ID: ${{ secrets.JOB_TRACKER_SHEET_ID }}
        run: |
          echo '${{ secrets.GOOGLE_SERVICE_ACCOUNT }}' > .secrets/google_service_account.json
          python scripts/run_ingest_tier1.py
          python scripts/run_digest.py
      - uses: actions/upload-artifact@v4
        with: { name: digests, path: data/digests/ }
```

Pick one (the spec says owner decides). Local Mac is simpler; GitHub Actions is more resilient.

## 7. Daily routine

- 6:30 AM ET — digest email arrives. Read in <5 minutes.
- Apply to the `apply_today` items first.
- Owner does NOT touch the Google Sheet manually — Gmail watcher fills `applied_date` automatically when confirmation emails come in.
- Sunday 6 PM ET — weekly retro arrives + an email asking about any untracked applications.

## What this system never does

See spec section 9. The hard prohibitions: never auto-applies, never sends outreach without your review, never edits the resume file, never scrapes LinkedIn, never deletes tracker rows, never writes the offer column.
