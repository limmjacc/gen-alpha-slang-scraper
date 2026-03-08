from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, timezone
from html import escape, unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


USER_AGENT = "gen-alpha-slang-scraper/0.1"
TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9']{1,24}")
HASHTAG_RE = re.compile(r"(?<!\w)#([a-zA-Z0-9_]{2,30})")
URL_RE = re.compile(r"https?://\S+")
MENTION_RE = re.compile(r"(?<!\w)@([a-zA-Z0-9._-]{2,})")
WHITESPACE_RE = re.compile(r"\s+")


class TextStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def get_text(self) -> str:
        return "".join(self.parts)


def ensure_dir(path: str | Path) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_text_resource(path: str) -> list[str]:
    package_root = Path(__file__).resolve().parent
    resource = package_root / path
    return [line.strip() for line in resource.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: Any) -> None:
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def strip_html(value: str) -> str:
    if not value:
        return ""
    parser = TextStripper()
    parser.feed(value)
    return normalize_whitespace(unescape(parser.get_text()))


def html_escape(value: str) -> str:
    return escape(value, quote=True)


def normalize_whitespace(value: str) -> str:
    return WHITESPACE_RE.sub(" ", value).strip()


def normalize_text(value: str) -> str:
    value = strip_html(value)
    value = URL_RE.sub(" ", value)
    value = MENTION_RE.sub(" ", value)
    return normalize_whitespace(value.lower())


def extract_hashtags(value: str) -> list[str]:
    return [match.group(1).lower() for match in HASHTAG_RE.finditer(value or "")]


def token_spans(value: str) -> list[tuple[str, int, int]]:
    return [(match.group(0).lower(), match.start(), match.end()) for match in TOKEN_RE.finditer(value or "")]


def tokenize(value: str) -> list[str]:
    return [token for token, _, _ in token_spans(value)]


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def recency_weight(value: str | None, window_hours: int) -> float:
    timestamp = parse_datetime(value)
    if not timestamp:
        return 0.2
    now = datetime.now(timezone.utc)
    age_hours = max((now - timestamp.astimezone(timezone.utc)).total_seconds() / 3600.0, 0.0)
    return math.exp(-age_hours / max(window_hours, 1))


def safe_log1p(value: float | int | None) -> float:
    if not value:
        return 0.0
    return math.log1p(max(float(value), 0.0))


def json_request(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: int = 20,
) -> Any:
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    full_url = url
    if params:
        query = urlencode({key: value for key, value in params.items() if value is not None}, doseq=True)
        full_url = f"{url}?{query}"
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = Request(full_url, headers=request_headers, method=method, data=data)
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8", "ignore"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:400]
        raise RuntimeError(f"HTTP {exc.code} for {full_url}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error for {full_url}: {exc}") from exc


def text_request(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    timeout: int = 20,
) -> str:
    request_headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
    if headers:
        request_headers.update(headers)
    full_url = url
    if params:
        query = urlencode({key: value for key, value in params.items() if value is not None}, doseq=True)
        full_url = f"{url}?{query}"
    request = Request(full_url, headers=request_headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", "ignore")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:400]
        raise RuntimeError(f"HTTP {exc.code} for {full_url}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error for {full_url}: {exc}") from exc


def getenv_required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
