from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from gen_alpha_slang_scraper.models import CollectorOutcome, PostRecord, TermScore
from gen_alpha_slang_scraper.utils import ensure_dir, utc_now_iso


def _save_top_terms_chart(terms: list[TermScore], output_dir: Path) -> str:
    labels = [term.term for term in terms[:12]][::-1]
    values = [term.total_score for term in terms[:12]][::-1]
    plt.figure(figsize=(10, 6))
    plt.barh(labels, values, color="#ff6b57")
    plt.xlabel("Score")
    plt.title("Top Slang / Buzz Terms")
    plt.tight_layout()
    output_path = output_dir / "top_terms.png"
    plt.savefig(output_path, dpi=160)
    plt.close()
    return output_path.name


def _save_platform_mix_chart(posts: list[PostRecord], output_dir: Path) -> str:
    counts = Counter(post.platform for post in posts)
    labels = list(counts.keys())
    values = list(counts.values())
    plt.figure(figsize=(8, 5))
    plt.bar(labels, values, color=["#0ea5e9", "#10b981", "#f59e0b", "#ef4444"])
    plt.ylabel("Posts collected")
    plt.title("Source Mix")
    plt.tight_layout()
    output_path = output_dir / "platform_mix.png"
    plt.savefig(output_path, dpi=160)
    plt.close()
    return output_path.name


def _save_buzz_vs_novelty_chart(terms: list[TermScore], output_dir: Path) -> str:
    selected = terms[:20]
    plt.figure(figsize=(8, 6))
    for term in selected:
        plt.scatter(term.novelty_score, term.buzz_score, s=40 + term.post_count * 10, alpha=0.75, color="#14b8a6")
        plt.text(term.novelty_score + 0.02, term.buzz_score + 0.02, term.term, fontsize=8)
    plt.xlabel("Novelty score")
    plt.ylabel("Buzz score")
    plt.title("Buzz vs Novelty")
    plt.tight_layout()
    output_path = output_dir / "buzz_vs_novelty.png"
    plt.savefig(output_path, dpi=160)
    plt.close()
    return output_path.name


def _write_csvs(posts: list[PostRecord], terms: list[TermScore], output_dir: Path) -> None:
    with (output_dir / "posts.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source", "platform", "external_id", "author", "created_at", "url", "text"])
        for post in posts:
            writer.writerow([post.source, post.platform, post.external_id, post.author, post.created_at, post.url, post.text])

    with (output_dir / "top_terms.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "term",
                "watchlist",
                "mention_count",
                "post_count",
                "unique_authors",
                "source_count",
                "novelty_score",
                "buzz_score",
                "discovery_score",
                "total_score",
                "platforms",
                "contexts",
            ]
        )
        for term in terms:
            writer.writerow(
                [
                    term.term,
                    term.is_watchlist,
                    term.mention_count,
                    term.post_count,
                    term.unique_authors,
                    term.source_count,
                    term.novelty_score,
                    term.buzz_score,
                    term.discovery_score,
                    term.total_score,
                    ", ".join(term.platforms),
                    " | ".join(term.contexts),
                ]
            )


def _collector_rows(outcomes: list[CollectorOutcome]) -> str:
    rows = []
    for outcome in outcomes:
        rows.append(
            "<tr>"
            f"<td>{outcome.name}</td>"
            f"<td>{outcome.platform}</td>"
            f"<td>{outcome.status}</td>"
            f"<td>{outcome.post_count}</td>"
            f"<td>{outcome.detail}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _term_rows(terms: list[TermScore]) -> str:
    rows = []
    for term in terms[:20]:
        contexts = "<br>".join(term.contexts[:3])
        rows.append(
            "<tr>"
            f"<td>{term.term}</td>"
            f"<td>{'tracked' if term.is_watchlist else 'discovered'}</td>"
            f"<td>{term.total_score}</td>"
            f"<td>{term.mention_count}</td>"
            f"<td>{', '.join(term.platforms)}</td>"
            f"<td>{contexts}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _write_summary_md(
    terms: list[TermScore],
    posts: list[PostRecord],
    outcomes: list[CollectorOutcome],
    output_dir: Path,
) -> None:
    top = ", ".join(term.term for term in terms[:10]) if terms else "none"
    lines = [
        "# Slang Scout Summary",
        "",
        f"- Generated at: {utc_now_iso()}",
        f"- Posts collected: {len(posts)}",
        f"- Top terms: {top}",
        "",
        "## Collector status",
        "",
    ]
    for outcome in outcomes:
        lines.append(f"- {outcome.name}: {outcome.status} ({outcome.post_count}) {outcome.detail}".rstrip())
    (output_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def render_dashboard(
    *,
    posts: list[PostRecord],
    terms: list[TermScore],
    outcomes: list[CollectorOutcome],
    output_dir: str,
    overview: dict[str, int],
) -> dict[str, str]:
    target_dir = ensure_dir(output_dir)
    _write_csvs(posts, terms, target_dir)
    top_terms_chart = _save_top_terms_chart(terms, target_dir) if terms else ""
    platform_mix_chart = _save_platform_mix_chart(posts, target_dir) if posts else ""
    buzz_chart = _save_buzz_vs_novelty_chart(terms, target_dir) if terms else ""
    _write_summary_md(terms, posts, outcomes, target_dir)

    html = f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Slang Scout Report</title>
    <style>
      :root {{
        --bg: #f6f0e8;
        --panel: rgba(255, 255, 255, 0.82);
        --ink: #1f2937;
        --muted: #5b6472;
        --accent: #ff6b57;
        --accent-2: #14b8a6;
        --line: rgba(31, 41, 55, 0.12);
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: "Space Grotesk", "Avenir Next", "Helvetica Neue", sans-serif;
        color: var(--ink);
        background:
          radial-gradient(circle at top left, rgba(255, 107, 87, 0.20), transparent 35%),
          radial-gradient(circle at bottom right, rgba(20, 184, 166, 0.16), transparent 30%),
          var(--bg);
      }}
      main {{ max-width: 1200px; margin: 0 auto; padding: 32px 20px 48px; }}
      .hero {{
        display: grid;
        gap: 16px;
        margin-bottom: 20px;
      }}
      .hero h1 {{
        margin: 0;
        font-size: clamp(2.1rem, 6vw, 4rem);
        line-height: 0.95;
        letter-spacing: -0.04em;
      }}
      .hero p {{ margin: 0; max-width: 72ch; color: var(--muted); }}
      .cards {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 12px;
        margin: 20px 0 28px;
      }}
      .card, .panel {{
        background: var(--panel);
        backdrop-filter: blur(14px);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 18px;
        box-shadow: 0 12px 30px rgba(31, 41, 55, 0.07);
      }}
      .card .label {{ color: var(--muted); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.08em; }}
      .card .value {{ font-size: 2rem; font-weight: 700; margin-top: 8px; }}
      .grid {{
        display: grid;
        grid-template-columns: 1.2fr 1fr;
        gap: 16px;
      }}
      .charts {{
        display: grid;
        grid-template-columns: 1fr;
        gap: 16px;
        margin-top: 16px;
      }}
      .charts img {{
        width: 100%;
        border-radius: 14px;
        border: 1px solid var(--line);
        background: white;
      }}
      table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 0.95rem;
      }}
      th, td {{
        padding: 10px 8px;
        border-bottom: 1px solid var(--line);
        vertical-align: top;
        text-align: left;
      }}
      th {{ font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); }}
      h2 {{ margin: 0 0 12px; font-size: 1.15rem; }}
      .note {{ color: var(--muted); font-size: 0.95rem; }}
      @media (max-width: 900px) {{
        .grid {{ grid-template-columns: 1fr; }}
      }}
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <h1>Slang Scout</h1>
        <p>Live public-source slang tracking run. Scores are directional monitoring signals, not platform-wide census values.</p>
      </section>

      <section class="cards">
        <div class="card"><div class="label">Generated</div><div class="value">{utc_now_iso()}</div></div>
        <div class="card"><div class="label">Posts Collected</div><div class="value">{overview.get("post_count", 0)}</div></div>
        <div class="card"><div class="label">Tracked Terms Hit</div><div class="value">{overview.get("watchlist_terms_found", 0)}</div></div>
        <div class="card"><div class="label">Novel Terms</div><div class="value">{overview.get("discovered_terms_found", 0)}</div></div>
      </section>

      <section class="grid">
        <div class="panel">
          <h2>Top Terms</h2>
          <div class="note">Highest combined buzz + novelty scores from the current run.</div>
          <table>
            <thead>
              <tr><th>Term</th><th>Type</th><th>Score</th><th>Mentions</th><th>Platforms</th><th>Evidence</th></tr>
            </thead>
            <tbody>
              {_term_rows(terms)}
            </tbody>
          </table>
        </div>
        <div class="panel">
          <h2>Collector Status</h2>
          <div class="note">Optional official collectors stay disabled until credentials are provided.</div>
          <table>
            <thead>
              <tr><th>Collector</th><th>Platform</th><th>Status</th><th>Posts</th><th>Detail</th></tr>
            </thead>
            <tbody>
              {_collector_rows(outcomes)}
            </tbody>
          </table>
        </div>
      </section>

      <section class="charts">
        <div class="panel"><h2>Top Terms Chart</h2>{f'<img src="{top_terms_chart}" alt="Top terms chart" />' if top_terms_chart else '<div class="note">No chart available.</div>'}</div>
        <div class="panel"><h2>Platform Mix</h2>{f'<img src="{platform_mix_chart}" alt="Platform mix chart" />' if platform_mix_chart else '<div class="note">No chart available.</div>'}</div>
        <div class="panel"><h2>Buzz vs Novelty</h2>{f'<img src="{buzz_chart}" alt="Buzz vs novelty chart" />' if buzz_chart else '<div class="note">No chart available.</div>'}</div>
      </section>
    </main>
  </body>
</html>
"""
    (target_dir / "report.html").write_text(html, encoding="utf-8")
    return {
        "report_html": str(target_dir / "report.html"),
        "posts_csv": str(target_dir / "posts.csv"),
        "terms_csv": str(target_dir / "top_terms.csv"),
        "summary_md": str(target_dir / "summary.md"),
    }

