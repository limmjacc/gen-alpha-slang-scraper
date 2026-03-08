# Platform Notes

This project separates `working now` sources from `official but gated` sources.

## Working now

These run in the default config without secrets:

- `bluesky_jetstream`
- `bluesky_author_feed`
- `mastodon_trends`
- `mastodon_tag_timeline`
- `youtube_search`
- `tumblr_tagged`
- `lemmy_posts`
- `fourchan_catalog`

### What kind of access these use

- `bluesky_jetstream`: public network stream sample
- `bluesky_author_feed`: public AppView endpoint
- `mastodon_*`: public instance endpoints
- `youtube_search`: public search-result HTML scraping
- `tumblr_tagged`: public tag-page HTML scraping
- `lemmy_posts`: public JSON API
- `fourchan_catalog`: public board JSON

These sources exist so the project can produce real output immediately, even when the major closed networks are unavailable.

## X

Implemented collector:

- `x_recent_search`

Requirements:

- `X_BEARER_TOKEN`

Notes:

- This is the cleanest official path for X once credentials are available.
- Practical access still depends on the current X developer plan and rate limits.

## Facebook

Implemented collector:

- `facebook_page_feed`

Requirements:

- `META_ACCESS_TOKEN`

Notes:

- This is for Pages, not personal profiles.
- It is useful for public Page content, but not a general public web search surface.

## Instagram

Implemented collector:

- `instagram_hashtags`

Requirements:

- `META_ACCESS_TOKEN`
- `META_IG_USER_ID`

Notes:

- This uses the official Graph API hashtag flow.
- It depends on Meta app/account setup and the relevant permissions.

## TikTok

Included as a gated placeholder:

- `tiktok_research`

Notes:

- The official Research API is the correct path for broad public-content analysis.
- Access is approval-gated.
- I also tested public tag-page scraping during development. In this environment the public page loaded, but it did not expose a clean public item list suitable for dependable ingestion, so it is not enabled as a default source.

## Snapchat

Included as a gated placeholder:

- `snap_public_profiles`

Notes:

- The Public Profile API is allowlist-only.
- This is not something to treat as open public scrape territory.

## Why the default run matters

The default configuration is designed around practical delivery:

- collect real public posts now
- track every extracted term now
- surface `most used`, `emerging`, and `signal posts` now

Then, when X or Meta credentials are added, the same pipeline and report layer can absorb those new feeds without changing the core analysis model.
