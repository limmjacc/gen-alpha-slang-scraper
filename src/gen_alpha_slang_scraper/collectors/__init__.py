from __future__ import annotations

from typing import Any

from gen_alpha_slang_scraper.collectors.base import BaseCollector
from gen_alpha_slang_scraper.collectors.bluesky import BlueskyAuthorFeedCollector, BlueskyJetstreamCollector
from gen_alpha_slang_scraper.collectors.mastodon import MastodonTagTimelineCollector, MastodonTrendsCollector
from gen_alpha_slang_scraper.collectors.official import (
    FacebookPageFeedCollector,
    InstagramHashtagCollector,
    SnapPublicProfilesCollector,
    TikTokResearchCollector,
    XRecentSearchCollector,
)


COLLECTOR_TYPES = {
    "bluesky_jetstream": BlueskyJetstreamCollector,
    "bluesky_author_feed": BlueskyAuthorFeedCollector,
    "mastodon_tag_timeline": MastodonTagTimelineCollector,
    "mastodon_trends": MastodonTrendsCollector,
    "x_recent_search": XRecentSearchCollector,
    "facebook_page_feed": FacebookPageFeedCollector,
    "instagram_hashtags": InstagramHashtagCollector,
    "tiktok_research": TikTokResearchCollector,
    "snap_public_profiles": SnapPublicProfilesCollector,
}


def build_collectors(config: dict[str, Any]) -> list[BaseCollector]:
    collectors: list[BaseCollector] = []
    for name, collector_config in config.get("collectors", {}).items():
        if not collector_config.get("enabled", False):
            continue
        collector_cls = COLLECTOR_TYPES.get(name)
        if collector_cls:
            collectors.append(collector_cls(collector_config))
    return collectors

