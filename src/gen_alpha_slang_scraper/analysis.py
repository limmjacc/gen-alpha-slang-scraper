from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from gen_alpha_slang_scraper.models import PostRecord, TermScore
from gen_alpha_slang_scraper.utils import (
    extract_hashtags,
    load_text_resource,
    normalize_text,
    recency_weight,
    safe_log1p,
    token_spans,
)

CONTAINS_FRAGMENTS = {
    "brainrot",
    "bussin",
    "crashout",
    "delulu",
    "fanum",
    "glaze",
    "goated",
    "gyatt",
    "looksmaxx",
    "mew",
    "mog",
    "rizz",
    "skibidi",
    "zesty",
}
SLANG_SUFFIXES = ("core", "coded", "maxxing", "posting", "pilled", "brainrot", "mogged")


@dataclass
class _TermAccumulator:
    term: str
    is_watchlist: bool = False
    posts: set[str] = field(default_factory=set)
    post_weights: dict[str, float] = field(default_factory=dict)
    authors: set[str] = field(default_factory=set)
    sources: set[str] = field(default_factory=set)
    platforms: set[str] = field(default_factory=set)
    mention_count: int = 0
    weighted_mentions: float = 0.0
    novelty_score_total: float = 0.0
    recency_total: float = 0.0
    engagement_total: float = 0.0
    contexts: list[str] = field(default_factory=list)


def load_watchlists() -> tuple[set[str], set[str], set[str]]:
    watch_terms = set(load_text_resource("data/watchlist_terms.txt"))
    watch_phrases = set(load_text_resource("data/watchlist_phrases.txt"))
    stopwords = set(load_text_resource("data/stopwords.txt"))
    return watch_terms, watch_phrases, stopwords


def looks_slangy(token: str, watch_terms: set[str], stopwords: set[str]) -> bool:
    if token in watch_terms:
        return True
    if token in stopwords:
        return False
    if len(token) < 3 or len(token) > 20:
        return False
    if any(char.isdigit() for char in token) and len(token) > 8:
        return False
    if token.endswith(SLANG_SUFFIXES):
        return True
    if any(fragment in token for fragment in CONTAINS_FRAGMENTS):
        return True
    if token.startswith(("unc", "anti")) and len(token) <= 10:
        return True
    return False


def novelty_score(token: str, watch_terms: set[str], stopwords: set[str]) -> float:
    score = 0.0
    if token in watch_terms:
        score += 0.7
    if token not in stopwords:
        score += 0.5
    if token.endswith(SLANG_SUFFIXES):
        score += 0.8
    if any(fragment in token for fragment in CONTAINS_FRAGMENTS):
        score += 0.9
    if len(set(token)) <= max(len(token) // 2, 2):
        score += 0.25
    return score


def _add_term(
    accumulator: dict[str, _TermAccumulator],
    term: str,
    post: PostRecord,
    *,
    is_watchlist: bool,
    context: str,
    novelty: float,
    weight: float,
    window_hours: int,
) -> None:
    record = accumulator.setdefault(term, _TermAccumulator(term=term))
    record.is_watchlist = record.is_watchlist or is_watchlist
    record.posts.add(post.external_id)
    record.post_weights[post.external_id] = max(record.post_weights.get(post.external_id, 0.0), weight)
    record.authors.add(post.author)
    record.sources.add(post.source)
    record.platforms.add(post.platform)
    record.mention_count += 1
    record.weighted_mentions += weight
    record.novelty_score_total += novelty
    record.recency_total += recency_weight(post.created_at, window_hours) * weight
    metrics = post.metrics or {}
    engagement = sum(
        safe_log1p(metrics.get(key))
        for key in (
            "reply_count",
            "repost_count",
            "like_count",
            "quote_count",
            "replies_count",
            "reblogs_count",
            "favourites_count",
            "comments_count",
            "reactions",
            "comments",
            "shares",
            "uses_today",
        )
    )
    record.engagement_total += engagement * weight
    if context and len(record.contexts) < 5 and context not in record.contexts:
        record.contexts.append(context)


def source_weight(post: PostRecord, term: str) -> float:
    metrics = post.metrics or {}
    tracked_tag = str(metrics.get("tracked_tag", "")).lower()
    if post.source == "mastodon_trends":
        return 0.45
    if post.source == "mastodon_tag_timeline":
        return 0.35 if tracked_tag == term else 0.85
    if post.source == "instagram_hashtags":
        return 0.4 if tracked_tag == term else 0.85
    if post.source == "bluesky_author_feed":
        return 0.9
    return 1.0


def analyze_posts(posts: list[PostRecord], *, window_hours: int) -> tuple[list[TermScore], dict[str, int]]:
    watch_terms, watch_phrases, stopwords = load_watchlists()
    accumulator: dict[str, _TermAccumulator] = {}
    candidate_windows: dict[str, Counter[str]] = defaultdict(Counter)

    for post in posts:
        normalized = normalize_text(post.text)
        tokens_with_spans = token_spans(normalized)
        tokens = [token for token, _, _ in tokens_with_spans]
        found_terms: set[str] = set()

        padded_text = f" {normalized} "
        for phrase in watch_phrases:
            if f" {phrase} " in padded_text:
                found_terms.add(phrase)
                _add_term(
                    accumulator,
                    phrase,
                    post,
                    is_watchlist=True,
                    context=post.text[:180],
                    novelty=novelty_score(phrase, watch_terms, stopwords),
                    weight=source_weight(post, phrase),
                    window_hours=window_hours,
                )

        for index, (token, _, _) in enumerate(tokens_with_spans):
            if token in watch_terms:
                found_terms.add(token)
                start = max(index - 4, 0)
                end = min(index + 5, len(tokens))
                context = " ".join(tokens[start:end])
                _add_term(
                    accumulator,
                    token,
                    post,
                    is_watchlist=True,
                    context=context,
                    novelty=novelty_score(token, watch_terms, stopwords),
                    weight=source_weight(post, token),
                    window_hours=window_hours,
                )
                for neighbor in tokens[start:end]:
                    if neighbor == token:
                        continue
                    if looks_slangy(neighbor, watch_terms, stopwords):
                        candidate_windows[neighbor][token] += 1

        for hashtag in extract_hashtags(post.text):
            if looks_slangy(hashtag, watch_terms, stopwords):
                _add_term(
                    accumulator,
                    hashtag,
                    post,
                    is_watchlist=hashtag in watch_terms,
                    context=post.text[:180],
                    novelty=novelty_score(hashtag, watch_terms, stopwords) + 0.25,
                    weight=source_weight(post, hashtag),
                    window_hours=window_hours,
                )

    for candidate, neighbors in candidate_windows.items():
        if sum(neighbors.values()) < 2:
            continue
        related_posts = []
        for post in posts:
            normalized_post = normalize_text(post.text)
            post_tokens = {token for token, _, _ in token_spans(normalized_post)}
            if candidate in post_tokens or candidate in extract_hashtags(post.text):
                related_posts.append(post)
        for post in related_posts[:8]:
            _add_term(
                accumulator,
                candidate,
                post,
                is_watchlist=candidate in watch_terms,
                context=post.text[:180],
                novelty=novelty_score(candidate, watch_terms, stopwords) + 0.35,
                weight=source_weight(post, candidate),
                window_hours=window_hours,
            )

    results: list[TermScore] = []
    for term, data in accumulator.items():
        post_count = len(data.posts)
        if post_count < 2 and not data.is_watchlist:
            continue
        novelty = data.novelty_score_total / max(data.mention_count, 1)
        weighted_post_count = sum(data.post_weights.values())
        weighted_mention_count = data.weighted_mentions
        if not data.is_watchlist and novelty < 1.0:
            continue
        buzz = (
            1.8 * weighted_post_count
            + 0.9 * weighted_mention_count
            + 1.25 * len(data.sources)
            + 0.75 * len(data.authors)
            + 3.0 * (data.recency_total / max(weighted_mention_count, 1))
            + 0.45 * data.engagement_total
            + (0.75 if data.is_watchlist else 0.0)
        )
        discovery = (
            1.5 * novelty
            + 0.8 * len(data.platforms)
            + 0.6 * len(data.contexts)
            + (0.35 if not data.is_watchlist else 0.0)
        )
        results.append(
            TermScore(
                term=term,
                normalized_term=term,
                is_watchlist=data.is_watchlist,
                mention_count=data.mention_count,
                post_count=post_count,
                unique_authors=len(data.authors),
                source_count=len(data.sources),
                novelty_score=round(novelty, 3),
                buzz_score=round(buzz, 3),
                discovery_score=round(discovery, 3),
                total_score=round(buzz + discovery, 3),
                platforms=sorted(data.platforms),
                contexts=data.contexts,
            )
        )

    overview = {
        "post_count": len(posts),
        "watchlist_terms_found": sum(1 for result in results if result.is_watchlist),
        "discovered_terms_found": sum(1 for result in results if not result.is_watchlist),
    }
    results.sort(key=lambda item: item.total_score, reverse=True)
    return results, overview
