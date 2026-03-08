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
    mention_count: int
    post_count: int
    unique_authors: int
    source_count: int
    novelty_score: float
    buzz_score: float
    discovery_score: float
    total_score: float
    platforms: list[str]
    contexts: list[str]

