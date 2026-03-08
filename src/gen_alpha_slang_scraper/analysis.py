from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from gen_alpha_slang_scraper.models import AnalysisResult, PostRecord, SignalPost, TermScore
from gen_alpha_slang_scraper.utils import (
    extract_hashtags,
    load_text_resource,
    normalize_text,
    recency_weight,
    safe_log1p,
    token_spans,
)

PREFIX_FRAGMENTS = {
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
MIN_TOKEN_LENGTH = 2


@dataclass
class _TermAccumulator:
    term: str
    is_watchlist: bool = False
    is_stopword: bool = False
    is_slang_candidate: bool = False
    posts: set[str] = field(default_factory=set)
    post_weights: dict[str, float] = field(default_factory=dict)
    authors: set[str] = field(default_factory=set)
    sources: set[str] = field(default_factory=set)
    platforms: set[str] = field(default_factory=set)
    mention_count: int = 0
    weighted_mentions: float = 0.0
    hashtag_count: int = 0
    co_occurrence_hits: int = 0
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
    if len(token) < 3 or len(token) > 24:
        return False
    if any(char.isdigit() for char in token) and len(token) > 8:
        return False
    if token.endswith(SLANG_SUFFIXES):
        return True
    if any(token.startswith(fragment) or token.endswith(fragment) for fragment in PREFIX_FRAGMENTS):
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
    if any(token.startswith(fragment) or token.endswith(fragment) for fragment in PREFIX_FRAGMENTS):
        score += 0.9
    if len(token) <= 6 and len(set(token)) <= max(len(token) // 2, 2):
        score += 0.25
    return score


def source_weight(post: PostRecord, term: str) -> float:
    metrics = post.metrics or {}
    tracked_tag = str(metrics.get("tracked_tag", "")).lower()
    tracked_query = str(metrics.get("tracked_query", "")).lower()
    tracked_board = str(metrics.get("tracked_board", "")).lower()
    if post.source == "mastodon_trends":
        return 0.45
    if post.source == "mastodon_tag_timeline":
        return 0.35 if tracked_tag == term else 0.85
    if post.source == "instagram_hashtags":
        return 0.4 if tracked_tag == term else 0.85
    if post.source == "tumblr_tagged":
        return 0.35 if tracked_tag == term else 0.8
    if post.source == "youtube_search":
        return 0.35 if tracked_query == term else 0.8
    if post.source == "fourchan_catalog":
        return 0.75 if tracked_board else 0.85
    if post.source == "bluesky_author_feed":
        return 0.9
    return 1.0


def _engagement_score(metrics: dict[str, object]) -> float:
    return sum(
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
            "score",
            "view_count",
            "note_count",
            "reply_count_raw",
            "like_count_raw",
        )
    )


def _add_term(
    accumulator: dict[str, _TermAccumulator],
    term: str,
    post: PostRecord,
    *,
    is_watchlist: bool,
    is_stopword: bool,
    is_slang_candidate: bool,
    context: str,
    novelty: float,
    weight: float,
    window_hours: int,
    from_hashtag: bool = False,
) -> None:
    record = accumulator.setdefault(term, _TermAccumulator(term=term))
    record.is_watchlist = record.is_watchlist or is_watchlist
    record.is_stopword = record.is_stopword and is_stopword if record.mention_count else is_stopword
    record.is_slang_candidate = record.is_slang_candidate or is_slang_candidate or is_watchlist
    record.posts.add(post.external_id)
    record.post_weights[post.external_id] = max(record.post_weights.get(post.external_id, 0.0), weight)
    record.authors.add(post.author)
    record.sources.add(post.source)
    record.platforms.add(post.platform)
    record.mention_count += 1
    record.weighted_mentions += weight
    record.hashtag_count += 1 if from_hashtag else 0
    record.novelty_score_total += novelty
    record.recency_total += recency_weight(post.created_at, window_hours) * weight
    record.engagement_total += _engagement_score(post.metrics or {}) * weight
    if context and len(record.contexts) < 6 and context not in record.contexts:
        record.contexts.append(context)


def _token_context(tokens: list[str], index: int, radius: int = 4) -> str:
    start = max(index - radius, 0)
    end = min(index + radius + 1, len(tokens))
    return " ".join(tokens[start:end])


def analyze_posts(posts: list[PostRecord], *, window_hours: int) -> AnalysisResult:
    watch_terms, watch_phrases, stopwords = load_watchlists()
    accumulator: dict[str, _TermAccumulator] = {}
    co_occurrence: dict[str, Counter[str]] = defaultdict(Counter)
    matched_terms_by_post: dict[str, set[str]] = defaultdict(set)

    for post in posts:
        normalized = normalize_text(post.text)
        tokens_with_spans = token_spans(normalized)
        tokens = [token for token, _, _ in tokens_with_spans if len(token) >= MIN_TOKEN_LENGTH]

        padded_text = f" {normalized} "
        for phrase in watch_phrases:
            if f" {phrase} " not in padded_text:
                continue
            weight = source_weight(post, phrase)
            _add_term(
                accumulator,
                phrase,
                post,
                is_watchlist=True,
                is_stopword=False,
                is_slang_candidate=True,
                context=post.text[:200],
                novelty=novelty_score(phrase, watch_terms, stopwords) + 0.45,
                weight=weight,
                window_hours=window_hours,
            )
            matched_terms_by_post[post.external_id].add(phrase)

        for index, token in enumerate(tokens):
            is_stopword = token in stopwords
            is_watchlist = token in watch_terms
            is_candidate = looks_slangy(token, watch_terms, stopwords)
            weight = source_weight(post, token)
            _add_term(
                accumulator,
                token,
                post,
                is_watchlist=is_watchlist,
                is_stopword=is_stopword,
                is_slang_candidate=is_candidate,
                context=_token_context(tokens, index),
                novelty=novelty_score(token, watch_terms, stopwords),
                weight=weight,
                window_hours=window_hours,
            )
            if is_watchlist or is_candidate:
                matched_terms_by_post[post.external_id].add(token)

            if is_watchlist or is_candidate:
                start = max(index - 4, 0)
                end = min(index + 5, len(tokens))
                for neighbor in tokens[start:end]:
                    if neighbor == token or neighbor in stopwords or len(neighbor) < 3:
                        continue
                    co_occurrence[neighbor][token] += 1

        for hashtag in extract_hashtags(post.text):
            is_stopword = hashtag in stopwords
            is_watchlist = hashtag in watch_terms
            is_candidate = looks_slangy(hashtag, watch_terms, stopwords) or not is_stopword
            weight = source_weight(post, hashtag) + 0.1
            _add_term(
                accumulator,
                hashtag,
                post,
                is_watchlist=is_watchlist,
                is_stopword=is_stopword,
                is_slang_candidate=is_candidate,
                context=post.text[:200],
                novelty=novelty_score(hashtag, watch_terms, stopwords) + 0.25,
                weight=weight,
                window_hours=window_hours,
                from_hashtag=True,
            )
            if not is_stopword:
                matched_terms_by_post[post.external_id].add(hashtag)

    for term, neighbors in co_occurrence.items():
        record = accumulator.get(term)
        if not record:
            continue
        record.co_occurrence_hits += sum(neighbors.values())
        if term not in stopwords and sum(neighbors.values()) >= 2:
            record.is_slang_candidate = True

    all_terms: list[TermScore] = []
    term_lookup: dict[str, TermScore] = {}
    for term, data in accumulator.items():
        weighted_post_count = sum(data.post_weights.values())
        novelty = data.novelty_score_total / max(data.mention_count, 1)
        recency_avg = data.recency_total / max(data.weighted_mentions, 1)
        final_candidate = data.is_watchlist or looks_slangy(term, watch_terms, stopwords) or (
            not data.is_stopword and novelty >= 0.9 and (data.co_occurrence_hits >= 4 or data.hashtag_count >= 2)
        )
        usage_score = (
            1.7 * weighted_post_count
            + 0.95 * data.weighted_mentions
            + 0.55 * data.engagement_total
            + 0.45 * len(data.platforms)
            + 0.25 * data.hashtag_count
        )
        emergence_score = (
            1.8 * novelty
            + 1.6 * recency_avg
            + 0.55 * len(data.sources)
            + 0.45 * len(data.platforms)
            + 0.4 * min(data.co_occurrence_hits, 12)
            + 0.35 * data.hashtag_count
            + (0.65 if not data.is_watchlist else 0.1)
            + (0.45 if final_candidate else -0.25)
            - (1.6 if data.is_stopword else 0.0)
        )
        score = TermScore(
            term=term,
            normalized_term=term,
            is_watchlist=data.is_watchlist,
            is_stopword=data.is_stopword,
            is_slang_candidate=final_candidate,
            mention_count=data.mention_count,
            weighted_mentions=round(data.weighted_mentions, 3),
            hashtag_count=data.hashtag_count,
            post_count=len(data.posts),
            unique_authors=len(data.authors),
            source_count=len(data.sources),
            co_occurrence_hits=data.co_occurrence_hits,
            novelty_score=round(novelty, 3),
            buzz_score=round(usage_score, 3),
            discovery_score=round(emergence_score, 3),
            total_score=round(usage_score + emergence_score, 3),
            platforms=sorted(data.platforms),
            contexts=data.contexts,
        )
        all_terms.append(score)
        term_lookup[term] = score

    all_terms.sort(key=lambda item: (item.total_score, item.weighted_mentions, item.mention_count), reverse=True)

    most_used_terms = sorted(
        [
            term
            for term in all_terms
            if not term.is_stopword and (term.is_watchlist or term.is_slang_candidate)
        ],
        key=lambda item: (item.buzz_score, item.weighted_mentions, item.post_count),
        reverse=True,
    )

    emerging_terms = sorted(
        [
            term
            for term in all_terms
            if not term.is_stopword
            and (term.is_watchlist or term.is_slang_candidate)
            and (term.post_count >= 2 or term.is_watchlist)
        ],
        key=lambda item: (item.discovery_score, not item.is_watchlist, item.hashtag_count, item.co_occurrence_hits),
        reverse=True,
    )

    watchlist_terms = sorted(
        [term for term in all_terms if term.is_watchlist],
        key=lambda item: (item.buzz_score, item.discovery_score),
        reverse=True,
    )

    signal_posts: list[SignalPost] = []
    for post in posts:
        matched_terms = sorted(
            [
                term
                for term in matched_terms_by_post.get(post.external_id, set())
                if term in term_lookup and (term_lookup[term].is_watchlist or term_lookup[term].is_slang_candidate)
            ],
            key=lambda term: term_lookup[term].total_score if term in term_lookup else 0.0,
            reverse=True,
        )
        if not matched_terms:
            continue
        signal_score = sum(term_lookup[term].total_score for term in matched_terms if term in term_lookup)
        signal_score += _engagement_score(post.metrics or {})
        signal_posts.append(
            SignalPost(
                source=post.source,
                platform=post.platform,
                author=post.author,
                created_at=post.created_at,
                url=post.url,
                text=post.text,
                matched_terms=matched_terms[:12],
                score=round(signal_score, 3),
                metrics=post.metrics,
            )
        )
    signal_posts.sort(key=lambda item: item.score, reverse=True)

    overview = {
        "post_count": len(posts),
        "all_terms_tracked": len(all_terms),
        "slang_terms_tracked": sum(1 for term in all_terms if term.is_slang_candidate and not term.is_stopword),
        "watchlist_terms_found": len(watchlist_terms),
        "emerging_terms_found": len([term for term in emerging_terms if not term.is_watchlist]),
        "signal_posts_count": len(signal_posts),
    }

    return AnalysisResult(
        all_terms=all_terms,
        most_used_terms=most_used_terms,
        emerging_terms=emerging_terms,
        watchlist_terms=watchlist_terms,
        signal_posts=signal_posts,
        overview=overview,
    )
