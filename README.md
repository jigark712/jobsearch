# Job-Search System

Personal job-discovery, scoring, and tracking system for Jigar Kanakhara (BU MS CS, F-1).

Three parallel tracks from one ingestion pipeline:

1. **Full-time** roles starting ~Jan 2027 (primary)
2. **Late-cycle summer 2026 internships** at small / YC startups (active until 2026-07-15)
3. **Boston-based part-time fall 2026 internships** (CPT)

Full spec: `../job_search_system_spec.md`.

## Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in API keys
```

## Project layout

```
config/             owner-provided YAML/JSON (preferences, companies, resume, project bank)
.secrets/           gitignored session cookies + OAuth tokens
src/ingest/         one module per source (greenhouse, lever, ashby, ...)
src/gates/          universal + per-track hard-gate filters
src/scoring/        12-component scoring rubric, one module per component
src/tracker/        Gmail watcher + Google Sheet client
src/prompts/        LLM prompts as .txt files (edit to retune; never hardcoded)
scripts/            cron entrypoints
data/               outputs: ingested jobs, digests, retros, alerts, logs
```

## Build order

Strict — see spec section 1. MVP = milestones 1–7. Post-MVP only after MVP runs cleanly for 2+ weeks.

## Hard prohibitions

- Never auto-applies. Never auto-sends outreach. Never auto-edits the resume file.
- Never scrapes LinkedIn (RSS + manual prompts only).
- Never deletes tracker rows. Never writes the offer column.
