from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PostRecord:
    source: str
    platform: str
    external_id: str
    author: str
    text: str
    created_at: str
    url: str
    metrics: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class CollectorOutcome:
    name: str
    platform: str
    status: str
    post_count: int
    detail: str = ""


@dataclass
class TermScore:
    term: str
    normalized_term: str
    is_watchlist: bool
    is_stopword: bool
    is_slang_candidate: bool
    mention_count: int
    weighted_mentions: float
    hashtag_count: int
    post_count: int
    unique_authors: int
    source_count: int
    co_occurrence_hits: int
    novelty_score: float
    buzz_score: float
    discovery_score: float
    total_score: float
    platforms: list[str]
    contexts: list[str]


@dataclass
class SignalPost:
    source: str
    platform: str
    author: str
    created_at: str
    url: str
    text: str
    matched_terms: list[str]
    score: float
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    all_terms: list[TermScore]
    most_used_terms: list[TermScore]
    emerging_terms: list[TermScore]
    watchlist_terms: list[TermScore]
    signal_posts: list[SignalPost]
    overview: dict[str, int]
