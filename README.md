# ES-Pulse (Eye Spy Pulse)

An anonymized, privacy-first NLP pipeline that turns public Blind and Low Vision (BVI)
community discussions into a daily, evidence-backed view of what the community is
struggling with most — built for the Eye Spy Foundation (ESF).

ES-Pulse ingests public Reddit discussions, strips all personally identifiable and
medical information before anything is analyzed, classifies posts into recurring
themes, scores how much real friction (not just negative sentiment) each theme
contains, and combines that into a daily **Topic Urgency Score** per theme —
surfaced on a small, accessible public dashboard.

## Why this exists

ESF knew its community was discussing real challenges online, but there was no
practical way to read every post or know which issues were actually most urgent.
This pipeline replaces manual reading with a repeatable, privacy-safe, data-driven
process that feeds:

- **Content strategy** — a daily "what's the community talking about" snapshot to
  inform blog posts, social content, and newsletters without manual research.
- **Resource-gap identification** — surfacing topics with high friction where
  EyeSpy.org's own resource directory may be thin (not yet implemented — see
  Roadmap).
- **Grant proposals** — quantifiable, privacy-safe evidence of community needs.

## Architecture

```
Reddit RSS feeds (r/Blind, ...)
        │  feedparser, retry/backoff on HTTP 429
        ▼
RawRecord  (Postgres) ── raw text, source_id (dedup key)
        │  Presidio + MedSpaCy two-layer PII/PHI masking
        ▼
MaskedRecord ── masked text, entity types found (audit trail only)
        │  sentence-transformers (all-MiniLM-L6-v2) embeddings
        ▼
   ┌────┴─────┐
   ▼          ▼
TopicAssignment          SentimentScore
(focus area via          (VADER polarity +
 cosine similarity to     embedding-based
 reference vectors)       Friction Index)
   │          │
   └────┬─────┘
        ▼
TopicDailyStat ── post_count, avg_friction, avg_polarity,
                  volume_velocity, urgency_score
        │
        ▼
FastAPI  /api/topics/current
        │
        ▼
React dashboard (urgency gauge + bar chart + ranked table)
```

The daily pipeline (`app/pipeline.py`) runs as a separate process from the API
server, scheduled once a day via APScheduler (`app/scheduler.py`), so it never
runs twice under `--reload` or multiple API workers.

## Tech stack

| Layer | Technology |
|---|---|
| Language / API | Python 3.13, FastAPI |
| Database | PostgreSQL 16 (Docker Compose), SQLAlchemy, Alembic migrations |
| Ingestion | `feedparser` against Reddit RSS |
| PII/PHI masking | Presidio (`presidio-analyzer`, `presidio-anonymizer`), MedSpaCy on top of spaCy `en_core_web_lg`, custom `PatternRecognizer`s |
| Embeddings / topic classification | `sentence-transformers` (`all-MiniLM-L6-v2`), cosine similarity to reference vectors |
| Exploratory clustering | HDBSCAN (used to ground the 5 focus-area categories in real data) |
| Sentiment / friction scoring | VADER (`vaderSentiment`), embedding-similarity-based Friction Index |
| Scheduling | APScheduler (`BlockingScheduler`, `CronTrigger`) |
| Frontend | React (Vite), plain CSS (no framework) |
| Testing | pytest |

## Repository structure

```
app/
  config.py              Pydantic Settings, loads .env
  db/session.py           SQLAlchemy engine, session, Base
  models/                 RawRecord, MaskedRecord, TopicAssignment,
                           SentimentScore, TopicDailyStat
  ingestion/
    reddit_rss.py          Reddit RSS ingestion
  services/
    pii_masker.py           Two-layer PII/PHI masking
    embeddings.py            Sentence-transformer wrapper
    topic_classifier.py      Focus-area classification
    sentiment_scorer.py      Polarity + Friction Index
    urgency_engine.py        Daily Topic Urgency Score computation
    retention.py             Raw-text scrubbing after the retention window
    explore_clusters.py      Standalone HDBSCAN exploration (not in production pipeline)
  api/
    topics.py                /api/topics/current endpoint
  main.py                   FastAPI app
  pipeline.py                Orchestrates the daily run, in order
  scheduler.py                Daily cron trigger (6:00 AM America/Los_Angeles)
alembic/                    Migrations (env.py imports every model)
tests/
  test_pii_masker.py         26-case PII/PHI masking test suite
frontend/
  src/
    components/
      FrictionSnapshot.jsx    Headline finding + urgency gauge
      UrgencyGauge.jsx         SVG circular urgency gauge
      UrgencyBarChart.jsx      Cross-topic urgency comparison
      TopicsTable.jsx          Full ranked data table
    constants.js              Shared focus-area labels, urgency bands, trend display
    api.js                     fetchCurrentTopics()
    App.jsx
    index.css
docker-compose.yml            Postgres 16 service
.env.example
```

## Setup

### Prerequisites

- Python 3.13
- Node.js (for the frontend)
- Docker (for Postgres)

### 1. Environment

```bash
cp .env.example .env
```

Fill in `.env`:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string, must match `docker-compose.yml` |
| `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` / `REDDIT_USER_AGENT` | Only needed if moving off RSS to the official Reddit API; RSS ingestion only needs a real `REDDIT_USER_AGENT` string (Reddit rejects generic/default user agents) |
| `GOOGLE_SEARCH_CONSOLE_CREDENTIALS_PATH` | Not yet integrated — reserved for internal query-log ingestion |
| `ENVIRONMENT` | `development` / `production` |
| `LOG_LEVEL` | Standard Python logging level |
| `SQL_ECHO` | `true` to log all SQL (noisy, dev only) |
| `RAW_RETENTION_DAYS` | Days raw (pre-scrub) text is kept after masking; default `7` |

### 2. Database

```bash
docker compose up -d
alembic upgrade head
```

If port `5432` is already in use by a local Postgres install, stop it first
(`lsof -i :5432` to find it) — Docker's container needs that port.

### 3. Python dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt --break-system-packages
python -m spacy download en_core_web_lg
```

### 4. Frontend dependencies

```bash
cd frontend
npm install
```

## Running it

**Run the full pipeline once, manually:**
```bash
python -m app.pipeline
```
Runs, in order: ingest RSS → mask PII/PHI → classify topics → score sentiment/friction
→ compute daily urgency stats → scrub expired raw text. Stops at the first failed step.

**Run on a daily schedule:**
```bash
python -m app.scheduler          # starts the blocking 6:00 AM daily schedule
python -m app.scheduler --now    # runs once immediately, for testing
```

**Run the API:**
```bash
uvicorn app.main:app --reload
```
`GET /api/topics/current` returns today's ranked topics; `GET /health` is a liveness check.

**Run the frontend:**
```bash
cd frontend
npm run dev
```
CORS is currently allowlisted for `http://localhost:5173` and `http://localhost:3000` in `app/main.py` — if Vite picks a different port, update that list.

**Run tests:**
```bash
pytest tests/test_pii_masker.py -v
```

## Data model

| Table | Purpose |
|---|---|
| `raw_records` | Original ingested text; scrubbed to a placeholder after masking + `RAW_RETENTION_DAYS` |
| `masked_records` | PII/PHI-masked text, plus an audit trail of entity *types* found (never values) |
| `topic_assignments` | Focus-area classification per post, similarity score, stored embedding |
| `sentiment_scores` | Polarity and Friction Index per post |
| `topic_daily_stats` | Daily aggregates per focus area: post count, avg friction/polarity, volume velocity, urgency score |

Five focus areas, derived from unsupervised clustering on real data rather than
assumed up front: Assistive Tech & Digital Access, Orientation & Mobility,
Community/Identity/Social, Healthcare & Vision Diagnosis, Daily Living.

## Privacy approach

- Two-layer masking: Presidio for general PII (names, emails, phone numbers, URLs,
  SSNs, social handles via custom pattern recognizers), MedSpaCy for medical
  condition mentions — with family-member and negation exclusion, so "my brother
  has diabetes" isn't flagged as the poster's own condition.
- Per-entity confidence thresholds (Presidio's default global threshold isn't
  right for every entity type; phone numbers in particular need a lower bar).
- Raw text is only retained for `RAW_RETENTION_DAYS` after masking, then
  permanently overwritten with a placeholder — only `source_id` (for dedup) and
  `source_created_at` (for date bucketing) survive.
- The masker is covered by a 26-case pytest suite using entirely invented example
  text — real user posts are never committed to this repo.

## Known limitations / roadmap

- **Google Search Console integration** not built — blocked on credentials.
- **Resource-gap analysis** (cross-referencing high-friction topics against
  EyeSpy.org's verified listings) depends on the above.
- **No live accessibility audit** — contrast ratios are verified numerically, but
  the dashboard hasn't been tested with a real screen reader or a BVI tester yet.
- **Not deployed** — the scheduler and API currently only run on a developer
  machine; a sleeping/closed laptop means a missed daily run.
- **Urgency formula weights** (volume velocity / engagement / friction, currently
  0.4 / 0.2 / 0.4) are placeholders, not yet reviewed
- **Subreddit sourcing** — only `r/Blind` has been confirmed active and on-topic;
  any additional subreddits added should be vetted before being relied on.


