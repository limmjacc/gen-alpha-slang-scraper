from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from gen_alpha_slang_scraper.models import AnalysisResult, CollectorOutcome, PostRecord, SignalPost, TermScore
from gen_alpha_slang_scraper.utils import ensure_dir, html_escape, utc_now_iso


def _save_rank_chart(terms: list[TermScore], output_dir: Path, *, filename: str, title: str, color: str, score_attr: str) -> str:
    labels = [term.term for term in terms[:12]][::-1]
    values = [getattr(term, score_attr) for term in terms[:12]][::-1]
    plt.figure(figsize=(10, 6))
    plt.barh(labels, values, color=color)
    plt.xlabel(score_attr.replace("_", " ").title())
    plt.title(title)
    plt.tight_layout()
    output_path = output_dir / filename
    plt.savefig(output_path, dpi=160)
    plt.close()
    return output_path.name


def _save_platform_mix_chart(posts: list[PostRecord], output_dir: Path) -> str:
    counts = Counter(post.platform for post in posts)
    labels = list(counts.keys())
    values = list(counts.values())
    plt.figure(figsize=(8, 5))
    plt.bar(labels, values, color=["#134074", "#ef8354", "#2ec4b6", "#7a9e7e", "#f6bd60", "#d62828"])
    plt.ylabel("Posts collected")
    plt.title("Source Mix")
    plt.tight_layout()
    output_path = output_dir / "platform_mix.png"
    plt.savefig(output_path, dpi=160)
    plt.close()
    return output_path.name


def _save_usage_vs_emergence_chart(terms: list[TermScore], output_dir: Path) -> str:
    selected = terms[:24]
    plt.figure(figsize=(8, 6))
    for term in selected:
        color = "#ef8354" if term.is_watchlist else "#2ec4b6"
        plt.scatter(term.buzz_score, term.discovery_score, s=40 + term.post_count * 16, alpha=0.8, color=color)
        plt.text(term.buzz_score + 0.05, term.discovery_score + 0.05, term.term, fontsize=8)
    plt.xlabel("Usage score")
    plt.ylabel("Emergence score")
    plt.title("Usage vs Emergence")
    plt.tight_layout()
    output_path = output_dir / "usage_vs_emergence.png"
    plt.savefig(output_path, dpi=160)
    plt.close()
    return output_path.name


def _write_terms_csv(path: Path, terms: list[TermScore]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "term",
                "watchlist",
                "stopword",
                "slang_candidate",
                "mention_count",
                "weighted_mentions",
                "hashtag_count",
                "post_count",
                "unique_authors",
                "source_count",
                "co_occurrence_hits",
                "novelty_score",
                "usage_score",
                "emergence_score",
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
                    term.is_stopword,
                    term.is_slang_candidate,
                    term.mention_count,
                    term.weighted_mentions,
                    term.hashtag_count,
                    term.post_count,
                    term.unique_authors,
                    term.source_count,
                    term.co_occurrence_hits,
                    term.novelty_score,
                    term.buzz_score,
                    term.discovery_score,
                    term.total_score,
                    ", ".join(term.platforms),
                    " | ".join(term.contexts),
                ]
            )


def _write_signal_posts_csv(path: Path, posts: list[SignalPost]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["platform", "source", "author", "created_at", "score", "matched_terms", "url", "text"])
        for post in posts:
            writer.writerow(
                [
                    post.platform,
                    post.source,
                    post.author,
                    post.created_at,
                    post.score,
                    ", ".join(post.matched_terms),
                    post.url,
                    post.text,
                ]
            )


def _write_posts_csv(posts: list[PostRecord], output_dir: Path) -> None:
    with (output_dir / "posts.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source", "platform", "external_id", "author", "created_at", "url", "text"])
        for post in posts:
            writer.writerow([post.source, post.platform, post.external_id, post.author, post.created_at, post.url, post.text])


def _term_badges(term: TermScore) -> str:
    badges = []
    if term.is_watchlist:
        badges.append('<span class="chip chip-watch">watchlist</span>')
    if term.is_slang_candidate and not term.is_watchlist:
        badges.append('<span class="chip chip-new">candidate</span>')
    if term.hashtag_count:
        badges.append(f'<span class="chip chip-neutral">hashtags {term.hashtag_count}</span>')
    if term.co_occurrence_hits:
        badges.append(f'<span class="chip chip-neutral">co-occur {term.co_occurrence_hits}</span>')
    return "".join(badges)


def _term_rows(terms: list[TermScore], *, score_attr: str, limit: int) -> str:
    rows = []
    for term in terms[:limit]:
        contexts = "<br>".join(html_escape(context) for context in term.contexts[:2])
        rows.append(
            "<tr>"
            f"<td><strong>{html_escape(term.term)}</strong><div class=\"row-chips\">{_term_badges(term)}</div></td>"
            f"<td>{getattr(term, score_attr):.3f}</td>"
            f"<td>{term.mention_count}</td>"
            f"<td>{term.post_count}</td>"
            f"<td>{', '.join(html_escape(platform) for platform in term.platforms)}</td>"
            f"<td>{contexts}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _collector_rows(outcomes: list[CollectorOutcome]) -> str:
    rows = []
    for outcome in outcomes:
        status_class = {
            "ok": "status-ok",
            "error": "status-error",
            "skipped": "status-skip",
        }.get(outcome.status, "")
        rows.append(
            "<tr>"
            f"<td>{html_escape(outcome.name)}</td>"
            f"<td>{html_escape(outcome.platform)}</td>"
            f"<td><span class=\"status-pill {status_class}\">{html_escape(outcome.status)}</span></td>"
            f"<td>{outcome.post_count}</td>"
            f"<td>{html_escape(outcome.detail)}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _highlight_terms(text: str, terms: list[str]) -> str:
    if not text:
        return ""
    unique_terms = [term for term in sorted(set(terms), key=len, reverse=True) if term]
    if not unique_terms:
        return html_escape(text)
    pattern = re.compile(r"(?i)\b(" + "|".join(re.escape(term) for term in unique_terms[:20]) + r")\b")
    parts: list[str] = []
    last = 0
    for match in pattern.finditer(text):
        parts.append(html_escape(text[last:match.start()]))
        parts.append(f"<mark>{html_escape(match.group(0))}</mark>")
        last = match.end()
    parts.append(html_escape(text[last:]))
    return "".join(parts)


def _signal_cards(posts: list[SignalPost], limit: int = 18) -> str:
    cards = []
    for post in posts[:limit]:
        chips = "".join(f'<span class="chip chip-evidence">{html_escape(term)}</span>' for term in post.matched_terms[:8])
        excerpt = _highlight_terms(post.text[:280], post.matched_terms)
        cards.append(
            "<article class=\"signal-card\">"
            f"<div class=\"signal-meta\"><span class=\"source-badge\">{html_escape(post.platform)}</span><span>{html_escape(post.author)}</span><span>{html_escape(post.source)}</span></div>"
            f"<div class=\"signal-chips\">{chips}</div>"
            f"<p class=\"signal-copy\">{excerpt}</p>"
            f"<div class=\"signal-footer\"><span>score {post.score:.2f}</span><a href=\"{html_escape(post.url)}\">open post</a></div>"
            "</article>"
        )
    return "\n".join(cards)


def _all_terms_rows(terms: list[TermScore]) -> str:
    rows = []
    for term in terms:
        classes = []
        if term.is_stopword:
            classes.append("is-stopword")
        row_class = " ".join(classes)
        rows.append(
            f"<tr class=\"{row_class}\">"
            f"<td>{html_escape(term.term)}</td>"
            f"<td>{'watchlist' if term.is_watchlist else ('candidate' if term.is_slang_candidate else 'plain')}</td>"
            f"<td>{term.mention_count}</td>"
            f"<td>{term.buzz_score:.3f}</td>"
            f"<td>{term.discovery_score:.3f}</td>"
            f"<td>{term.co_occurrence_hits}</td>"
            f"<td>{', '.join(html_escape(platform) for platform in term.platforms)}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _write_summary_md(analysis: AnalysisResult, outcomes: list[CollectorOutcome], output_dir: Path) -> None:
    top_used = ", ".join(term.term for term in analysis.most_used_terms[:10]) if analysis.most_used_terms else "none"
    top_emerging = ", ".join(term.term for term in analysis.emerging_terms[:10]) if analysis.emerging_terms else "none"
    lines = [
        "# Slang Scout Summary",
        "",
        f"- Generated at: {utc_now_iso()}",
        f"- Posts collected: {analysis.overview.get('post_count', 0)}",
        f"- All terms tracked: {analysis.overview.get('all_terms_tracked', 0)}",
        f"- Slang candidates tracked: {analysis.overview.get('slang_terms_tracked', 0)}",
        f"- Most used now: {top_used}",
        f"- Top emerging: {top_emerging}",
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
    analysis: AnalysisResult,
    outcomes: list[CollectorOutcome],
    output_dir: str,
) -> dict[str, str]:
    target_dir = ensure_dir(output_dir)
    _write_posts_csv(posts, target_dir)
    _write_terms_csv(target_dir / "all_terms.csv", analysis.all_terms)
    _write_terms_csv(target_dir / "most_used_terms.csv", analysis.most_used_terms)
    _write_terms_csv(target_dir / "emerging_terms.csv", analysis.emerging_terms)
    _write_terms_csv(target_dir / "top_terms.csv", analysis.most_used_terms)
    _write_signal_posts_csv(target_dir / "signal_posts.csv", analysis.signal_posts)

    most_used_chart = _save_rank_chart(
        analysis.most_used_terms,
        target_dir,
        filename="top_terms.png",
        title="Most Used Slang",
        color="#ef8354",
        score_attr="buzz_score",
    ) if analysis.most_used_terms else ""
    emerging_chart = _save_rank_chart(
        analysis.emerging_terms,
        target_dir,
        filename="emerging_terms.png",
        title="Top Emerging Terms",
        color="#2ec4b6",
        score_attr="discovery_score",
    ) if analysis.emerging_terms else ""
    platform_mix_chart = _save_platform_mix_chart(posts, target_dir) if posts else ""
    usage_chart = _save_usage_vs_emergence_chart(analysis.emerging_terms or analysis.most_used_terms, target_dir) if (analysis.emerging_terms or analysis.most_used_terms) else ""
    _write_summary_md(analysis, outcomes, target_dir)

    top_now_chips = "".join(
        f'<span class="hero-chip">{html_escape(term.term)}</span>' for term in analysis.most_used_terms[:10]
    )
    emerging_chips = "".join(
        f'<span class="hero-chip hero-chip-alt">{html_escape(term.term)}</span>' for term in analysis.emerging_terms[:10]
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Slang Scout Report</title>
    <style>
      :root {{
        --bg: #f7f4ec;
        --ink: #13293d;
        --muted: #5d6b78;
        --paper: rgba(255, 255, 255, 0.82);
        --line: rgba(19, 41, 61, 0.14);
        --coral: #ef8354;
        --teal: #2ec4b6;
        --gold: #f6bd60;
        --navy: #134074;
        --shadow: 0 22px 50px rgba(19, 41, 61, 0.10);
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        color: var(--ink);
        font-family: "Avenir Next", "Gill Sans", "Trebuchet MS", sans-serif;
        background:
          radial-gradient(circle at 0% 0%, rgba(239, 131, 84, 0.22), transparent 28%),
          radial-gradient(circle at 100% 10%, rgba(46, 196, 182, 0.22), transparent 30%),
          linear-gradient(180deg, #fffdf8 0%, var(--bg) 100%);
      }}
      main {{ max-width: 1340px; margin: 0 auto; padding: 28px 20px 52px; }}
      .hero {{
        position: relative;
        overflow: hidden;
        padding: 30px;
        border-radius: 30px;
        background: linear-gradient(135deg, rgba(19, 64, 116, 0.92), rgba(19, 64, 116, 0.74));
        color: #fefcf6;
        box-shadow: var(--shadow);
      }}
      .hero::after {{
        content: "";
        position: absolute;
        inset: auto -10% -35% auto;
        width: 320px;
        height: 320px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(246, 189, 96, 0.22), transparent 65%);
      }}
      .eyebrow {{
        text-transform: uppercase;
        letter-spacing: 0.14em;
        font-size: 0.78rem;
        color: rgba(254, 252, 246, 0.72);
      }}
      h1 {{
        margin: 10px 0 8px;
        font-family: "Iowan Old Style", "Palatino Linotype", "Book Antiqua", serif;
        font-size: clamp(2.5rem, 6vw, 5rem);
        line-height: 0.95;
        letter-spacing: -0.04em;
      }}
      .hero p {{
        max-width: 68ch;
        margin: 0;
        color: rgba(254, 252, 246, 0.82);
      }}
      .hero-band {{
        display: grid;
        grid-template-columns: 1.3fr 1fr;
        gap: 20px;
        margin-top: 24px;
      }}
      .hero-stack {{ display: grid; gap: 12px; }}
      .hero-chipline, .row-chips, .signal-chips {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }}
      .hero-chip, .chip {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        border-radius: 999px;
        padding: 6px 10px;
        font-size: 0.84rem;
        line-height: 1;
        border: 1px solid rgba(19, 41, 61, 0.08);
      }}
      .hero-chip {{
        background: rgba(255, 255, 255, 0.12);
        border-color: rgba(255, 255, 255, 0.12);
        color: #fff9ef;
      }}
      .hero-chip-alt {{ background: rgba(46, 196, 182, 0.18); }}
      .stats {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 12px;
        margin: 18px 0 22px;
      }}
      .panel, .stat {{
        background: var(--paper);
        border: 1px solid var(--line);
        border-radius: 24px;
        backdrop-filter: blur(12px);
        box-shadow: var(--shadow);
      }}
      .stat {{
        padding: 18px;
      }}
      .stat-label {{
        font-size: 0.82rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: var(--muted);
      }}
      .stat-value {{
        font-size: 2rem;
        font-weight: 700;
        margin-top: 8px;
      }}
      .layout {{
        display: grid;
        grid-template-columns: 1.2fr 1fr;
        gap: 16px;
      }}
      .panel {{
        padding: 22px;
      }}
      .section-head {{
        display: flex;
        justify-content: space-between;
        align-items: end;
        gap: 16px;
        margin-bottom: 14px;
      }}
      h2 {{
        margin: 0;
        font-size: 1.28rem;
        letter-spacing: -0.03em;
      }}
      .note {{
        color: var(--muted);
        font-size: 0.95rem;
      }}
      table {{
        width: 100%;
        border-collapse: collapse;
      }}
      th, td {{
        padding: 12px 10px;
        text-align: left;
        vertical-align: top;
        border-bottom: 1px solid var(--line);
      }}
      th {{
        font-size: 0.77rem;
        text-transform: uppercase;
        letter-spacing: 0.11em;
        color: var(--muted);
      }}
      .chip-watch {{ background: rgba(239, 131, 84, 0.12); color: #9d3d17; }}
      .chip-new {{ background: rgba(46, 196, 182, 0.14); color: #0d6f66; }}
      .chip-neutral {{ background: rgba(19, 41, 61, 0.08); color: var(--ink); }}
      .chip-evidence {{ background: rgba(246, 189, 96, 0.18); color: #7b5711; border-color: rgba(246, 189, 96, 0.25); }}
      .status-pill {{
        display: inline-flex;
        border-radius: 999px;
        padding: 6px 10px;
        font-size: 0.82rem;
      }}
      .status-ok {{ background: rgba(46, 196, 182, 0.16); color: #0d6f66; }}
      .status-error {{ background: rgba(214, 40, 40, 0.14); color: #9a2222; }}
      .status-skip {{ background: rgba(246, 189, 96, 0.2); color: #825b0c; }}
      .charts {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 16px;
        margin-top: 16px;
      }}
      .charts img {{
        width: 100%;
        display: block;
        border-radius: 18px;
        background: white;
        border: 1px solid var(--line);
      }}
      .signal-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(290px, 1fr));
        gap: 14px;
      }}
      .signal-card {{
        border: 1px solid var(--line);
        border-radius: 22px;
        padding: 16px;
        background: linear-gradient(180deg, rgba(255,255,255,0.88), rgba(255,255,255,0.7));
      }}
      .signal-meta, .signal-footer {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        font-size: 0.84rem;
        color: var(--muted);
      }}
      .source-badge {{
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--navy);
        font-weight: 700;
      }}
      .signal-copy {{
        margin: 14px 0;
        line-height: 1.55;
      }}
      .signal-copy mark {{
        background: rgba(246, 189, 96, 0.42);
        color: inherit;
        padding: 0 2px;
        border-radius: 3px;
      }}
      .signal-footer {{
        justify-content: space-between;
      }}
      .signal-footer a, .hero a {{
        color: var(--navy);
      }}
      .all-terms-tools {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-bottom: 14px;
      }}
      input[type="search"] {{
        flex: 1 1 260px;
        min-width: 220px;
        padding: 12px 14px;
        border-radius: 999px;
        border: 1px solid var(--line);
        background: rgba(255,255,255,0.9);
        color: var(--ink);
      }}
      .legend {{
        font-size: 0.88rem;
        color: var(--muted);
      }}
      .table-wrap {{
        max-height: 520px;
        overflow: auto;
      }}
      .is-stopword {{
        opacity: 0.55;
      }}
      @media (max-width: 980px) {{
        .hero-band, .layout {{
          grid-template-columns: 1fr;
        }}
      }}
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <div class="eyebrow">Slang Intelligence Report</div>
        <h1>Exactly What The Feed Is Saying</h1>
        <p>This run tracks every extracted term from collected posts, then breaks the data into separate views for what is most used right now and what looks newly emergent.</p>
        <div class="hero-band">
          <div class="hero-stack">
            <div class="eyebrow">Most Used Now</div>
            <div class="hero-chipline">{top_now_chips}</div>
          </div>
          <div class="hero-stack">
            <div class="eyebrow">Emerging Candidates</div>
            <div class="hero-chipline">{emerging_chips}</div>
          </div>
        </div>
      </section>

      <section class="stats">
        <div class="stat"><div class="stat-label">Generated</div><div class="stat-value">{utc_now_iso()}</div></div>
        <div class="stat"><div class="stat-label">Posts Collected</div><div class="stat-value">{analysis.overview.get("post_count", 0)}</div></div>
        <div class="stat"><div class="stat-label">All Terms Tracked</div><div class="stat-value">{analysis.overview.get("all_terms_tracked", 0)}</div></div>
        <div class="stat"><div class="stat-label">Slang Candidates</div><div class="stat-value">{analysis.overview.get("slang_terms_tracked", 0)}</div></div>
        <div class="stat"><div class="stat-label">Signal Posts</div><div class="stat-value">{analysis.overview.get("signal_posts_count", 0)}</div></div>
      </section>

      <section class="layout">
        <div class="panel">
          <div class="section-head">
            <div>
              <h2>Most Used Right Now</h2>
              <div class="note">High-usage slang and tracked terms across the current run.</div>
            </div>
          </div>
          <table>
            <thead>
              <tr><th>Term</th><th>Usage</th><th>Mentions</th><th>Posts</th><th>Platforms</th><th>Evidence</th></tr>
            </thead>
            <tbody>
              {_term_rows(analysis.most_used_terms, score_attr="buzz_score", limit=15)}
            </tbody>
          </table>
        </div>

        <div class="panel">
          <div class="section-head">
            <div>
              <h2>Top Emerging</h2>
              <div class="note">Terms boosted by novelty, recency, hashtags, and co-occurrence with known slang.</div>
            </div>
          </div>
          <table>
            <thead>
              <tr><th>Term</th><th>Emergence</th><th>Mentions</th><th>Posts</th><th>Platforms</th><th>Evidence</th></tr>
            </thead>
            <tbody>
              {_term_rows(analysis.emerging_terms, score_attr="discovery_score", limit=15)}
            </tbody>
          </table>
        </div>
      </section>

      <section class="panel" style="margin-top: 16px;">
        <div class="section-head">
          <div>
            <h2>Signal Posts</h2>
            <div class="note">Each card shows the exact matched terms pulled from that post, so co-occurring slang like <code>bussin</code> does not disappear inside another term's evidence row.</div>
          </div>
        </div>
        <div class="signal-grid">
          {_signal_cards(analysis.signal_posts)}
        </div>
      </section>

      <section class="charts">
        <div class="panel"><div class="section-head"><h2>Most Used Chart</h2><div class="note">Usage score ranking</div></div>{f'<img src="{most_used_chart}" alt="Most used slang chart" />' if most_used_chart else ''}</div>
        <div class="panel"><div class="section-head"><h2>Emerging Chart</h2><div class="note">Emergence score ranking</div></div>{f'<img src="{emerging_chart}" alt="Emerging terms chart" />' if emerging_chart else ''}</div>
        <div class="panel"><div class="section-head"><h2>Source Mix</h2><div class="note">Collected post volume by platform</div></div>{f'<img src="{platform_mix_chart}" alt="Platform mix chart" />' if platform_mix_chart else ''}</div>
        <div class="panel"><div class="section-head"><h2>Usage vs Emergence</h2><div class="note">Top terms plotted by both dimensions</div></div>{f'<img src="{usage_chart}" alt="Usage vs emergence chart" />' if usage_chart else ''}</div>
      </section>

      <section class="layout" style="margin-top: 16px;">
        <div class="panel">
          <div class="section-head">
            <div>
              <h2>All Tracked Terms</h2>
              <div class="note">This inventory includes every extracted normalized term from collected posts. Use the search box to inspect anything the scraper saw.</div>
            </div>
          </div>
          <div class="all-terms-tools">
            <input id="termSearch" type="search" placeholder="Filter tracked terms..." />
            <div class="legend">`plain` terms are still tracked even if they are not currently classified as slang candidates.</div>
          </div>
          <div class="table-wrap">
            <table id="allTermsTable">
              <thead>
                <tr><th>Term</th><th>Class</th><th>Mentions</th><th>Usage</th><th>Emergence</th><th>Co-occur</th><th>Platforms</th></tr>
              </thead>
              <tbody>
                {_all_terms_rows(analysis.all_terms)}
              </tbody>
            </table>
          </div>
        </div>

        <div class="panel">
          <div class="section-head">
            <div>
              <h2>Collector Status</h2>
              <div class="note">Official APIs remain optional. Public web and public API sources are mixed here.</div>
            </div>
          </div>
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
    </main>
    <script>
      const searchInput = document.getElementById("termSearch");
      const table = document.getElementById("allTermsTable");
      if (searchInput && table) {{
        const rows = Array.from(table.querySelectorAll("tbody tr"));
        searchInput.addEventListener("input", () => {{
          const query = searchInput.value.trim().toLowerCase();
          rows.forEach((row) => {{
            row.style.display = row.textContent.toLowerCase().includes(query) ? "" : "none";
          }});
        }});
      }}
    </script>
  </body>
</html>
"""
    (target_dir / "report.html").write_text(html, encoding="utf-8")
    return {
        "report_html": str(target_dir / "report.html"),
        "posts_csv": str(target_dir / "posts.csv"),
        "terms_csv": str(target_dir / "top_terms.csv"),
        "all_terms_csv": str(target_dir / "all_terms.csv"),
        "emerging_terms_csv": str(target_dir / "emerging_terms.csv"),
        "signal_posts_csv": str(target_dir / "signal_posts.csv"),
        "summary_md": str(target_dir / "summary.md"),
    }
