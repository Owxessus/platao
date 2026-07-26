"""The engine: parse a file once, run every enabled check, return sorted findings.

This is the whole orchestration. It owns file walking, the skip list, syntax-error handling, and
nothing else — the checks own the judgment, the report owns the presentation. Deliberately small.
"""

from __future__ import annotations

import os
from pathlib import Path

from platao.checks import REGISTRY
from platao.context import FileContext
from platao.finding import Finding, Severity

_SKIP_DIRS = frozenset({
    ".git", "__pycache__", "node_modules", ".venv", "venv", "build", "dist",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", "site-packages",
})


def analyze_source(path: str, source: str, *, enabled: set[str] | None = None) -> list[Finding]:
    """Audit one in-memory source string. The core entry point — everything else calls this.

    Args:
        path: display path (also decides whether test-only checks run).
        source: the code.
        enabled: if given, only checks whose id is in this set run; ``None`` runs all.

    Returns:
        Findings, sorted most-severe-first. A syntax error yields a single ``parse_error`` finding
        rather than raising — auditing a broken file should report, not crash.
    """
    try:
        ctx = FileContext.from_source(path, source)
    except SyntaxError as exc:
        return [Finding("parse_error", "engine", Severity.LOW, path, exc.lineno or 1,
                        f"could not parse: {exc.msg}")]

    out: list[Finding] = []
    for check in REGISTRY.values():
        if enabled is not None and check.id not in enabled:
            continue
        if check.test_only and not ctx.is_test:
            continue
        out.extend(check.fn(ctx))
    out.sort(key=lambda f: f.sort_key)
    return out


def analyze_file(path: Path | str, *, display: str | None = None,
                 enabled: set[str] | None = None) -> list[Finding]:
    """Read and audit one file. Undecodable bytes are replaced rather than fatal."""
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    return analyze_source(display or str(path), text, enabled=enabled)


def iter_python_files(root: Path | str):
    """Yield ``.py`` files under ``root`` (or ``root`` itself if it is one), skipping vendored dirs."""
    root = Path(root)
    if root.is_file():
        if root.suffix == ".py":
            yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for name in filenames:
            if name.endswith(".py"):
                yield Path(dirpath) / name


def analyze_paths(paths, *, root: Path | str | None = None,
                  enabled: set[str] | None = None) -> list[Finding]:
    """Audit every ``.py`` file under each of ``paths`` (files or dirs), deduping by real path.

    Args:
        paths: iterable of files/directories.
        root: if given, findings' ``path`` is shown relative to it (forward-slashed).
        enabled: restrict to these check ids.
    """
    root_path = Path(root) if root else None
    seen: set[str] = set()
    out: list[Finding] = []
    for p in paths:
        for f in iter_python_files(p):
            real = str(f.resolve())
            if real in seen:
                continue
            seen.add(real)
            if root_path is not None:
                try:
                    display = os.path.relpath(f, root_path).replace("\\", "/")
                except ValueError:  # different drive on Windows
                    display = str(f).replace("\\", "/")
            else:
                display = str(f).replace("\\", "/")
            out.extend(analyze_file(f, display=display, enabled=enabled))
    out.sort(key=lambda f: f.sort_key)
    return out
