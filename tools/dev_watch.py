#!/usr/bin/env python3
"""HMR-style dev server for the FEC site.

Routes file changes to the cheapest action that still produces the right output:

    notebooks/*.ipynb       → render .html + rebuild site                (~5 s)
    docs-src/*.md           → rebuild site                               (<1 s)
    build-site.py           → rebuild site                               (<1 s)
    output/charts/*.png     → rebuild site                               (<1 s)
    output/tables/*         → rebuild site                               (<1 s)
    tools/build_cross_company_nb.py → regen ipynb → execute → render → build  (~30 s)
    fec_client.py           → re-execute notebook → render → build       (~30 s)
    main.py | api-demo.py   → rebuild site (not imported by notebooks)   (<1 s)

The browser auto-reloads on every `docs/` change via livereload's injected JS.

Run:
    just dev          # default port 8000
    just dev 8081     # custom port

Press Ctrl-C to stop.
"""
from __future__ import annotations

import argparse
import functools
import subprocess
import sys
import time
from pathlib import Path
from threading import Lock

from livereload import Server

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK_TIMEOUT_S = 300

_lock = Lock()  # avoid overlapping rebuilds when multiple files change at once


def _log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"\033[90m[{ts}]\033[0m {msg}", flush=True)


def _run(cmd: list[str], *, timeout: int = 120) -> bool:
    pretty = " ".join(cmd)
    _log(f"\033[2m$ {pretty}\033[0m")
    started = time.monotonic()
    try:
        result = subprocess.run(cmd, cwd=ROOT, timeout=timeout)
    except subprocess.TimeoutExpired:
        _log(f"\033[31m! timeout after {timeout}s\033[0m")
        return False
    elapsed = time.monotonic() - started
    if result.returncode != 0:
        _log(f"\033[31m! exit {result.returncode} in {elapsed:.1f}s\033[0m")
        return False
    _log(f"\033[32m✓ {elapsed:.1f}s\033[0m")
    return True


def _guarded(label: str):
    """Decorator: serialize hooks and print a labeled banner per invocation."""
    def wrap(fn):
        @functools.wraps(fn)
        def inner(*args, **kwargs):
            if not _lock.acquire(blocking=False):
                _log(f"\033[33m… {label} skipped (rebuild in progress)\033[0m")
                return
            try:
                _log(f"\033[36m→ {label}\033[0m")
                fn(*args, **kwargs)
            finally:
                _lock.release()
        return inner
    return wrap


# ── Build steps ─────────────────────────────────────────────────────────────

@_guarded("build site")
def build_site() -> None:
    _run(["uv", "run", "python", "build-site.py"])


def _render_html(nb: str) -> bool:
    return _run([
        "uv", "run", "jupyter", "nbconvert",
        "--to", "html", nb, "--output-dir", "notebooks/",
    ])


@_guarded("render notebook HTML")
def render_all_notebooks() -> None:
    for nb in sorted((ROOT / "notebooks").glob("*.ipynb")):
        if ".ipynb_checkpoints" in str(nb):
            continue
        _render_html(str(nb.relative_to(ROOT)))
    _run(["uv", "run", "python", "build-site.py"])


def _make_html_only(nb_rel: str):
    @_guarded(f"render {nb_rel} → HTML")
    def inner():
        if _render_html(nb_rel):
            _run(["uv", "run", "python", "build-site.py"])
    return inner


@_guarded("re-execute + render cross-company")
def execute_cross_company() -> None:
    nb = "notebooks/cross-company.ipynb"
    if not _run(
        ["uv", "run", "jupyter", "nbconvert",
         "--to", "notebook", "--execute", "--inplace", nb],
        timeout=NOTEBOOK_TIMEOUT_S,
    ):
        return
    if _render_html(nb):
        _run(["uv", "run", "python", "build-site.py"])


@_guarded("regenerate cross-company.ipynb from builder")
def regen_cross_company() -> None:
    if not _run(["uv", "run", "python", "tools/build_cross_company_nb.py"]):
        return
    # Builder rewrites the .ipynb without outputs → must execute before rendering.
    nb = "notebooks/cross-company.ipynb"
    if not _run(
        ["uv", "run", "jupyter", "nbconvert",
         "--to", "notebook", "--execute", "--inplace", nb],
        timeout=NOTEBOOK_TIMEOUT_S,
    ):
        return
    if _render_html(nb):
        _run(["uv", "run", "python", "build-site.py"])


# ── Server ─────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("port", nargs="?", type=int, default=8000)
    p.add_argument("--no-initial-build", action="store_true",
                   help="Skip the initial build-site run on startup.")
    args = p.parse_args()

    if not args.no_initial_build:
        _log("\033[36m→ initial build\033[0m")
        _run(["uv", "run", "python", "build-site.py"])

    server = Server()

    # Site-only rebuilds (cheap, <1s) ──────────────────────────────────────
    server.watch("build-site.py",         build_site)
    server.watch("docs-src/*.md",         build_site)
    server.watch("output/charts/*.png",   build_site)
    server.watch("output/tables/*",       build_site)
    server.watch("main.py",               build_site)   # not imported by notebooks
    server.watch("api-demo.py",           build_site)

    # Render notebook HTML on .ipynb change (~5s) ──────────────────────────
    for nb in sorted((ROOT / "notebooks").glob("*.ipynb")):
        if ".ipynb_checkpoints" in str(nb):
            continue
        rel = str(nb.relative_to(ROOT))
        server.watch(rel, _make_html_only(rel))

    # Builder change → regen + re-execute + render (~30s) ──────────────────
    server.watch("tools/build_cross_company_nb.py", regen_cross_company)

    # Source code change that *does* affect notebook output → re-execute ───
    server.watch("fec_client.py", execute_cross_company)

    _log(f"\033[1mserving http://127.0.0.1:{args.port}\033[0m  "
         f"\033[90m(Ctrl-C to stop)\033[0m")
    _log("\033[90mwatching: build-site.py · docs-src · notebooks · "
         "tools/build_cross_company_nb.py · fec_client.py · output\033[0m")
    try:
        server.serve(
            root="docs", port=args.port, host="127.0.0.1",
            open_url_delay=None, restart_delay=0,
        )
    except KeyboardInterrupt:
        _log("bye")
    return 0


if __name__ == "__main__":
    sys.exit(main())
