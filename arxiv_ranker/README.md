# arxiv_ranker

Streamlit app + CLI for ranking `paperposterbot.bsky.social` arXiv posts by engagement, with a local SQLite cache for speed.

Public path on this server: `https://lalten.org/arxiv_methods_charts/`

## What This App Does

- Fetches Bluesky posts for an actor (default: `paperposterbot.bsky.social`)
- Keeps only posts linking to `arxiv.org`
- Computes engagement as:
  - `likes + replies + reposts + quotes`
- Ranks and displays top papers for a selected UTC date window
- Dedupes paper versions by canonical arXiv key (e.g. `v1`, `v2` collapse to one paper)

## Why Caching Exists

Without caching, each query re-scans feed history and sorts in memory. For long windows (months/year), that is slow.

With caching:

- New requests do incremental sync (only newer feed items)
- Older windows trigger one-time backfill to the requested start date
- Results are read from local SQLite after sync

This keeps UI behavior the same while reducing repeated latency.

## Core Design

Code files:

- `bsky_paperbot/streamlit_app.py`: web UI
- `bsky_paperbot/rank_papers.py`: ingestion, canonicalization, cache, ranking logic

### Data Model

Database file:

- `bsky_paperbot/paper_scores.db`

Tables:

1. `paper_score_log`
- One row per post (`PRIMARY KEY (actor, post_uri)`)
- Stores raw-ish scoring snapshots per post
- Used for window filtering + per-post audit trail

2. `paper_scores`
- One row per deduped paper (`PRIMARY KEY (actor, arxiv_key)`)
- `arxiv_key` is canonicalized and version-stripped
- Stores representative best-engagement post and aggregate counters (`mention_count`, first/last seen)

3. `sync_state`
- One row per actor
- Tracks newest `created_at` ingested to enable incremental sync

### Canonical arXiv Key Logic

`canonicalize_arxiv_key()` normalizes links:

- Accepts `arxiv.org/abs/...` and `arxiv.org/pdf/...`
- Strips `.pdf` suffix
- Strips version suffix like `v2`
- Lowercases the key

Examples:

- `https://arxiv.org/abs/2501.12345v3` -> `2501.12345`
- `https://arxiv.org/pdf/2501.12345v2.pdf` -> `2501.12345`
- `https://arxiv.org/abs/math/0301234v1` -> `math/0301234`

## Cache Sync Flow

When user clicks **Fetch posts**:

1. Streamlit calls `fetch_posts_cached(actor, username, password, start, end)`
2. App logs into Bluesky (`atproto`) and opens SQLite
3. Sync behavior:
   - If actor has prior sync state:
     - ingest only posts newer than last synced timestamp
   - If actor has no sync state:
     - initial seed down to `start`
   - If cached history does not reach `start`:
     - backfill older pages until reaching `start`
4. Upsert each arXiv post into:
   - `paper_score_log` (by post URI)
   - `paper_scores` (by canonical arXiv key)
5. Query window from `paper_score_log`, then dedupe by `arxiv_key` keeping highest engagement in-window
6. Return ranked results to UI

## Streamlit UX

UI output remains intentionally simple:

- Summary cards:
  - most liked
  - most commented
  - most engaged
- Table columns:
  - `timestamp | title | authors | link | bsky_link | engagement`

## Running Locally

From `arxiv_ranker/`:

```bash
uv run streamlit run bsky_paperbot/streamlit_app.py --server.baseUrlPath /arxiv_methods_charts
```

Or with helper script:

```bash
./run_bsky_ranker.sh
```

CLI mode:

```bash
uv run python bsky_paperbot/rank_papers.py --start 2026-02-01 --end 2026-03-01
```

## Deployment Notes (This VPS)

- systemd unit: `arxiv_ranker.service`
- service reads credentials from:
  - `EnvironmentFile=/etc/default/arxiv_ranker`
- nginx proxies:
  - `/arxiv_methods_charts/` -> `127.0.0.1:8754/arxiv_methods_charts/`

## Credentials

Required env vars:

- `BSKYUSR`
- `BSKYPWD`

Recommended location on server:

- `/etc/default/arxiv_ranker` (not in git)

