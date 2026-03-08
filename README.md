# gen-alpha-slang-scraper

Track emerging slang, meme vocabulary, and "gen alpha speak" from live public social feeds, keep an inventory of every extracted term, and render a static dashboard that separates `most used now` from `top emerging`.

## Current state

As of March 8, 2026, this repo runs end to end without credentials in this environment using a mix of public APIs and public web scraping:

- Bluesky public Jetstream sample
- Bluesky public author feeds
- Mastodon public trend tags
- Mastodon public tag timelines
- YouTube public search pages
- Tumblr public tag pages
- Lemmy public post API
- 4chan board catalogs

It also includes optional official collectors for:

- `X` recent search
- `Facebook` Page feed
- `Instagram` hashtag media

And gated placeholders for:

- `TikTok` Research API
- `Snapchat` Public Profile API

## API access findings

The major social platforms do gate access, but not always in the same way:

- `X`: mainly a paid developer platform problem once you want serious coverage.
- `Facebook` / `Instagram`: more about app review, scoped permissions, and limited official surfaces than a simple paywall.
- `TikTok`: official broad research access is approval-gated rather than open public API access.
- `Snapchat`: public-profile access is allowlist-only.

That is why the default run leans on public, runnable sources instead of pretending the big closed networks are freely scrapable at production quality.

## What this project does

1. Collects live posts from configured sources.
2. Stores raw records in SQLite.
3. Tracks every extracted normalized term from those posts.
4. Separates the data into:
   - `most used now`
   - `top emerging`
   - `all tracked terms`
   - `signal posts`
5. Exports CSVs and a static HTML dashboard.

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

Open the generated dashboard:

- [`artifacts/latest/report.html`](/Users/liamjack/Library/Mobile%20Documents/com~apple~CloudDocs/Projects/Code%20Projects/gen-alpha-slang-scraper/artifacts/latest/report.html)

## CLI

Available commands:

```bash
./.venv/bin/python -m gen_alpha_slang_scraper list-sources
./.venv/bin/python -m gen_alpha_slang_scraper doctor --config configs/default.json
./.venv/bin/python -m gen_alpha_slang_scraper run --config configs/default.json
```

## Outputs

`artifacts/latest/` contains:

- `report.html`: the dashboard
- `summary.md`: short run summary
- `run_metadata.json`: machine-readable run metadata
- `posts.csv`: collected posts
- `signal_posts.csv`: posts with matched slang terms surfaced explicitly
- `all_terms.csv`: every extracted normalized term tracked from collected posts
- `most_used_terms.csv`: top slang terms by current usage score
- `emerging_terms.csv`: top slang terms by emergence score
- `top_terms.csv`: compatibility alias for `most_used_terms.csv`
- `slang.db`: SQLite database with raw posts and tracked term rows
- `top_terms.png`, `emerging_terms.png`, `platform_mix.png`, `usage_vs_emergence.png`: charts used in the report

## How the tracker now works

The tracker is no longer just a narrow leaderboard.

- Every extracted normalized term is tracked in the inventory.
- The dashboard has separate views for `most used` and `emerging`.
- `signal posts` show the exact matched terms for each post, so co-occurring slang does not disappear inside another term's evidence row.
- `all tracked terms` is searchable in the report and complete in `all_terms.csv`.

This means if a post contains both `sigma` and `bussin`, the report surfaces both terms and also shows them together inside the post-level evidence card.

## Scoring model

The scores are directional monitoring signals, not language-science ground truth.

- `usage score`: weighted post count, weighted mentions, engagement, and platform spread
- `emergence score`: novelty, recency, co-occurrence with known slang, and hashtag behavior

Important bias notes:

- Query-driven collectors like `youtube_search`, `tumblr_tagged`, and `mastodon_tag_timeline` are downweighted so they do not dominate as if they were unbiased global samples.
- Public web scraping sources are useful for monitoring, but they are not the same thing as full official-platform firehose access.

## Config files

- [`configs/default.json`](/Users/liamjack/Library/Mobile%20Documents/com~apple~CloudDocs/Projects/Code%20Projects/gen-alpha-slang-scraper/configs/default.json): runnable default configuration
- [`configs/official-example.json`](/Users/liamjack/Library/Mobile%20Documents/com~apple~CloudDocs/Projects/Code%20Projects/gen-alpha-slang-scraper/configs/official-example.json): example overrides for official X and Meta sources

## Official-source env vars

When you want to turn on official collectors, these are the current env vars:

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

- The big closed social platforms still require official credentials, review, approval, or allowlisting for serious coverage.
- Public web scraping can break when page structures change.
- TikTok and Snapchat are still the hardest platforms to cover cleanly without official access.
- Slang classification is heuristic. The full inventory is intentionally broader than the curated leaderboard.

## Next useful extensions

- Cross-run history so `emerging` becomes true burst-over-baseline detection.
- Human curation labels for slang candidates.
- OCR and ASR once a legal video-source path is available.
- A small local API or web app on top of the SQLite output.
