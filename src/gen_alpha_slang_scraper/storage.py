from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from gen_alpha_slang_scraper.models import PostRecord, TermScore


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  config_path TEXT,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  source TEXT NOT NULL,
  platform TEXT NOT NULL,
  external_id TEXT NOT NULL,
  author TEXT NOT NULL,
  text TEXT NOT NULL,
  created_at TEXT,
  url TEXT,
  metrics_json TEXT,
  raw_json TEXT
);

CREATE TABLE IF NOT EXISTS term_scores (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL,
  term TEXT NOT NULL,
  normalized_term TEXT NOT NULL,
  is_watchlist INTEGER NOT NULL,
  mention_count INTEGER NOT NULL,
  post_count INTEGER NOT NULL,
  unique_authors INTEGER NOT NULL,
  source_count INTEGER NOT NULL,
  novelty_score REAL NOT NULL,
  buzz_score REAL NOT NULL,
  discovery_score REAL NOT NULL,
  total_score REAL NOT NULL,
  platforms_json TEXT NOT NULL,
  contexts_json TEXT NOT NULL
);
"""


class Storage:
    def __init__(self, database_path: str) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.database_path)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def start_run(self, started_at: str, config_path: str | None) -> int:
        cursor = self.connection.execute(
            "INSERT INTO runs (started_at, config_path) VALUES (?, ?)",
            (started_at, config_path),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def finish_run(self, run_id: int, finished_at: str, notes: str) -> None:
        self.connection.execute(
            "UPDATE runs SET finished_at = ?, notes = ? WHERE id = ?",
            (finished_at, notes, run_id),
        )
        self.connection.commit()

    def insert_posts(self, run_id: int, posts: list[PostRecord]) -> None:
        self.connection.executemany(
            """
            INSERT INTO posts (
              run_id, source, platform, external_id, author, text, created_at, url, metrics_json, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    post.source,
                    post.platform,
                    post.external_id,
                    post.author,
                    post.text,
                    post.created_at,
                    post.url,
                    json.dumps(post.metrics, sort_keys=True),
                    json.dumps(post.raw, sort_keys=True),
                )
                for post in posts
            ],
        )
        self.connection.commit()

    def insert_term_scores(self, run_id: int, terms: list[TermScore]) -> None:
        self.connection.executemany(
            """
            INSERT INTO term_scores (
              run_id, term, normalized_term, is_watchlist, mention_count, post_count, unique_authors, source_count,
              novelty_score, buzz_score, discovery_score, total_score, platforms_json, contexts_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    run_id,
                    term.term,
                    term.normalized_term,
                    1 if term.is_watchlist else 0,
                    term.mention_count,
                    term.post_count,
                    term.unique_authors,
                    term.source_count,
                    term.novelty_score,
                    term.buzz_score,
                    term.discovery_score,
                    term.total_score,
                    json.dumps(term.platforms),
                    json.dumps(term.contexts),
                )
                for term in terms
            ],
        )
        self.connection.commit()

