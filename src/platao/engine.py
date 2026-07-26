"""The engine: parse a file once, run every enabled check, return sorted findings.

This is the whole orchestration. It owns file walking, the skip list, syntax-error handling, and
nothing else — the checks own the judgment, the report owns the presentation. Deliberately small.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path

from platao.checks import PROJECT_REGISTRY, REGISTRY
from platao.context import FileContext
from platao.finding import Finding, Severity
from platao.project import build_index

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


def _display_path(path: Path, root: Path | None) -> str:
    """The path to show a finding under — relative to ``root`` when possible, always forward-slashed."""
    if root is not None:
        # suppress states the intent: on a cross-drive path (Windows) fall through to the absolute
        # form, rather than dropping an error. It's also what Platão's swallowed_error check asks for.
        with contextlib.suppress(ValueError):
            return os.path.relpath(path, root).replace("\\", "/")
    return str(path).replace("\\", "/")


def analyze_paths(paths, *, root: Path | str | None = None,
                  enabled: set[str] | None = None) -> list[Finding]:
    """Audit every ``.py`` file under each of ``paths``, per file *and* across the project graph.

    Each file gets the per-file checks; the whole set also feeds a :class:`ProjectIndex` so the
    project-wide checks (``unwired``, ``dangling_import``) can see connectivity a single file can't.

    Args:
        paths: iterable of files/directories.
        root: if given, findings' ``path`` is shown relative to it (forward-slashed).
        enabled: restrict to these check ids (applies to per-file and project checks alike).
    """
    root_path = Path(root) if root else None
    seen: set[str] = set()
    triples: list[tuple[Path, str, str]] = []
    out: list[Finding] = []

    for p in paths:
        for f in iter_python_files(p):
            real = str(f.resolve())
            if real in seen:
                continue
            seen.add(real)
            display = _display_path(f, root_path)
            source = Path(f).read_text(encoding="utf-8", errors="ignore")
            triples.append((f, display, source))
            out.extend(analyze_source(display, source, enabled=enabled))

    if triples:
        index = build_index(triples, root_path or Path.cwd())
        for pcheck in PROJECT_REGISTRY.values():
            if enabled is not None and pcheck.id not in enabled:
                continue
            out.extend(pcheck.fn(index))

    out.sort(key=lambda f: f.sort_key)
    return out
