from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from gen_alpha_slang_scraper.models import PostRecord


class CollectorSkip(RuntimeError):
    pass


class BaseCollector(ABC):
    name: str
    platform: str

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    @abstractmethod
    def collect(self) -> list[PostRecord]:
        raise NotImplementedError

