from __future__ import annotations

import json
import re
from urllib.parse import quote_plus

from gen_alpha_slang_scraper.collectors.base import BaseCollector
from gen_alpha_slang_scraper.models import PostRecord
from gen_alpha_slang_scraper.utils import json_request, normalize_whitespace, strip_html, text_request


YOUTUBE_DATA_RE = re.compile(r"var ytInitialData = (.*?);</script>", re.S)
TUMBLR_STATE_RE = re.compile(r'<script type="application/json" id="___INITIAL_STATE___">\s*(.*?)\s*</script>', re.S)


def _walk_key(node: object, target_key: str):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == target_key:
                yield value
            yield from _walk_key(value, target_key)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_key(item, target_key)


def _text_from_runs(value: dict) -> str:
    if not isinstance(value, dict):
        return ""
    if "simpleText" in value:
        return normalize_whitespace(str(value.get("simpleText", "")))
    if "content" in value:
        return normalize_whitespace(str(value.get("content", "")))
    runs = value.get("runs") or []
    return normalize_whitespace(" ".join(str(run.get("text", "")) for run in runs if isinstance(run, dict)))


def _parse_compact_number(value: str) -> int:
    if not value:
        return 0
    cleaned = value.lower().replace("views", "").replace("view", "").replace(",", "").strip()
    match = re.search(r"(\d+(?:\.\d+)?)\s*([kmb])?", cleaned)
    if not match:
        return 0
    number = float(match.group(1))
    suffix = match.group(2)
    if suffix == "k":
        number *= 1_000
    elif suffix == "m":
        number *= 1_000_000
    elif suffix == "b":
        number *= 1_000_000_000
    return int(number)


def _collect_text_bits(node: object) -> list[str]:
    bits: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in {"text", "summary", "title", "description"} and isinstance(value, str):
                bits.append(value)
            else:
                bits.extend(_collect_text_bits(value))
    elif isinstance(node, list):
        for item in node:
            bits.extend(_collect_text_bits(item))
    return bits


class YouTubeSearchCollector(BaseCollector):
    name = "youtube_search"
    platform = "youtube"

    def collect(self) -> list[PostRecord]:
        queries = list(self.config.get("queries", []))
        limit_per_query = int(self.config.get("limit_per_query", 8))
        posts: list[PostRecord] = []
        seen_ids: set[str] = set()

        for query in queries:
            html = text_request("https://www.youtube.com/results", params={"search_query": query})
            match = YOUTUBE_DATA_RE.search(html)
            if not match:
                continue
            payload = json.loads(match.group(1))

            count = 0
            for renderer in _walk_key(payload, "videoRenderer"):
                video_id = renderer.get("videoId", "")
                if not video_id or video_id in seen_ids:
                    continue
                title = _text_from_runs(renderer.get("title", {}))
                description = _text_from_runs(renderer.get("descriptionSnippet", {})) or _text_from_runs(
                    (renderer.get("detailedMetadataSnippets") or [{}])[0].get("snippetText", {})
                )
                author = _text_from_runs(renderer.get("ownerText", {})) or "youtube"
                view_count = _parse_compact_number(
                    _text_from_runs(renderer.get("viewCountText", {})) or _text_from_runs(renderer.get("shortViewCountText", {}))
                )
                text = normalize_whitespace(" ".join(part for part in [title, description] if part))
                if not text:
                    continue
                seen_ids.add(video_id)
                posts.append(
                    PostRecord(
                        source=self.name,
                        platform=self.platform,
                        external_id=video_id,
                        author=author,
                        text=text,
                        created_at="",
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        metrics={
                            "view_count": view_count,
                            "tracked_query": query.lower(),
                            "published_text": _text_from_runs(renderer.get("publishedTimeText", {})),
                        },
                        raw=renderer,
                    )
                )
                count += 1
                if count >= limit_per_query:
                    break

            if count < limit_per_query:
                for renderer in _walk_key(payload, "shortsLockupViewModel"):
                    video_id = (
                        ((renderer.get("onTap") or {}).get("innertubeCommand") or {}).get("reelWatchEndpoint") or {}
                    ).get("videoId", "")
                    if not video_id or video_id in seen_ids:
                        continue
                    title = _text_from_runs((renderer.get("overlayMetadata") or {}).get("primaryText", {}))
                    view_count = _parse_compact_number(_text_from_runs((renderer.get("overlayMetadata") or {}).get("secondaryText", {})))
                    if not title:
                        continue
                    seen_ids.add(video_id)
                    posts.append(
                        PostRecord(
                            source=self.name,
                            platform=self.platform,
                            external_id=video_id,
                            author="youtube-shorts",
                            text=title,
                            created_at="",
                            url=f"https://www.youtube.com/shorts/{video_id}",
                            metrics={"view_count": view_count, "tracked_query": query.lower()},
                            raw=renderer,
                        )
                    )
                    count += 1
                    if count >= limit_per_query:
                        break
        return posts


class TumblrTaggedCollector(BaseCollector):
    name = "tumblr_tagged"
    platform = "tumblr"

    def collect(self) -> list[PostRecord]:
        tags = list(self.config.get("tags", []))
        limit_per_tag = int(self.config.get("limit_per_tag", 8))
        posts: list[PostRecord] = []
        seen_ids: set[str] = set()
        for tag in tags:
            html = text_request(f"https://www.tumblr.com/tagged/{quote_plus(tag)}")
            match = TUMBLR_STATE_RE.search(html)
            if not match:
                continue
            payload = json.loads(match.group(1))
            items: list[dict] = []
            for query in payload.get("queries", {}).get("queries", []):
                data = query.get("state", {}).get("data")
                if isinstance(data, dict) and "pages" in data:
                    for page in data.get("pages", []):
                        items.extend(page.get("items", []))
            count = 0
            for item in items:
                post_id = str(item.get("idString") or item.get("id") or "")
                if not post_id or post_id in seen_ids:
                    continue
                text_bits = _collect_text_bits(item.get("content", []))
                text_bits.extend(_collect_text_bits(item.get("trail", [])))
                text = normalize_whitespace(" ".join([item.get("summary", "")] + text_bits))
                if not text:
                    continue
                seen_ids.add(post_id)
                posts.append(
                    PostRecord(
                        source=self.name,
                        platform=self.platform,
                        external_id=post_id,
                        author=item.get("blogName", "tumblr"),
                        text=text,
                        created_at=item.get("date", ""),
                        url=item.get("postUrl", ""),
                        metrics={
                            "note_count": item.get("noteCount", 0),
                            "like_count_raw": item.get("likeCount", 0),
                            "reply_count_raw": item.get("replyCount", 0),
                            "tracked_tag": tag.lower(),
                        },
                        raw=item,
                    )
                )
                count += 1
                if count >= limit_per_tag:
                    break
        return posts


class LemmyPostsCollector(BaseCollector):
    name = "lemmy_posts"
    platform = "lemmy"

    def collect(self) -> list[PostRecord]:
        instances = list(self.config.get("instances", ["https://lemmy.world"]))
        limit_per_instance = int(self.config.get("limit_per_instance", 20))
        sort = self.config.get("sort", "Hot")
        type_ = self.config.get("type_", "All")
        posts: list[PostRecord] = []
        seen_ids: set[str] = set()
        for instance in instances:
            try:
                payload = json_request(
                    f"{instance.rstrip('/')}/api/v3/post/list",
                    params={"type_": type_, "sort": sort, "limit": limit_per_instance},
                )
            except Exception:  # noqa: BLE001
                continue
            for item in payload.get("posts", []):
                post = item.get("post", {})
                counts = item.get("counts", {})
                creator = item.get("creator", {})
                post_id = str(post.get("id", ""))
                if not post_id or post_id in seen_ids:
                    continue
                text = normalize_whitespace(" ".join(part for part in [post.get("name", ""), post.get("body", "")] if part))
                if not text:
                    continue
                seen_ids.add(post_id)
                posts.append(
                    PostRecord(
                        source=self.name,
                        platform=self.platform,
                        external_id=post_id,
                        author=creator.get("name", "lemmy"),
                        text=text,
                        created_at=post.get("published", ""),
                        url=post.get("ap_id", post.get("url", "")),
                        metrics={
                            "score": counts.get("score", 0),
                            "comments_count": counts.get("comments", 0),
                        },
                        raw=item,
                    )
                )
        return posts


class FourChanCatalogCollector(BaseCollector):
    name = "fourchan_catalog"
    platform = "4chan"

    def collect(self) -> list[PostRecord]:
        boards = list(self.config.get("boards", ["v", "co", "tv"]))
        limit_per_board = int(self.config.get("limit_per_board", 15))
        posts: list[PostRecord] = []
        for board in boards:
            payload = json_request(f"https://a.4cdn.org/{board}/catalog.json")
            count = 0
            for page in payload:
                for thread in page.get("threads", []):
                    if count >= limit_per_board:
                        break
                    thread_id = str(thread.get("no", ""))
                    if not thread_id:
                        continue
                    text = normalize_whitespace(
                        " ".join(
                            part
                            for part in [thread.get("sub", ""), strip_html(thread.get("com", ""))]
                            if part
                        )
                    )
                    if not text:
                        continue
                    posts.append(
                        PostRecord(
                            source=self.name,
                            platform=self.platform,
                            external_id=f"{board}-{thread_id}",
                            author=thread.get("name", "Anonymous"),
                            text=text,
                            created_at=thread.get("now", ""),
                            url=f"https://boards.4chan.org/{board}/thread/{thread_id}",
                            metrics={
                                "replies_count": thread.get("replies", 0),
                                "images_count": thread.get("images", 0),
                                "tracked_board": board,
                            },
                            raw=thread,
                        )
                    )
                    count += 1
                if count >= limit_per_board:
                    break
        return posts
