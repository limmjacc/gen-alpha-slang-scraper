from __future__ import annotations

from gen_alpha_slang_scraper.collectors.base import BaseCollector, CollectorSkip
from gen_alpha_slang_scraper.models import PostRecord
from gen_alpha_slang_scraper.utils import getenv_required, json_request, normalize_whitespace


class XRecentSearchCollector(BaseCollector):
    name = "x_recent_search"
    platform = "x"

    def collect(self) -> list[PostRecord]:
        bearer_token = getenv_required("X_BEARER_TOKEN")
        base_url = self.config.get("base_url", "https://api.x.com/2").rstrip("/")
        limit = min(int(self.config.get("limit", 50)), 100)
        query = self.config["query"]
        payload = json_request(
            f"{base_url}/tweets/search/recent",
            headers={"Authorization": f"Bearer {bearer_token}"},
            params={
                "query": query,
                "max_results": limit,
                "tweet.fields": "created_at,lang,public_metrics",
                "expansions": "author_id",
                "user.fields": "username",
            },
        )
        users = {item["id"]: item for item in payload.get("includes", {}).get("users", [])}
        posts: list[PostRecord] = []
        for item in payload.get("data", []):
            metrics = item.get("public_metrics") or {}
            author = users.get(item.get("author_id", ""), {})
            posts.append(
                PostRecord(
                    source=self.name,
                    platform=self.platform,
                    external_id=item.get("id", ""),
                    author=author.get("username", item.get("author_id", "unknown")),
                    text=normalize_whitespace(item.get("text", "")),
                    created_at=item.get("created_at") or "",
                    url=f"https://x.com/{author.get('username', 'i')}/status/{item.get('id', '')}",
                    metrics=metrics,
                    raw=item,
                )
            )
        return posts


class FacebookPageFeedCollector(BaseCollector):
    name = "facebook_page_feed"
    platform = "facebook"

    def collect(self) -> list[PostRecord]:
        access_token = getenv_required("META_ACCESS_TOKEN")
        graph_version = self.config.get("graph_version", "v21.0")
        page_ids = list(self.config.get("page_ids", []))
        if not page_ids:
            raise CollectorSkip("No Facebook page IDs configured.")
        posts: list[PostRecord] = []
        for page_id in page_ids:
            payload = json_request(
                f"https://graph.facebook.com/{graph_version}/{page_id}/feed",
                params={
                    "access_token": access_token,
                    "limit": 25,
                    "fields": "id,message,created_time,permalink_url,from,shares,reactions.limit(0).summary(true),comments.limit(0).summary(true)",
                },
            )
            for item in payload.get("data", []):
                message = normalize_whitespace(item.get("message", ""))
                if not message:
                    continue
                reactions = (item.get("reactions") or {}).get("summary", {}).get("total_count", 0)
                comments = (item.get("comments") or {}).get("summary", {}).get("total_count", 0)
                shares = (item.get("shares") or {}).get("count", 0)
                author = (item.get("from") or {}).get("name", page_id)
                posts.append(
                    PostRecord(
                        source=self.name,
                        platform=self.platform,
                        external_id=item.get("id", ""),
                        author=author,
                        text=message,
                        created_at=item.get("created_time") or "",
                        url=item.get("permalink_url") or "",
                        metrics={"reactions": reactions, "comments": comments, "shares": shares},
                        raw=item,
                    )
                )
        return posts


class InstagramHashtagCollector(BaseCollector):
    name = "instagram_hashtags"
    platform = "instagram"

    def collect(self) -> list[PostRecord]:
        access_token = getenv_required("META_ACCESS_TOKEN")
        ig_user_id = getenv_required("META_IG_USER_ID")
        graph_version = self.config.get("graph_version", "v21.0")
        hashtags = list(self.config.get("hashtags", []))
        if not hashtags:
            raise CollectorSkip("No Instagram hashtags configured.")

        posts: list[PostRecord] = []
        for hashtag in hashtags:
            lookup = json_request(
                f"https://graph.facebook.com/{graph_version}/ig_hashtag_search",
                params={"user_id": ig_user_id, "q": hashtag, "access_token": access_token},
            )
            for hashtag_node in lookup.get("data", []):
                hashtag_id = hashtag_node.get("id")
                payload = json_request(
                    f"https://graph.facebook.com/{graph_version}/{hashtag_id}/recent_media",
                    params={
                        "user_id": ig_user_id,
                        "access_token": access_token,
                        "fields": "id,caption,comments_count,like_count,media_type,permalink,timestamp",
                    },
                )
                for item in payload.get("data", []):
                    caption = normalize_whitespace(item.get("caption", ""))
                    if not caption:
                        continue
                    posts.append(
                        PostRecord(
                            source=self.name,
                            platform=self.platform,
                            external_id=item.get("id", ""),
                            author=f"hashtag:{hashtag}",
                            text=caption,
                            created_at=item.get("timestamp") or "",
                            url=item.get("permalink") or "",
                            metrics={
                                "like_count": item.get("like_count", 0),
                                "comments_count": item.get("comments_count", 0),
                                "tracked_tag": hashtag,
                            },
                            raw=item,
                        )
                    )
        return posts


class TikTokResearchCollector(BaseCollector):
    name = "tiktok_research"
    platform = "tiktok"

    def collect(self) -> list[PostRecord]:
        raise CollectorSkip(
            "TikTok Research API access is approval-gated. Wire in an approved token and endpoint once access is granted."
        )


class SnapPublicProfilesCollector(BaseCollector):
    name = "snap_public_profiles"
    platform = "snapchat"

    def collect(self) -> list[PostRecord]:
        raise CollectorSkip(
            "Snap Public Profile API is allowlist-only. Enable this collector after your app is approved by Snap."
        )

