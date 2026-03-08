# gen-alpha-slang-scraper

Track emerging slang, meme vocabulary, and "gen alpha speak" from live public social feeds, score the terms, and render a static dashboard for quick review.

As shipped on March 8, 2026, the project is fully runnable end to end with public sources that do not require credentials in this environment:

- Bluesky public Jetstream sample
- Bluesky public author feeds
- Mastodon public trend tags
- Mastodon public tag timelines

It also includes optional official collectors for:

- `X` recent search
- `Facebook` Page feed
- `Instagram` hashtag media

And gated placeholders for:

- `TikTok` Research API
- `Snapchat` Public Profile API

Those last two remain disabled by default because access is approval-gated or allowlist-only.

## What this project does

1. Collects live posts from configured sources.
2. Stores raw records in SQLite.
3. Extracts tracked slang terms and nearby candidate vocabulary.
4. Scores terms using weighted buzz + novelty signals.
5. Exports CSVs and a static HTML report with charts.

## Quickstart

Create the environment and install the package:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip setuptools wheel
./.venv/bin/pip install -e .
```

Inspect enabled sources:

```bash
./.venv/bin/python -m gen_alpha_slang_scraper doctor --config configs/default.json
```

Run the full pipeline:

```bash
./.venv/bin/python -m gen_alpha_slang_scraper run --config configs/default.json
```

Open the generated report:

- [`artifacts/latest/report.html`](/Users/liamjack/Library/Mobile%20Documents/com~apple~CloudDocs/Projects/Code%20Projects/gen-alpha-slang-scraper/artifacts/latest/report.html)
- [`artifacts/latest/top_terms.csv`](/Users/liamjack/Library/Mobile%20Documents/com~apple~CloudDocs/Projects/Code%20Projects/gen-alpha-slang-scraper/artifacts/latest/top_terms.csv)
- [`artifacts/latest/posts.csv`](/Users/liamjack/Library/Mobile%20Documents/com~apple~CloudDocs/Projects/Code%20Projects/gen-alpha-slang-scraper/artifacts/latest/posts.csv)
- [`artifacts/latest/slang.db`](/Users/liamjack/Library/Mobile%20Documents/com~apple~CloudDocs/Projects/Code%20Projects/gen-alpha-slang-scraper/artifacts/latest/slang.db)

Each run overwrites the files in `artifacts/latest/` and appends a new row set to the SQLite database.

## CLI

Available commands:

```bash
./.venv/bin/python -m gen_alpha_slang_scraper list-sources
./.venv/bin/python -m gen_alpha_slang_scraper doctor --config configs/default.json
./.venv/bin/python -m gen_alpha_slang_scraper run --config configs/default.json
```

## Output structure

`artifacts/latest/` contains:

- `report.html`: static dashboard
- `top_terms.csv`: ranked slang terms and evidence
- `posts.csv`: collected posts
- `summary.md`: short run summary
- `run_metadata.json`: machine-readable run metadata
- `slang.db`: SQLite database with raw posts and scored terms
- `top_terms.png`, `platform_mix.png`, `buzz_vs_novelty.png`: charts used in the dashboard

## How scoring works

The score is directional, not absolute.

- `buzz score`: weighted recent mentions, post count, source coverage, and engagement
- `novelty score`: whether a term matches slang patterns or the built-in watchlist
- `discovery score`: novelty plus contextual variety

Important bias to keep in mind:

- `mastodon_tag_timeline` is a targeted monitoring source. Its hits are downweighted so tracked hashtags do not dominate the report as if they were unbiased platform-wide counts.
- The default run is a monitoring dashboard, not a complete census of every major social platform.

## Config files

- [`configs/default.json`](/Users/liamjack/Library/Mobile%20Documents/com~apple~CloudDocs/Projects/Code%20Projects/gen-alpha-slang-scraper/configs/default.json): working no-credential configuration
- [`configs/official-example.json`](/Users/liamjack/Library/Mobile%20Documents/com~apple~CloudDocs/Projects/Code%20Projects/gen-alpha-slang-scraper/configs/official-example.json): example overrides for X and Meta

## Official sources

The default config leaves official collectors off because this environment does not contain platform credentials.

Supported env vars:

- `X_BEARER_TOKEN`
- `META_ACCESS_TOKEN`
- `META_IG_USER_ID`

More detail is in [`docs/platform-notes.md`](/Users/liamjack/Library/Mobile%20Documents/com~apple~CloudDocs/Projects/Code%20Projects/gen-alpha-slang-scraper/docs/platform-notes.md).

## Repo layout

```text
configs/
docs/
artifacts/latest/
src/gen_alpha_slang_scraper/
  collectors/
  data/
  reports/
```

## Practical limitations

- Without approved access, TikTok and Snapchat cannot be monitored broadly through official APIs.
- Instagram public access is limited to Graph API surfaces like hashtag search and requires business/professional app setup.
- X support is straightforward once a bearer token is available, but rate limits and plan limits still matter.
- Slang detection is heuristic. It is good for monitoring, not final lexicography.

## Next useful extensions

- Persist cross-run history and add real burst-over-baseline scoring.
- Add OCR and ASR pipelines for short-form video once a legal source path exists.
- Add a small web UI or API server on top of the SQLite output.
- Add manual review / approval labels so the slang list can be curated over time.

