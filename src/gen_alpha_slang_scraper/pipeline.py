from __future__ import annotations

from collections import Counter
from typing import Any

from gen_alpha_slang_scraper.analysis import analyze_posts
from gen_alpha_slang_scraper.collectors import build_collectors
from gen_alpha_slang_scraper.collectors.base import CollectorSkip
from gen_alpha_slang_scraper.models import CollectorOutcome, PostRecord
from gen_alpha_slang_scraper.reports.dashboard import render_dashboard
from gen_alpha_slang_scraper.storage import Storage
from gen_alpha_slang_scraper.utils import utc_now_iso, write_json


def run_pipeline(config: dict[str, Any], *, config_path: str | None = None) -> dict[str, Any]:
    started_at = utc_now_iso()
    storage = Storage(config["database_path"])
    run_id = storage.start_run(started_at, config_path)

    posts: list[PostRecord] = []
    outcomes: list[CollectorOutcome] = []
    for collector in build_collectors(config):
        try:
            collector_posts = collector.collect()
            posts.extend(collector_posts)
            outcomes.append(
                CollectorOutcome(
                    name=collector.name,
                    platform=collector.platform,
                    status="ok",
                    post_count=len(collector_posts),
                    detail="",
                )
            )
        except CollectorSkip as exc:
            outcomes.append(
                CollectorOutcome(
                    name=collector.name,
                    platform=collector.platform,
                    status="skipped",
                    post_count=0,
                    detail=str(exc),
                )
            )
        except Exception as exc:  # noqa: BLE001
            outcomes.append(
                CollectorOutcome(
                    name=collector.name,
                    platform=collector.platform,
                    status="error",
                    post_count=0,
                    detail=str(exc),
                )
            )

    deduped_posts: dict[tuple[str, str], PostRecord] = {}
    for post in posts:
        deduped_posts[(post.platform, post.external_id)] = post
    posts = list(deduped_posts.values())

    storage.insert_posts(run_id, posts)
    analysis = analyze_posts(posts, window_hours=int(config.get("window_hours", 72)))
    storage.insert_term_scores(run_id, analysis.all_terms)
    artifacts = render_dashboard(
        posts=posts,
        analysis=analysis,
        outcomes=outcomes,
        output_dir=config["output_dir"],
    )

    platform_counts = Counter(post.platform for post in posts)
    payload = {
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": utc_now_iso(),
        "posts_collected": len(posts),
        "platform_counts": dict(platform_counts),
        "most_used_terms": [term.term for term in analysis.most_used_terms[:10]],
        "emerging_terms": [term.term for term in analysis.emerging_terms[:10]],
        "overview": analysis.overview,
        "collector_outcomes": [outcome.__dict__ for outcome in outcomes],
        "artifacts": artifacts,
    }
    write_json(f"{config['output_dir']}/run_metadata.json", payload)
    storage.finish_run(run_id, payload["finished_at"], notes="; ".join(f"{o.name}:{o.status}" for o in outcomes))
    return payload
