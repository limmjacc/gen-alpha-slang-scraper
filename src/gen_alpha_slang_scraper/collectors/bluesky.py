from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import websockets

from gen_alpha_slang_scraper.collectors.base import BaseCollector
from gen_alpha_slang_scraper.models import PostRecord
from gen_alpha_slang_scraper.utils import json_request, normalize_whitespace


class BlueskyJetstreamCollector(BaseCollector):
    name = "bluesky_jetstream"
    platform = "bluesky"

    async def _collect_async(self) -> list[PostRecord]:
        endpoint = self.config["endpoint"]
        max_posts = int(self.config.get("max_posts", 300))
        duration_seconds = float(self.config.get("duration_seconds", 10))
        only_english = bool(self.config.get("only_english", True))

        posts: list[PostRecord] = []
        started = time.monotonic()

        async with websockets.connect(endpoint, max_size=2_000_000, ping_interval=20) as websocket:
            while len(posts) < max_posts and (time.monotonic() - started) < duration_seconds:
                remaining = max(duration_seconds - (time.monotonic() - started), 0.5)
                raw_message = await asyncio.wait_for(websocket.recv(), timeout=remaining)
                message = json.loads(raw_message)
                commit = message.get("commit") or {}
                if commit.get("operation") != "create" or commit.get("collection") != "app.bsky.feed.post":
                    continue
                record = commit.get("record") or {}
                text = normalize_whitespace(record.get("text", ""))
                if not text:
                    continue
                langs = record.get("langs") or []
                if only_english and langs and "en" not in langs:
                    continue
                did = message.get("did", "unknown")
                rkey = commit.get("rkey", "")
                posts.append(
                    PostRecord(
                        source=self.name,
                        platform=self.platform,
                        external_id=f"at://{did}/app.bsky.feed.post/{rkey}" if rkey else did,
                        author=did,
                        text=text,
                        created_at=record.get("createdAt") or "",
                        url=f"https://bsky.app/profile/{did}/post/{rkey}" if rkey else "",
                        metrics={"reply_count": 0, "repost_count": 0, "like_count": 0},
                        raw=message,
                    )
                )
        return posts

    def collect(self) -> list[PostRecord]:
        return asyncio.run(self._collect_async())


class BlueskyAuthorFeedCollector(BaseCollector):
    name = "bluesky_author_feed"
    platform = "bluesky"

    def collect(self) -> list[PostRecord]:
        handles = list(self.config.get("handles", []))
        limit_per_handle = int(self.config.get("limit_per_handle", 20))
        posts: list[PostRecord] = []
        for handle in handles:
            payload = json_request(
                "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed",
                params={"actor": handle, "limit": limit_per_handle},
            )
            for item in payload.get("feed", []):
                post = (item.get("post") or {})
                author = post.get("author") or {}
                record = post.get("record") or {}
                text = normalize_whitespace(record.get("text", ""))
                if not text:
                    continue
                posts.append(
                    PostRecord(
                        source=self.name,
                        platform=self.platform,
                        external_id=post.get("uri", ""),
                        author=author.get("handle", handle),
                        text=text,
                        created_at=record.get("createdAt") or "",
                        url=f"https://bsky.app/profile/{author.get('handle', handle)}/post/{post.get('uri', '').split('/')[-1]}",
                        metrics={
                            "reply_count": post.get("replyCount", 0),
                            "repost_count": post.get("repostCount", 0),
                            "like_count": post.get("likeCount", 0),
                            "quote_count": post.get("quoteCount", 0),
                        },
                        raw=item,
                    )
                )
        return posts
