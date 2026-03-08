# Platform Notes

This project intentionally separates `working now` collectors from `credentialed or approval-gated` collectors.

## Working now

These run with the default config and no secrets:

- `bluesky_jetstream`
- `bluesky_author_feed`
- `mastodon_trends`
- `mastodon_tag_timeline`

They exist to keep the project runnable and to generate real output immediately.

## X

Implemented collector:

- `x_recent_search`

Requirements:

- `X_BEARER_TOKEN`

Config fields:

- `query`
- `limit`
- `base_url`

Notes:

- This collector uses the recent-search endpoint and expects a valid bearer token.
- The default query is a compact slang watch query. Replace it with a better operator expression for your use case.

## Facebook

Implemented collector:

- `facebook_page_feed`

Requirements:

- `META_ACCESS_TOKEN`

Config fields:

- `page_ids`
- `graph_version`

Notes:

- This is for Pages, not personal profiles.
- It is a useful official route for public page posts, but it is not a broad public web search product.

## Instagram

Implemented collector:

- `instagram_hashtags`

Requirements:

- `META_ACCESS_TOKEN`
- `META_IG_USER_ID`

Config fields:

- `hashtags`
- `graph_version`

Notes:

- This uses the Graph API hashtag lookup flow and then reads recent media for those hashtag IDs.
- It depends on the app and account having the correct Meta setup.

## TikTok

Included as a gated placeholder:

- `tiktok_research`

Notes:

- The official Research API is the correct direction for broad public-content analysis, but access is restricted.
- The placeholder exists so the rest of the project structure is ready once access is approved.

## Snapchat

Included as a gated placeholder:

- `snap_public_profiles`

Notes:

- The Public Profile API is allowlist-only.
- Add the real API implementation after approval and token provisioning.

## Why the default run is still useful

The default configuration is designed to answer a practical need:

- collect live social text now
- score slang now
- generate a report now

Then, when X or Meta credentials are added, the same pipeline and reporting layer can absorb those new feeds with minimal code changes.

