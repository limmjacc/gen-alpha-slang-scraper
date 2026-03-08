from __future__ import annotations

from datetime import datetime, timezone

from gen_alpha_slang_scraper.collectors.base import BaseCollector
from gen_alpha_slang_scraper.models import PostRecord
from gen_alpha_slang_scraper.utils import json_request, normalize_whitespace, strip_html


class MastodonTagTimelineCollector(BaseCollector):
    name = "mastodon_tag_timeline"
    platform = "mastodon"

    def collect(self) -> list[PostRecord]:
        instance_url = self.config["instance_url"].rstrip("/")
        limit_per_tag = int(self.config.get("limit_per_tag", 8))
        tags = list(self.config.get("tags", []))
        posts: list[PostRecord] = []
        for tag in tags:
            payload = json_request(f"{instance_url}/api/v1/timelines/tag/{tag}", params={"limit": limit_per_tag})
            for status in payload:
                text = normalize_whitespace(strip_html(status.get("content", "")))
                if not text:
                    continue
                account = status.get("account") or {}
                posts.append(
                    PostRecord(
                        source=self.name,
                        platform=self.platform,
                        external_id=str(status.get("id", "")),
                        author=account.get("acct", "unknown"),
                        text=text,
                        created_at=status.get("created_at") or "",
                        url=status.get("url") or "",
                        metrics={
                            "replies_count": status.get("replies_count", 0),
                            "reblogs_count": status.get("reblogs_count", 0),
                            "favourites_count": status.get("favourites_count", 0),
                            "tracked_tag": tag,
                        },
                        raw=status,
                    )
                )
        return posts


class MastodonTrendsCollector(BaseCollector):
    name = "mastodon_trends"
    platform = "mastodon"

    def collect(self) -> list[PostRecord]:
        instance_url = self.config["instance_url"].rstrip("/")
        limit = int(self.config.get("limit", 20))
        payload = json_request(f"{instance_url}/api/v1/trends/tags")
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        posts: list[PostRecord] = []
        for item in payload[:limit]:
            history = item.get("history") or []
            latest = history[0] if history else {}
            uses = int(latest.get("uses", 0)) if str(latest.get("uses", "")).isdigit() else 0
            posts.append(
                PostRecord(
                    source=self.name,
                    platform=self.platform,
                    external_id=f"trend:{item.get('name', '')}",
                    author="mastodon-trends",
                    text=f"#{item.get('name', '')}",
                    created_at=now,
                    url=item.get("url") or "",
                    metrics={"uses_today": uses, "accounts_today": latest.get("accounts", 0)},
                    raw=item,
                )
            )
        return posts

