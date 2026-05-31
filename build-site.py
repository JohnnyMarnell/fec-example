#!/usr/bin/env python3
"""Build static GitHub Pages site from FEC project outputs.

Run:  python build-site.py
Out:  docs/   (configure GitHub Pages → main branch → /docs folder)
"""
import csv
import html as html_mod
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
DOCS = ROOT / "docs"
OUT_CHARTS = ROOT / "output" / "charts"
OUT_SCHEDULE_A = ROOT / "output" / "schedule_a"
OUT_TABLES = ROOT / "output" / "tables"
NOTEBOOKS_DIR = ROOT / "notebooks"
DOCS_SRC = ROOT / "docs-src"

# Markdown pages: (slug, title, source path, nav order). Rendered to docs/<slug>/index.html.
DESIGN_DOCS = [
    ("sas-port", "SAS Port Design", DOCS_SRC / "sas-port.md"),
]

BUILD_DATE = datetime.now().strftime("%B %d, %Y")
GITHUB_REPO = "https://github.com/JohnnyMarnell/fec-example"

SOURCE_FILES = [
    ("fec_client.py", "python", "fec_client.py"),
    ("api-demo.py",   "python", "api-demo.py"),
    ("main.py",       "python", "main.py"),
    ("Justfile",      "makefile", "Justfile"),
]

# Columns to show in schedule_a CSV preview (in order, skip missing ones)
PREVIEW_COLS = [
    "contributor_name", "contribution_receipt_amount", "contribution_receipt_date",
    "contributor_employer", "contributor_occupation", "contributor_city",
    "contributor_state", "committee_name",
]


# ── Discovery helpers ──────────────────────────────────────────────────────

def find_notebooks() -> list[Path]:
    """All rendered .html files under notebooks/ (skips checkpoints)."""
    if not NOTEBOOKS_DIR.exists():
        return []
    return sorted(
        p for p in NOTEBOOKS_DIR.glob("*.html")
        if ".ipynb_checkpoints" not in str(p)
    )


def notebook_slug(path: Path) -> str:
    return path.stem.lower().replace("_", "-")


def notebook_display(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " ").title()


def company_from_filename(stem: str) -> str:
    """TRACTOR_SUPPLY_2019-01-01_2020-12-31 → TRACTOR SUPPLY"""
    import re as _re
    name = _re.sub(r"_\d{4}-\d{2}-\d{2}.*$", "", stem)
    return name.replace("_", " ").strip()


HLJS_CSS  = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.10.0/styles/github.min.css"
HLJS_JS   = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.10.0/highlight.min.js"
TAILWIND  = "https://cdn.tailwindcss.com"
MERMAID_JS = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"


# ── Helpers ────────────────────────────────────────────────────────────────

def esc(s: str) -> str:
    return html_mod.escape(str(s))


def nav(active: str, depth: int) -> str:
    b = "../" * depth
    items = {
        "home":     (f"{b}index.html",         "Home"),
        "notebook": (f"{b}notebook/",           "Notebooks"),
        "design":   (f"{b}design/sas-port/",    "Design"),
        "data":     (f"{b}data/",               "Data"),
        "sql":      (f"{b}sql/",               "SQL"),
        "source":   (f"{b}source/",             "Source"),
    }
    links = []
    for key, (href, label) in items.items():
        cls = "text-indigo-300 font-semibold border-b-2 border-indigo-400 pb-0.5" \
              if key == active else \
              "text-slate-300 hover:text-white transition-colors"
        links.append(f'<a href="{href}" class="{cls} text-sm">{label}</a>')
    return f'<nav class="bg-slate-800 px-6 py-2.5 flex gap-8 border-b border-slate-700/60">{"  ".join(links)}</nav>'


def page(title: str, body: str, active: str, depth: int = 1,
         extra_head: str = "", main_class: str = "max-w-6xl mx-auto px-6 py-10 flex-1") -> str:
    b = "../" * depth
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)} · FEC Analysis</title>
  <link rel="icon" type="image/svg+xml" href="{b}favicon.svg">
  <script src="{TAILWIND}"></script>
  <link rel="stylesheet" href="{HLJS_CSS}">
  <script src="{HLJS_JS}"></script>
  <script>document.addEventListener('DOMContentLoaded', () => hljs.highlightAll());</script>
  <style>
    pre code.hljs {{
      font-size: 0.8rem; line-height: 1.7;
      border-radius: 0.5rem; padding: 1.25rem 1.5rem;
      border: 1px solid #e5e7eb;
    }}
    html {{ scroll-behavior: smooth; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; }}
    .badge-d {{ background: #dbeafe; color: #1d4ed8; }}
    .badge-r {{ background: #fee2e2; color: #b91c1c; }}
    .badge-n {{ background: #f3f4f6; color: #6b7280; }}
    /* Force monospace on all code/highlight blocks (nbconvert's Pygments output
       uses font-family: inherit, which otherwise picks up the body sans-serif). */
    pre, code, .highlight, .highlight pre, .highlight code,
    .jp-RenderedHTMLCommon pre, .jp-RenderedHTMLCommon code,
    .jp-RenderedMarkdown pre, .jp-RenderedMarkdown code,
    [data-mime-type="text/markdown"] pre, [data-mime-type="text/markdown"] code {{
      font-family: ui-monospace, SFMono-Regular, "JetBrains Mono", "Cascadia Code", Menlo, Consolas, monospace !important;
    }}
    /* Markdown prose blocks (Design page) */
    .prose h1 {{ font-size: 1.875rem; font-weight: 800; color: #0f172a; margin: 0 0 1rem; }}
    .prose h2 {{ font-size: 1.4rem; font-weight: 700; color: #0f172a;
                 margin: 2.25rem 0 .75rem; padding-bottom: .3rem; border-bottom: 1px solid #e2e8f0; }}
    .prose h3 {{ font-size: 1.1rem; font-weight: 600; color: #1e293b; margin: 1.75rem 0 .6rem; }}
    .prose h4 {{ font-size: 1rem; font-weight: 600; color: #334155; margin: 1.25rem 0 .5rem; }}
    .prose p {{ color: #334155; line-height: 1.7; margin: .65rem 0; }}
    .prose ul, .prose ol {{ color: #334155; line-height: 1.7; margin: .5rem 0 .9rem 1.25rem; }}
    .prose ul {{ list-style: disc; }}
    .prose ol {{ list-style: decimal; }}
    .prose li {{ margin: .15rem 0; }}
    .prose a {{ color: #4f46e5; text-decoration: underline; text-underline-offset: 2px; }}
    .prose a:hover {{ color: #4338ca; }}
    .prose strong {{ color: #0f172a; font-weight: 600; }}
    .prose blockquote {{
      border-left: 3px solid #6366f1; background: #eef2ff;
      padding: .6rem 1rem; margin: 1rem 0; color: #334155; border-radius: 0 .375rem .375rem 0;
    }}
    .prose blockquote p {{ margin: .25rem 0; }}
    .prose code {{
      background: #f1f5f9; color: #be185d;
      padding: .1em .35em; border-radius: .25rem;
      font-size: .85em; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    }}
    .prose pre {{
      background: #0f172a; color: #f1f5f9;
      padding: 1rem 1.25rem; border-radius: .5rem;
      overflow-x: auto; margin: 1rem 0;
      font-size: .82rem; line-height: 1.6;
    }}
    .prose pre code {{ background: transparent; color: inherit; padding: 0; }}
    .prose pre.filetree {{
      background: #f8fafc; color: #334155;
      border: 1px solid #e2e8f0; border-left: 3px solid #6366f1;
    }}
    .mermaid {{ margin: 1.25rem 0; text-align: center; }}
    .prose table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: .9rem; }}
    .prose th, .prose td {{
      border: 1px solid #e2e8f0; padding: .5rem .75rem; text-align: left; vertical-align: top;
    }}
    .prose th {{ background: #f8fafc; font-weight: 600; color: #0f172a; }}
    .prose tr:nth-child(even) td {{ background: #fafbfc; }}
    .prose hr {{ border: 0; border-top: 1px solid #e2e8f0; margin: 1.75rem 0; }}
  </style>
  {extra_head}
</head>
<body class="bg-slate-50 text-slate-900 min-h-screen flex flex-col">
  <header class="bg-slate-900 text-white shadow-lg">
    <div class="max-w-6xl mx-auto px-6 py-4 flex items-start justify-between">
      <div>
        <a href="{b}index.html" class="text-lg font-bold tracking-tight hover:text-indigo-300 transition-colors">
          FEC Contribution Analysis
        </a>
        <p class="text-slate-400 text-xs mt-0.5">OpenFEC · Political contribution explorer</p>
      </div>
      <a href="{GITHUB_REPO}" target="_blank" rel="noopener"
         class="text-slate-400 hover:text-white text-xs flex items-center gap-1.5 mt-1 transition-colors">
        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.92.359.31.678.921.678 1.856 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/></svg>
        GitHub
      </a>
    </div>
  </header>
  {nav(active, depth)}
  <main class="{main_class}">
    {body}
  </main>
  <footer class="border-t border-slate-200 py-5 text-center text-xs text-slate-400">
    Generated {BUILD_DATE} ·
    <a href="{GITHUB_REPO}" target="_blank" rel="noopener" class="hover:text-slate-700 underline">GitHub</a> ·
    <a href="{b}source/" class="hover:text-slate-700 underline">Source code</a>
  </footer>
</body>
</html>"""


# ── Homepage ───────────────────────────────────────────────────────────────

def _read_summary() -> dict:
    p = OUT_TABLES / "summary.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}
    return {}


def _company_tilts() -> list[dict]:
    """Per-company D/R/N share + dominant lean from company_contributors.csv."""
    p = OUT_TABLES / "company_contributors.csv"
    if not p.exists():
        return []
    out = []
    with open(p) as f:
        for r in csv.DictReader(f):
            try:
                d = int(r.get("Dnum") or 0)
                rep = int(r.get("Rnum") or 0)
                o = int(r.get("Onum") or 0)
                total = d + rep + o
                if total == 0:
                    continue
                if d >= rep and d >= o:
                    lean, color = f"Democrat ({d/total*100:.0f}%)", "badge-d"
                elif rep >= d and rep >= o:
                    lean, color = f"Republican ({rep/total*100:.0f}%)", "badge-r"
                else:
                    lean, color = f"Mixed ({o/total*100:.0f}% N)", "badge-n"
                out.append({
                    "company":  r.get("Company", ""),
                    "people":   total,
                    "dollars":  float(r.get("contribsum") or 0),
                    "lean":     lean,
                    "color":    color,
                    "d_share":  d / total,
                    "r_share":  rep / total,
                    "o_share":  o / total,
                })
            except (ValueError, KeyError):
                continue
    return out


def _tilt_bar(d: float, r: float, o: float) -> str:
    """Three-color horizontal share bar; widths sum to 100%."""
    dp, rp, op_ = d * 100, r * 100, o * 100
    return (
        '<div class="flex w-full h-2 rounded-full overflow-hidden bg-slate-100">'
        f'<div style="width:{dp:.1f}%" class="bg-blue-500"></div>'
        f'<div style="width:{rp:.1f}%" class="bg-red-500"></div>'
        f'<div style="width:{op_:.1f}%" class="bg-slate-400"></div>'
        '</div>'
    )


# Featured chart order — hero first, then 2-col grid (most interesting first).
_CHART_ORDER = [
    ("cross_company_party_stack.png",   "Cross-company party breakdown",
                                        "Unique contributors classified by the 60 % rule, side by side.", True),
    ("cross_company_outflow_by_party.png", "Outflow by recipient candidate party",
                                        "Schedule B disbursements sliced by /candidate/-resolved recipient party.", False),
    ("cross_company_schedule_b.png",    "Top recipients per PAC",
                                        "Where each corporate PAC actually sent the money (Schedule B).", False),
    ("cross_company_monthly.png",       "Monthly inflow by party",
                                        "2020 election surge by party across each employer.", False),
    ("cross_company_top_states.png",    "Top contributing states",
                                        "Geographic distribution of contributions across all employers.", False),
    ("cross_company_committee_types.png", "Recipient committee types",
                                        "Mix of PAC types, candidate committees, party committees.", False),
]


def build_index(charts: list[str], data_files: list[str], notebooks: list[Path]) -> None:
    chart_set = set(charts)
    summary = _read_summary()
    tilts = _company_tilts()

    # Headline numbers — prefer summary.json, fall back to the schedule_a CSVs.
    if summary:
        n_companies = len(summary.get("companies") or [])
        inflow      = summary.get("inflow_dollars", 0)
        outflow     = summary.get("outflow_dollars", 0)
        n_contribs  = summary.get("unique_contributors", 0)
        n_states    = summary.get("states", 0)
    else:
        # Fallback (single-notebook era)
        csvs = [f for f in data_files if f.endswith(".csv")]
        inflow = 0.0
        all_states: set[str] = set()
        companies_found: list[str] = []
        seen: set[str] = set()
        for filename in csvs:
            cname = company_from_filename(Path(filename).stem)
            if cname not in seen:
                companies_found.append(cname); seen.add(cname)
            try:
                with open(OUT_SCHEDULE_A / filename) as f:
                    for r in csv.DictReader(f):
                        inflow += float(r.get("contribution_receipt_amount", 0) or 0)
                        st = r.get("contributor_state")
                        if st:
                            all_states.add(st)
            except Exception:
                pass
        n_companies = len(companies_found)
        outflow     = 0
        n_contribs  = 0
        n_states    = len(all_states)

    # ── Quick-link cards ──────────────────────────────────────────────────
    nb_count = len(notebooks)
    nb_label = f"{nb_count} notebook{'s' if nb_count != 1 else ''}"
    nb_desc  = (
        f"{nb_label}: a basic 60 %-rule analysis and a multi-company port of the SAS "
        f"pipeline (Schedule A inflow + Schedule B outflow + 60 % classification)."
    )
    quick_links = f"""
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-10">
        {link_card("notebook/cross-company/", "Cross-company", nb_desc, "📓")}
        {link_card("design/sas-port/",        "Design",        "How the SAS pipeline maps to DuckDB + pandas, end to end.", "📐")}
        {link_card("data/",                   "Data",          "Schedule A receipts and SAS-parity output tables.", "📂")}
        {link_card("source/",                 "Source",        "Python client, builder script, and Justfile recipes.", "🔍")}
      </div>"""

    # ── Stat tiles ────────────────────────────────────────────────────────
    stats_html = f"""
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-10">
          {stat_card("Companies",     str(n_companies),
                     "Fortune-500 employers analyzed")}
          {stat_card("Inflow $",      f"${inflow:,.0f}",
                     f"{n_contribs:,} unique contributors (60 % rule)")}
          {stat_card("Outflow $",     f"${outflow:,.0f}",
                     f"{summary.get('outflow_records', 0):,} Schedule B disbursements")}
          {stat_card("States",        str(n_states),
                     "represented across all transactions")}
        </div>"""

    # ── What's new beyond the SAS pipeline ────────────────────────────────
    beyond_sas_html = f"""
      <section class="mb-10">
        <div class="bg-gradient-to-br from-indigo-50 to-white border border-indigo-100 rounded-xl p-6 shadow-sm">
          <div class="flex items-baseline justify-between mb-3">
            <h2 class="text-lg font-semibold text-slate-800">Beyond the original SAS pipeline</h2>
            <a href="design/sas-port/" class="text-xs text-indigo-600 hover:underline">Design doc →</a>
          </div>
          <p class="text-sm text-slate-500 mb-4 max-w-3xl">
            The SAS pipeline ran <span class="font-mono">sascsvc19.sas</span> against pre-downloaded CSVs and lookup tables.
            This port keeps the full SAS logic — committee→party join, gender inference,
            60 % rule, two-track contributor/contribution outputs — and adds four things SAS never had.
          </p>
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
            <div class="bg-white border border-slate-200 rounded-lg p-3">
              <p class="font-semibold text-slate-800 mb-1">Schedule B outflow</p>
              <p class="text-xs text-slate-500">Where each corporate PAC ultimately spent the money. ${outflow:,.0f} across {summary.get('outflow_records', 0)} disbursements.</p>
            </div>
            <div class="bg-white border border-slate-200 rounded-lg p-3">
              <p class="font-semibold text-slate-800 mb-1">API-direct party</p>
              <p class="text-xs text-slate-500">Committee party comes from the embedded API field, with <code class="text-[10px]">/committee/{{id}}/</code> filling nulls — no static <code class="text-[10px]">AllPacs.csv</code> needed.</p>
            </div>
            <div class="bg-white border border-slate-200 rounded-lg p-3">
              <p class="font-semibold text-slate-800 mb-1">Candidate enrichment</p>
              <p class="text-xs text-slate-500"><code class="text-[10px]">/candidate/{{id}}/</code> resolves recipient party + office. Outflow can be sliced by who actually got the money.</p>
            </div>
            <div class="bg-white border border-slate-200 rounded-lg p-3">
              <p class="font-semibold text-slate-800 mb-1">Side-by-side companies</p>
              <p class="text-xs text-slate-500">SAS produced one PROC TABULATE page per employer. Here all {n_companies} employers appear together in stacked bars, time series, and state maps.</p>
            </div>
          </div>
        </div>
      </section>"""

    # ── Per-company tilt strip ────────────────────────────────────────────
    tilts_html = ""
    if tilts:
        cards = ""
        for t in tilts:
            cards += f"""
        <div class="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
          <div class="flex items-center justify-between mb-1.5">
            <span class="font-semibold text-slate-900 text-sm">{esc(t['company'])}</span>
            <span class="text-[10px] px-1.5 py-0.5 rounded {esc(t['color'])} font-semibold whitespace-nowrap">
              {esc(t['lean'])}
            </span>
          </div>
          <p class="text-xs text-slate-400 mb-2.5">
            {t['people']} contributors · ${t['dollars']:,.0f}
          </p>
          {_tilt_bar(t['d_share'], t['r_share'], t['o_share'])}
        </div>"""
        tilts_html = f"""
      <section class="mb-12">
        <div class="flex items-baseline justify-between mb-3">
          <h2 class="text-lg font-semibold text-slate-800">Lean by employer</h2>
          <span class="text-xs text-slate-400">contributors classified by 60 % rule</span>
        </div>
        <div class="grid grid-cols-2 lg:grid-cols-4 gap-3">{cards}</div>
      </section>"""

    # ── Charts: hero + supporting grid ────────────────────────────────────
    hero_html = ""
    grid_imgs = ""
    for fname, title, caption, is_hero in _CHART_ORDER:
        if fname not in chart_set:
            continue
        fig = f"""
      <figure class="rounded-xl overflow-hidden border border-slate-200 shadow-sm bg-white">
        <img src="charts/{esc(fname)}" alt="{esc(title)}"
             class="w-full object-contain {'max-h-[480px]' if is_hero else 'max-h-[300px]'}">
        <figcaption class="px-4 py-2 bg-slate-50 border-t border-slate-100">
          <span class="text-sm font-semibold text-slate-700">{esc(title)}</span>
          <span class="text-xs text-slate-500"> · {esc(caption)}</span>
        </figcaption>
      </figure>"""
        if is_hero:
            hero_html += fig
        else:
            grid_imgs += fig

    charts_section = ""
    if hero_html or grid_imgs:
        charts_section = f"""
      <section class="mb-12">
        <h2 class="text-lg font-semibold text-slate-800 mb-4">Findings</h2>
        {hero_html}
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">{grid_imgs}</div>
      </section>"""
    elif charts:
        # Unknown chart names — fall back to a generic grid
        charts_section = '<section class="mb-12"><h2 class="text-lg font-semibold text-slate-800 mb-4">Charts</h2>'
        for fname in sorted(charts):
            charts_section += f'<img src="charts/{esc(fname)}" class="w-full mb-4 rounded-xl border border-slate-200">'
        charts_section += "</section>"
    else:
        charts_section = (
            '<p class="text-slate-400 text-sm mb-12">'
            'No charts yet — run <code>just build</code> first.</p>'
        )

    pipeline_html = """
      <section class="mb-12">
        <h2 class="text-lg font-semibold text-slate-800 mb-3">Pipeline</h2>
        <div class="bg-white rounded-xl border border-slate-200 p-5 shadow-sm font-mono text-sm text-slate-700 space-y-1">
          <div><span class="text-green-600 font-bold">just build</span>  <span class="text-slate-400"># prewarm → analyze → notebooks → site</span></div>
          <div class="pl-4 text-slate-500">↳ prewarm-cache hits Schedule A + B + /committee/ for every employer (idempotent)</div>
          <div class="pl-4 text-slate-500">↳ notebooks/cross-company.ipynb runs the SAS-port pipeline, writes tables + charts</div>
          <div class="pl-4 text-slate-500">↳ build-site.py renders this page from the latest outputs</div>
        </div>
      </section>"""

    # ── Title ─────────────────────────────────────────────────────────────
    if summary and len(summary.get("company_display") or []) >= 2:
        company_line = " · ".join(summary["company_display"])
    elif tilts:
        company_line = " · ".join(t["company"] for t in tilts)
    else:
        company_line = ""

    body = f"""
    <div class="mb-10">
      <h1 class="text-3xl font-bold text-slate-900 mb-2">
        Cross-Company FEC Analysis
        <span class="text-slate-400 font-normal text-2xl">· {summary.get('min_date', '2019-01-01')} → {summary.get('max_date', '2020-12-31')}</span>
      </h1>
      <p class="text-slate-500 max-w-2xl">
        Pulls Schedule A receipts and Schedule B disbursements from the
        <a href="https://api.open.fec.gov/" target="_blank" rel="noopener" class="text-indigo-600 hover:underline">OpenFEC API</a>,
        joins committee-to-party lookups, classifies contributors with the
        <strong>60 % rule</strong>, and lines up inflow vs. outflow side by side.
      </p>
      {f'<p class="text-xs text-slate-400 mt-2 font-mono">{esc(company_line)}</p>' if company_line else ''}
    </div>
    {quick_links}
    {stats_html}
    {beyond_sas_html}
    {tilts_html}
    {charts_section}
    {pipeline_html}"""

    (DOCS / "index.html").write_text(page("Home", body, "home", depth=0))
    print("  index.html")


def stat_card(label: str, value: str, sub: str) -> str:
    return f"""<div class="bg-white rounded-xl border border-slate-200 p-4 shadow-sm">
    <p class="text-xs text-slate-500 font-medium uppercase tracking-wide">{esc(label)}</p>
    <p class="text-2xl font-bold text-slate-900 mt-1">{esc(value)}</p>
    <p class="text-xs text-slate-400 mt-1">{esc(sub)}</p>
  </div>"""


def link_card(href: str, title: str, desc: str, icon: str) -> str:
    return f"""<a href="{href}" class="block bg-white rounded-xl border border-slate-200 p-5 shadow-sm
              hover:border-indigo-400 hover:shadow-md transition-all group">
    <div class="text-2xl mb-2">{icon}</div>
    <h3 class="font-semibold text-slate-900 group-hover:text-indigo-700 transition-colors">{esc(title)}</h3>
    <p class="text-sm text-slate-500 mt-1">{esc(desc)}</p>
  </a>"""


# ── Notebooks ──────────────────────────────────────────────────────────────

_USERNAME_PATH_RE = None  # lazy

def _scrub_username(html: str) -> str:
    """Replace absolute paths under /Users/<actual-user>/ or /home/<user>/ with ~/.

    Defensive belt-and-braces; the notebook also prints relative paths now, but
    any leaked /Users/.../ string in cell output would land in the rendered HTML
    unless we strip it here.
    """
    global _USERNAME_PATH_RE
    if _USERNAME_PATH_RE is None:
        import re as _re
        # /Users/<word>/ or /home/<word>/ followed by anything
        _USERNAME_PATH_RE = _re.compile(r"(/Users|/home)/([A-Za-z0-9_.\-]+)/")
    return _USERNAME_PATH_RE.sub("~/", html)


def _inline_notebook(nb_path: Path) -> tuple[str, str]:
    """Return (extra_head_styles, body_content) extracted from a Jupyter HTML export."""
    import re as _re
    raw = _scrub_username(nb_path.read_text())
    head_end = raw.find("</head>")
    nb_styles = "\n".join(_re.findall(r"<style[^>]*>.*?</style>", raw[:head_end + 7], _re.DOTALL))
    body_match = _re.search(r"<body[^>]*>(.*)</body>", raw, _re.DOTALL)
    nb_body = body_match.group(1).strip() if body_match else "<p>Could not parse notebook.</p>"
    return nb_styles, nb_body


def build_notebooks(notebooks: list[Path]) -> None:
    nb_dir = DOCS / "notebook"
    nb_dir.mkdir(exist_ok=True)

    # ── Individual notebook pages ──────────────────────────────────────────
    for nb_path in notebooks:
        slug = notebook_slug(nb_path)
        display = notebook_display(nb_path)
        size_kb = nb_path.stat().st_size // 1024

        slug_dir = nb_dir / slug
        slug_dir.mkdir(exist_ok=True)

        (slug_dir / "notebook_content.html").write_text(
            _scrub_username(nb_path.read_text())
        )

        nb_styles, nb_body = _inline_notebook(nb_path)

        back = '← All notebooks' if len(notebooks) > 1 else '← Home'
        back_href = '../' if len(notebooks) > 1 else '../../index.html'
        bar = f"""
    <div class="flex items-center justify-between px-6 py-3 bg-white border-b border-slate-200 sticky top-0 z-10 shadow-sm">
      <div class="flex items-center gap-3">
        <a href="{back_href}" class="text-xs text-slate-400 hover:text-slate-700 transition-colors">{back}</a>
        <span class="text-slate-300">|</span>
        <span class="font-semibold text-slate-800">{esc(display)}</span>
        <span class="text-slate-400 text-xs">· {size_kb} KB</span>
      </div>
      <a href="notebook_content.html" target="_blank" rel="noopener"
         class="text-xs text-indigo-600 hover:text-indigo-800 font-medium transition-colors">
        Open full screen ↗
      </a>
    </div>"""

        body = f"{bar}\n<div class='nb-inline'>{nb_body}</div>"
        (slug_dir / "index.html").write_text(page(
            display, body, "notebook",
            depth=2,
            extra_head=nb_styles,
            main_class="w-full flex-1 p-0",
        ))
        print(f"  notebook/{slug}/index.html")

    # ── Listing / index page ───────────────────────────────────────────────
    if not notebooks:
        body = """
    <div class="text-center py-20 text-slate-400">
      <p class="text-4xl mb-4">📓</p>
      <p class="font-medium">No notebooks rendered yet.</p>
      <p class="text-sm mt-1">Run <code class="bg-slate-100 px-2 py-0.5 rounded text-slate-700">just notebook</code> to build them.</p>
    </div>"""
    else:
        cards = ""
        for nb_path in notebooks:
            slug = notebook_slug(nb_path)
            display = notebook_display(nb_path)
            size_kb = nb_path.stat().st_size // 1024
            mtime = datetime.fromtimestamp(nb_path.stat().st_mtime).strftime("%b %d, %Y")
            cards += f"""
        <a href="{slug}/" class="block bg-white rounded-xl border border-slate-200 p-5 shadow-sm
                  hover:border-indigo-400 hover:shadow-md transition-all group">
          <div class="flex items-start justify-between mb-2">
            <h3 class="font-semibold text-slate-900 group-hover:text-indigo-700 transition-colors">
              {esc(display)}
            </h3>
            <span class="text-xs text-slate-400 ml-3 flex-shrink-0">{size_kb} KB</span>
          </div>
          <p class="text-xs text-slate-400">Last rendered {mtime}</p>
          <p class="text-xs text-indigo-500 mt-2 group-hover:underline">View notebook →</p>
        </a>"""
        body = f"""
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-slate-900">Notebooks</h1>
      <p class="text-slate-500 text-sm mt-1">
        {len(notebooks)} rendered notebook{'s' if len(notebooks) != 1 else ''} —
        any <code class="bg-slate-100 px-1 rounded text-xs">notebooks/*.html</code> file is picked up automatically.
      </p>
    </div>
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">{cards}</div>"""

    (nb_dir / "index.html").write_text(page("Notebooks", body, "notebook"))
    print("  notebook/index.html")


# ── Data browser ───────────────────────────────────────────────────────────

def csv_table(path: Path, max_rows: int = 12) -> str:
    try:
        with open(path) as f:
            reader = csv.DictReader(f)
            all_cols = reader.fieldnames or []
            show_cols = [c for c in PREVIEW_COLS if c in all_cols]
            if not show_cols:
                show_cols = all_cols[:8]
            rows = [
                {c: r.get(c, "") for c in show_cols}
                for r in list(reader)[:max_rows]
            ]
        header = "".join(
            f'<th class="px-3 py-2 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide whitespace-nowrap">'
            f'{esc(c.replace("_", " "))}</th>'
            for c in show_cols
        )
        body_rows = ""
        for i, row in enumerate(rows):
            bg = "bg-white" if i % 2 == 0 else "bg-slate-50"
            cells = "".join(
                f'<td class="px-3 py-2 text-sm text-slate-700 whitespace-nowrap max-w-[200px] truncate">'
                f'{esc(str(row[c])[:80])}</td>'
                for c in show_cols
            )
            body_rows += f'<tr class="{bg}">{cells}</tr>'
        return f"""<div class="overflow-x-auto rounded-xl border border-slate-200 shadow-sm">
  <table class="min-w-full divide-y divide-slate-200">
    <thead class="bg-slate-50"><tr>{header}</tr></thead>
    <tbody class="divide-y divide-slate-100">{body_rows}</tbody>
  </table>
</div>"""
    except Exception as e:
        return f'<p class="text-red-500 text-sm">Could not preview CSV: {esc(str(e))}</p>'


def _dl_icon() -> str:
    return (
        '<svg class="w-3 h-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" '
        'stroke="currentColor" stroke-width="2.5">'
        '<path stroke-linecap="round" stroke-linejoin="round" '
        'd="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>'
        '</svg>'
    )


def _table_preview(path: Path, max_rows: int = 10) -> str:
    """Render an HTML preview of an arbitrary CSV (any columns, not just FEC-shaped)."""
    try:
        with open(path) as f:
            reader = csv.reader(f)
            rows = list(reader)
        if not rows:
            return '<p class="text-slate-400 text-sm">empty</p>'
        head, body = rows[0], rows[1 : max_rows + 1]
        th = "".join(
            f'<th class="px-3 py-2 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide whitespace-nowrap">'
            f'{esc(c)}</th>' for c in head
        )
        tr = ""
        for i, r in enumerate(body):
            bg = "bg-white" if i % 2 == 0 else "bg-slate-50"
            cells = "".join(
                f'<td class="px-3 py-2 text-sm text-slate-700 whitespace-nowrap max-w-[220px] truncate">'
                f'{esc(str(c)[:80])}</td>' for c in r
            )
            tr += f'<tr class="{bg}">{cells}</tr>'
        return f"""<div class="overflow-x-auto rounded-xl border border-slate-200 shadow-sm">
  <table class="min-w-full divide-y divide-slate-200">
    <thead class="bg-slate-50"><tr>{th}</tr></thead>
    <tbody class="divide-y divide-slate-100">{tr}</tbody>
  </table>
</div>"""
    except Exception as e:
        return f'<p class="text-red-500 text-sm">preview failed: {esc(str(e))}</p>'


def _generated_tables_section() -> str:
    """SAS-parity tables produced by the cross-company notebook, dropped under output/tables/."""
    if not OUT_TABLES.exists():
        return ""
    tables = sorted(p for p in OUT_TABLES.iterdir() if p.suffix in {".csv", ".xlsx"})
    if not tables:
        return ""
    dest = DOCS / "data" / "tables"
    dest.mkdir(parents=True, exist_ok=True)
    blocks = ""
    for src in tables:
        shutil.copy(src, dest / src.name)
        size_kb = src.stat().st_size // 1024
        preview = _table_preview(src) if src.suffix == ".csv" else (
            '<p class="text-xs text-slate-500">Excel workbook — download to inspect.</p>'
        )
        anchor = "tbl-" + src.stem.replace("_", "-")
        blocks += f"""
    <section id="{esc(anchor)}" class="mb-10 scroll-mt-10">
      <div class="flex items-center justify-between mb-3">
        <div>
          <h3 class="text-base font-bold text-slate-900 font-mono">{esc(src.name)}</h3>
          <p class="text-xs text-slate-400 mt-0.5">notebook-generated</p>
        </div>
        <a href="tables/{esc(src.name)}" download
           class="inline-flex items-center gap-1.5 text-xs bg-emerald-600 text-white
                  px-3 py-1.5 rounded-lg hover:bg-emerald-700 transition-colors">
          {_dl_icon()} Download ({size_kb} KB)
        </a>
      </div>
      {preview}
    </section>"""
    return f"""
    <div class="mt-12 pt-8 border-t border-slate-200">
      <h2 class="text-lg font-semibold text-slate-800 mb-1">Generated tables</h2>
      <p class="text-slate-500 text-sm mb-6">
        SAS-parity outputs written by
        <a href="../notebook/cross-company/" class="text-indigo-600 hover:underline">the cross-company notebook</a>
        — one row per employer for the contributors / contributions families plus
        contribution-level and contributor-level samples.
      </p>
      {blocks}
    </div>"""


def build_data(data_files: list[str]) -> None:
    data_dir = DOCS / "data"
    data_dir.mkdir(exist_ok=True)

    # Group by stem so CSV + JSON sit together, ordered by stem
    groups: dict[str, dict[str, str]] = {}
    for filename in sorted(data_files):
        stem = Path(filename).stem
        ext  = Path(filename).suffix.lstrip(".")
        if stem not in groups:
            groups[stem] = {}
        groups[stem][ext] = filename

    if not groups:
        body = """
    <div class="text-center py-20 text-slate-400">
      <p class="text-4xl mb-4">📂</p>
      <p class="font-medium">No data files found.</p>
      <p class="text-sm mt-1">Run <code class="bg-slate-100 px-2 py-0.5 rounded text-slate-700">just fetch</code> to download FEC data.</p>
    </div>"""
        (data_dir / "index.html").write_text(page("Data", body, "data"))
        print("  data/index.html")
        return

    # ── Sidebar ────────────────────────────────────────────────────────────
    sidebar_items = ""
    for stem, files in groups.items():
        anchor  = stem
        company = company_from_filename(stem)
        dl_links = ""
        if "csv" in files:
            dl_links += (
                f'<a href="{esc(files["csv"])}" download '
                f'class="inline-flex items-center gap-0.5 text-xs text-indigo-500 hover:text-indigo-700 transition-colors">'
                f'{_dl_icon()} csv</a>'
            )
        if "json" in files:
            dl_links += (
                f'<a href="{esc(files["json"])}" download '
                f'class="inline-flex items-center gap-0.5 text-xs text-slate-400 hover:text-slate-600 transition-colors">'
                f'{_dl_icon()} json</a>'
            )
        sidebar_items += (
            f'<div class="flex items-center justify-between gap-2 py-1">'
            f'<a href="#{esc(anchor)}" class="text-xs text-slate-600 hover:text-indigo-600 transition-colors truncate">'
            f'{esc(company.lower())}</a>'
            f'<div class="flex items-center gap-2 flex-shrink-0">{dl_links}</div>'
            f'</div>'
        )

    # ── Main sections ──────────────────────────────────────────────────────
    sections = ""
    for stem, files in groups.items():
        anchor  = stem
        company = company_from_filename(stem)
        csv_file  = files.get("csv")
        json_file = files.get("json")

        download_bar = ""
        if csv_file:
            csv_src  = OUT_SCHEDULE_A / csv_file
            csv_kb   = csv_src.stat().st_size // 1024 if csv_src.exists() else 0
            download_bar += (
                f'<a href="{esc(csv_file)}" download '
                f'class="inline-flex items-center gap-1.5 text-xs bg-indigo-600 text-white '
                f'px-3 py-1.5 rounded-lg hover:bg-indigo-700 transition-colors">'
                f'{_dl_icon()} CSV ({csv_kb} KB)</a>'
            )
        if json_file:
            json_src = OUT_SCHEDULE_A / json_file
            json_kb  = json_src.stat().st_size // 1024 if json_src.exists() else 0
            download_bar += (
                f'<a href="{esc(json_file)}" download '
                f'class="inline-flex items-center gap-1.5 text-xs bg-slate-600 text-white '
                f'px-3 py-1.5 rounded-lg hover:bg-slate-700 transition-colors">'
                f'{_dl_icon()} JSON ({json_kb} KB)</a>'
            )

        table_html = csv_table(OUT_SCHEDULE_A / csv_file) if csv_file else ""
        row_note   = f"Showing first 12 rows · {csv_kb} KB total" if csv_file else ""

        sections += f"""
    <section id="{esc(anchor)}" class="mb-12 scroll-mt-10">
      <div class="flex items-center justify-between mb-3">
        <div>
          <h2 class="text-base font-bold text-slate-900">{esc(company)}</h2>
          <p class="text-xs text-slate-400 font-mono mt-0.5">{esc(stem)}</p>
        </div>
        <div class="flex items-center gap-2">{download_bar}</div>
      </div>
      {table_html}
      {f'<p class="text-xs text-slate-400 mt-2">{esc(row_note)}</p>' if row_note else ""}
    </section>"""

    body = f"""
    <div class="flex gap-8">
      <aside class="hidden md:block w-52 flex-shrink-0">
        <div class="sticky top-6">
          <p class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Files</p>
          <div class="divide-y divide-slate-100">{sidebar_items}</div>
        </div>
      </aside>
      <div class="flex-1 min-w-0">
        <div class="mb-8">
          <h1 class="text-2xl font-bold text-slate-900">Data Files</h1>
          <p class="text-slate-500 text-sm mt-1">
            OpenFEC Schedule A contributions fetched via
            <code class="bg-slate-100 px-1 rounded text-xs">api-demo.py</code>.
            CSV previews show the {len(PREVIEW_COLS)} most useful columns.
          </p>
        </div>
        {sections}
        {_generated_tables_section()}
      </div>
    </div>"""

    (data_dir / "index.html").write_text(page("Data", body, "data"))
    print("  data/index.html")


# ── Source browser ─────────────────────────────────────────────────────────

def build_source() -> None:
    src_dir = DOCS / "source"
    src_dir.mkdir(exist_ok=True)

    file_sections = ""
    toc_items = ""

    for filename, lang, display in SOURCE_FILES:
        src_path = ROOT / filename
        if not src_path.exists():
            continue
        code = src_path.read_text()
        anchor = filename.replace(".", "-").replace("/", "-")
        line_count = code.count("\n")
        toc_items += f"""
      <a href="#{anchor}"
         class="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-slate-100 transition-colors text-sm">
        <span class="font-mono font-medium text-slate-800">{esc(display)}</span>
        <span class="text-xs text-slate-400">{line_count} lines</span>
      </a>"""
        file_sections += f"""
    <section id="{anchor}" class="mb-12 scroll-mt-8">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-base font-bold font-mono text-slate-900">{esc(display)}</h2>
        <span class="text-xs text-slate-400 bg-slate-100 px-2 py-1 rounded">{line_count} lines · {lang}</span>
      </div>
      <pre><code class="language-{lang}">{esc(code)}</code></pre>
    </section>"""

    body = f"""
    <div class="flex gap-8">
      <aside class="hidden md:block w-52 flex-shrink-0">
        <div class="sticky top-6">
          <p class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Files</p>
          <nav class="space-y-0.5">{toc_items}</nav>
        </div>
      </aside>
      <div class="flex-1 min-w-0">
        <div class="mb-8">
          <h1 class="text-2xl font-bold text-slate-900">Source Code</h1>
          <p class="text-slate-500 text-sm mt-1">
            Three Python scripts + a Justfile. Syntax highlighted via
            <a href="https://highlightjs.org/" target="_blank" rel="noopener" class="text-indigo-600 hover:underline">highlight.js</a>.
          </p>
        </div>
        {file_sections}
      </div>
    </div>"""

    (src_dir / "index.html").write_text(page("Source", body, "source"))
    print("  source/index.html")


# ── Design docs (Markdown → HTML) ──────────────────────────────────────────

def _markdown_to_html(md: str) -> str:
    """Render GFM-flavored markdown to HTML. Uses mistune (vendored by nbconvert)."""
    import mistune
    renderer = mistune.HTMLRenderer(escape=False)
    md_parser = mistune.create_markdown(
        renderer=renderer,
        plugins=["table", "url", "strikethrough", "task_lists"],
    )
    return md_parser(md)


def _postprocess_design_html(raw: str, depth: int = 2) -> str:
    """Convert fenced blocks and rewrite root-relative links for the page depth."""
    import re as _re, html as _html

    def _mermaid(m: "_re.Match[str]") -> str:
        return f'<div class="mermaid">{_html.unescape(m.group(1))}</div>'

    def _filetree(m: "_re.Match[str]") -> str:
        return f'<pre class="filetree">{_html.unescape(m.group(1))}</pre>'

    raw = _re.sub(
        r'<pre><code class="language-mermaid">(.*?)</code></pre>',
        _mermaid, raw, flags=_re.DOTALL,
    )
    raw = _re.sub(
        r'<pre><code class="language-tree">(.*?)</code></pre>',
        _filetree, raw, flags=_re.DOTALL,
    )
    # Rewrite root-relative links written as /path/ in markdown to correct
    # relative paths based on this page's depth (works locally and when served).
    prefix = "../" * depth
    raw = _re.sub(r'href="/((?!/)[^"]*)"', lambda m: f'href="{prefix}{m.group(1)}"', raw)
    return raw


def build_design() -> None:
    design_dir = DOCS / "design"
    design_dir.mkdir(exist_ok=True)

    toc = "".join(
        f'<a href="../{slug}/" class="block px-3 py-2 rounded-lg hover:bg-slate-100 transition-colors '
        f'text-sm font-medium text-slate-700">{esc(title)}</a>'
        for slug, title, _ in DESIGN_DOCS
    )

    for slug, title, src in DESIGN_DOCS:
        if not src.exists():
            print(f"  (skip design/{slug} — {src} missing)")
            continue
        page_dir = design_dir / slug
        page_dir.mkdir(exist_ok=True)
        depth = 2
        rendered = _postprocess_design_html(_markdown_to_html(src.read_text()), depth=depth)
        mermaid_head = (
            f'<script src="{MERMAID_JS}"></script>\n'
            f'<script>document.addEventListener("DOMContentLoaded", () => '
            f'mermaid.initialize({{ startOnLoad: true, theme: "neutral" }}));</script>'
        )
        body = f"""
    <div class="flex gap-8">
      <aside class="hidden md:block w-56 flex-shrink-0">
        <div class="sticky top-6">
          <p class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Design docs</p>
          <nav class="space-y-0.5">{toc}</nav>
        </div>
      </aside>
      <article class="prose flex-1 min-w-0 bg-white rounded-xl border border-slate-200 shadow-sm px-8 py-7">
        {rendered}
      </article>
    </div>"""
        (page_dir / "index.html").write_text(
            page(title, body, "design", depth=depth, extra_head=mermaid_head)
        )
        print(f"  design/{slug}/index.html")


# ── SQL extractor ──────────────────────────────────────────────────────────

_SQL_START = re.compile(r'^\s*(SELECT|WITH|INSERT|UPDATE|DELETE|CREATE|DROP)\b', re.IGNORECASE)
_SQL_STR   = re.compile(r'f?"""(.*?)"""|f?\'\'\'(.*?)\'\'\'', re.DOTALL)
_MD_STRIP  = re.compile(r'^#{1,6}\s*|\*\*|__|\*|_|`|\[([^\]]+)\]\([^)]+\)')
_BLANK_RE  = re.compile(r'\n{3,}')


def _extract_notebook_sql(nb_path: Path, comment_cap: int = 3) -> list[tuple[str, str]]:
    """Return (comment_header, sql) pairs extracted from a .ipynb file."""
    nb     = json.loads(nb_path.read_text())
    cells  = nb["cells"]
    result = []
    last_md = ""

    for cell in cells:
        src = "".join(cell["source"])
        if cell["cell_type"] == "markdown":
            last_md = src
            continue
        if cell["cell_type"] != "code":
            last_md = ""
            continue

        for m in _SQL_STR.finditer(src):
            sql = (m.group(1) or m.group(2) or "").strip()
            if not _SQL_START.match(sql):
                continue

            comment = ""
            if last_md:
                raw_lines = last_md.strip().splitlines()
                kept: list[str] = []
                for line in raw_lines:
                    clean = _MD_STRIP.sub(r"\1", line).strip()
                    if clean:
                        kept.append(f"-- {clean}")
                    if len(kept) >= comment_cap:
                        break
                comment = "\n".join(kept)

            result.append((comment, sql))
        last_md = ""

    return result


def build_sql(notebooks: list[Path]) -> None:
    sql_dir = DOCS / "sql"
    sql_dir.mkdir(exist_ok=True)

    toc_items     = ""
    nb_sections   = ""
    built_any     = False

    for nb_html in notebooks:
        slug    = notebook_slug(nb_html)
        display = notebook_display(nb_html)
        ipynb   = NOTEBOOKS_DIR / (nb_html.stem + ".ipynb")
        if not ipynb.exists():
            continue

        queries = _extract_notebook_sql(ipynb)
        if not queries:
            continue
        built_any = True

        # Assemble one SQL block with comment headers between queries
        parts: list[str] = []
        for header, sql in queries:
            if parts:
                parts.append("")          # blank line separator
            if header:
                parts.append(header)
            parts.append(_BLANK_RE.sub("\n\n", sql))
        sql_text = "\n".join(parts).strip()

        toc_items += (
            f'<a href="#{esc(slug)}" class="flex items-center justify-between '
            f'px-3 py-2 rounded-lg hover:bg-slate-100 transition-colors text-sm">'
            f'<span class="font-medium text-slate-800">{esc(display)}</span>'
            f'<span class="text-xs text-slate-400">{len(queries)}q</span></a>'
        )
        nb_sections += f"""
    <section id="{esc(slug)}" class="mb-12 scroll-mt-8">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-base font-bold text-slate-900">{esc(display)}</h2>
        <span class="text-xs text-slate-400 bg-slate-100 px-2 py-1 rounded">
          {len(queries)} quer{'y' if len(queries) == 1 else 'ies'}
        </span>
      </div>
      <pre><code class="language-sql">{esc(sql_text)}</code></pre>
    </section>"""

    if not built_any:
        body = """<div class="text-center py-20 text-slate-400">
          <p class="text-4xl mb-4">🗄️</p>
          <p class="font-medium">No SQL found in notebooks yet.</p>
        </div>"""
    else:
        body = f"""
    <div class="flex gap-8">
      <aside class="hidden md:block w-52 flex-shrink-0">
        <div class="sticky top-6">
          <p class="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Notebooks</p>
          <nav class="space-y-0.5">{toc_items}</nav>
        </div>
      </aside>
      <div class="flex-1 min-w-0">
        <div class="mb-8">
          <h1 class="text-2xl font-bold text-slate-900">SQL Queries</h1>
          <p class="text-slate-500 text-sm mt-1">
            DuckDB queries extracted from notebook sources.
            Section headers come from the preceding markdown cell (capped at {3} lines).
          </p>
        </div>
        {nb_sections}
      </div>
    </div>"""

    (sql_dir / "index.html").write_text(page("SQL", body, "sql"))
    print("  sql/index.html")


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"Building site → {DOCS}/")
    DOCS.mkdir(exist_ok=True)
    (DOCS / "charts").mkdir(exist_ok=True)
    (DOCS / "data").mkdir(exist_ok=True)

    # Copy charts
    charts: list[str] = []
    if OUT_CHARTS.exists():
        for png in sorted(OUT_CHARTS.glob("*.png")):
            shutil.copy(png, DOCS / "charts" / png.name)
            charts.append(png.name)
            print(f"  charts/{png.name}")

    # Copy schedule_a data files
    data_files: list[str] = []
    if OUT_SCHEDULE_A.exists():
        for f in sorted(OUT_SCHEDULE_A.iterdir()):
            if f.suffix in {".csv", ".json"}:
                shutil.copy(f, DOCS / "data" / f.name)
                data_files.append(f.name)
                print(f"  data/{f.name}")

    notebooks = find_notebooks()
    for nb in notebooks:
        print(f"  notebooks/{nb.name}")

    build_index(charts, data_files, notebooks)
    build_notebooks(notebooks)
    build_design()
    build_data(data_files)
    build_source()
    build_sql(notebooks)
    print(f"\nDone. {sum(1 for _ in DOCS.rglob('*.html'))} HTML files generated.")


if __name__ == "__main__":
    main()
