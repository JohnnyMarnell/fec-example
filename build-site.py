#!/usr/bin/env python3
"""Build static GitHub Pages site from FEC project outputs.

Run:  python build-site.py
Out:  docs/   (configure GitHub Pages → main branch → /docs folder)
"""
import csv
import html as html_mod
import json
import shutil
from datetime import datetime
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
DOCS = ROOT / "docs"
OUT_CHARTS = ROOT / "output" / "charts"
OUT_SCHEDULE_A = ROOT / "output" / "schedule_a"
NOTEBOOK_HTML = ROOT / "notebooks" / "analysis.html"

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

HLJS_CSS = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.10.0/styles/github.min.css"
HLJS_JS  = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.10.0/highlight.min.js"
TAILWIND = "https://cdn.tailwindcss.com"


# ── Helpers ────────────────────────────────────────────────────────────────

def esc(s: str) -> str:
    return html_mod.escape(str(s))


def nav(active: str, depth: int) -> str:
    b = "../" * depth
    items = {
        "home":     (f"{b}index.html",         "Home"),
        "notebook": (f"{b}notebook/",           "Notebook"),
        "data":     (f"{b}data/",               "Data"),
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
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; }}
    .badge-d {{ background: #dbeafe; color: #1d4ed8; }}
    .badge-r {{ background: #fee2e2; color: #b91c1c; }}
    .badge-n {{ background: #f3f4f6; color: #6b7280; }}
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
        <p class="text-slate-400 text-xs mt-0.5">OpenFEC · Political contribution explorer · Tractor Supply Co.</p>
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

def build_index(charts: list[str], data_files: list[str]) -> None:
    # Quick stats from CSV
    stats_html = ""
    csvs = [f for f in data_files if f.endswith(".csv")]
    if csvs:
        csv_path = OUT_SCHEDULE_A / csvs[0]
        try:
            with open(csv_path) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            total = len(rows)
            total_amt = sum(float(r.get("contribution_receipt_amount", 0) or 0) for r in rows)
            employers = set(r.get("contributor_employer", "") for r in rows)
            states = set(r.get("contributor_state", "") for r in rows if r.get("contributor_state"))
            stats_html = f"""
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
          {stat_card("Contributions", f"{total:,}", "API records fetched (2 pages)")}
          {stat_card("Total Amount", f"${total_amt:,.0f}", "Sum of contribution amounts")}
          {stat_card("Unique Employers", f"{len(employers):,}", "Distinct employer strings")}
          {stat_card("States", f"{len(states)}", "Contributor states represented")}
        </div>"""
        except Exception:
            pass

    chart_imgs = ""
    for chart in sorted(charts):
        chart_imgs += f"""
      <figure class="rounded-xl overflow-hidden border border-slate-200 shadow-sm bg-white">
        <img src="charts/{esc(chart)}" alt="Party breakdown chart"
             class="w-full object-contain max-h-[420px]">
        <figcaption class="text-xs text-slate-500 text-center py-2 bg-slate-50 border-t border-slate-100">
          {esc(chart.replace("_party_breakdown.png", "").replace("_", " "))} · party breakdown by 60% rule
        </figcaption>
      </figure>"""

    quick_links = f"""
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-12">
        {link_card("notebook/", "Notebook", "Full Jupyter analysis with charts, data joins, and the 60% contributor classification rule.", "📓")}
        {link_card("data/",     "Data",     "Browse and download raw API output: Schedule A CSV and JSON files.", "📂")}
        {link_card("source/",   "Source",   "Syntax-highlighted Python source and Justfile build recipes.", "🔍")}
      </div>"""

    pipeline_html = """
      <section class="mb-12">
        <h2 class="text-lg font-semibold text-slate-800 mb-3">Pipeline</h2>
        <div class="bg-white rounded-xl border border-slate-200 p-5 shadow-sm font-mono text-sm text-slate-700 space-y-1">
          <div><span class="text-green-600 font-bold">just build</span>  <span class="text-slate-400"># fetch → analyze → notebook + HTML</span></div>
          <div class="pl-4 text-slate-500">↳ api-demo.py fetches OpenFEC Schedule A for TRACTOR SUPPLY (2019–2020)</div>
          <div class="pl-4 text-slate-500">↳ main.py joins party lookups (AllPacs, Aristotle), applies 60% rule</div>
          <div class="pl-4 text-slate-500">↳ notebooks/analysis.ipynb executes and renders to HTML</div>
          <div class="pl-4 text-slate-500">↳ output/charts/ and output/schedule_a/ written to disk</div>
        </div>
      </section>"""

    body = f"""
    <div class="mb-10">
      <h1 class="text-3xl font-bold text-slate-900 mb-2">Tractor Supply Co. · FEC Contributions</h1>
      <p class="text-slate-500 max-w-2xl">
        Fetches political contribution records from the
        <a href="https://api.open.fec.gov/" target="_blank" rel="noopener" class="text-indigo-600 hover:underline">OpenFEC API</a>,
        aggregates by contributor using the <strong>60% rule</strong> (assign a party if ≥60%
        of a person's total went to that party), and visualizes the breakdown.
      </p>
    </div>
    {quick_links}
    {stats_html}
    <section class="mb-12">
      <h2 class="text-lg font-semibold text-slate-800 mb-4">Results</h2>
      {"".join(f'<div class="mb-6">{chart_imgs}</div>') if chart_imgs else '<p class="text-slate-400 text-sm">No charts found — run <code>just build</code> first.</p>'}
    </section>
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


# ── Notebook ───────────────────────────────────────────────────────────────

def build_notebook() -> None:
    import re as _re
    nb_dir = DOCS / "notebook"
    nb_dir.mkdir(exist_ok=True)

    if NOTEBOOK_HTML.exists():
        # Keep standalone copy for full-screen link
        shutil.copy(NOTEBOOK_HTML, nb_dir / "notebook_content.html")

        raw = NOTEBOOK_HTML.read_text()
        head_end = raw.find("</head>")

        # Extract all <style> blocks from the notebook's <head> to inject into ours
        nb_styles = "\n".join(_re.findall(r"<style[^>]*>.*?</style>", raw[:head_end + 7], _re.DOTALL))

        # Extract <body ...>...</body> inner content
        body_match = _re.search(r"<body[^>]*>(.*)</body>", raw, _re.DOTALL)
        nb_body = body_match.group(1).strip() if body_match else "<p>Could not parse notebook.</p>"

        bar = """
    <div class="flex items-center justify-between px-6 py-3 bg-white border-b border-slate-200 sticky top-0 z-10 shadow-sm">
      <div>
        <span class="font-semibold text-slate-800">Jupyter Notebook</span>
        <span class="text-slate-400 text-xs ml-2">— full executed analysis</span>
      </div>
      <a href="notebook_content.html" target="_blank" rel="noopener"
         class="text-xs text-indigo-600 hover:text-indigo-800 font-medium transition-colors">
        Open full screen ↗
      </a>
    </div>"""

        body = f"{bar}\n<div class='nb-inline'>{nb_body}</div>"

        (nb_dir / "index.html").write_text(page(
            "Notebook", body, "notebook",
            extra_head=nb_styles,
            main_class="w-full flex-1 p-0",
        ))
    else:
        body = """
    <div class="text-center py-20 text-slate-400">
      <p class="text-4xl mb-4">📓</p>
      <p class="font-medium">Notebook not yet generated.</p>
      <p class="text-sm mt-1">Run <code class="bg-slate-100 px-2 py-0.5 rounded text-slate-700">just notebook</code> to build it.</p>
    </div>"""
        (nb_dir / "index.html").write_text(page("Notebook", body, "notebook"))

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


def build_data(data_files: list[str]) -> None:
    data_dir = DOCS / "data"
    data_dir.mkdir(exist_ok=True)

    sections = ""
    csvs   = sorted(f for f in data_files if f.endswith(".csv"))
    jsons  = sorted(f for f in data_files if f.endswith(".json"))
    others = sorted(f for f in data_files if not f.endswith(".csv") and not f.endswith(".json"))

    for filename in csvs:
        src = OUT_SCHEDULE_A / filename
        size_kb = src.stat().st_size // 1024 if src.exists() else 0
        sections += f"""
    <section class="mb-10">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-base font-semibold text-slate-800 font-mono">{esc(filename)}</h2>
        <a href="{esc(filename)}" download
           class="text-xs bg-indigo-600 text-white px-3 py-1.5 rounded-lg hover:bg-indigo-700 transition-colors">
          Download CSV ({size_kb} KB)
        </a>
      </div>
      {csv_table(src)}
      <p class="text-xs text-slate-400 mt-2">Showing first 12 rows · {size_kb} KB total</p>
    </section>"""

    for filename in jsons:
        src = OUT_SCHEDULE_A / filename
        size_kb = src.stat().st_size // 1024 if src.exists() else 0
        sections += f"""
    <section class="mb-8">
      <div class="flex items-center justify-between mb-2">
        <h2 class="text-base font-semibold text-slate-800 font-mono">{esc(filename)}</h2>
        <a href="{esc(filename)}" download
           class="text-xs bg-slate-600 text-white px-3 py-1.5 rounded-lg hover:bg-slate-700 transition-colors">
          Download JSON ({size_kb} KB)
        </a>
      </div>
      <p class="text-sm text-slate-500">Raw API response — same records as the CSV above, in OpenFEC format.</p>
    </section>"""

    if not sections:
        sections = """
    <div class="text-center py-20 text-slate-400">
      <p class="text-4xl mb-4">📂</p>
      <p class="font-medium">No data files found.</p>
      <p class="text-sm mt-1">Run <code class="bg-slate-100 px-2 py-0.5 rounded text-slate-700">just fetch</code> to download FEC data.</p>
    </div>"""

    body = f"""
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-slate-900">Data Files</h1>
      <p class="text-slate-500 text-sm mt-1">
        OpenFEC Schedule A contributions fetched via <code class="bg-slate-100 px-1 rounded text-xs">api-demo.py</code>.
        CSV previews show the {len(PREVIEW_COLS)} most useful columns.
      </p>
    </div>
    {sections}"""

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

    build_index(charts, data_files)
    build_notebook()
    build_data(data_files)
    build_source()
    print(f"\nDone. {sum(1 for _ in DOCS.rglob('*.html'))} HTML files generated.")


if __name__ == "__main__":
    main()
