"""The ``platao`` command.

Subcommands:
  * ``check <paths>``   — audit files/dirs, detailed output.
  * ``sweep <dir>``     — audit a whole tree (same engine; the name signals repo-wide intent).
  * ``list-checks``     — show what's registered.

Exit code: non-zero when a finding at or above ``--fail-on`` (default: ``high``) is present, so it
drops into CI and pre-commit as a gate. ``--json`` emits the machine-readable payload the MCP server
will reuse.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from pathlib import Path

from platao import __version__
from platao.checks import PROJECT_REGISTRY, REGISTRY
from platao.engine import analyze_paths
from platao.finding import RANK
from platao.report import render


def _audit(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else Path.cwd()
    findings = analyze_paths([Path(p) for p in args.paths], root=root)

    if getattr(args, "judge", False):
        findings = sorted([*findings, *_run_judgment(args, root)], key=lambda f: f.sort_key)

    if args.json:
        print(json.dumps([f.to_dict() for f in findings], indent=2, ensure_ascii=False))
    else:
        print(render(findings, color=False if args.no_color else None))

    # The gate is deterministic — judgment findings (an LLM's opinion) are advisory, not exit-driving.
    worst = min((RANK[f.severity.value] for f in findings if f.category != "judgment"), default=99)
    return 1 if worst <= RANK[args.fail_on] else 0


def _run_judgment(args: argparse.Namespace, root: Path):
    """Run the opt-in BYO-LLM layer over each audited file. Skips (with a note) if unconfigured."""
    from platao.judge import JudgeConfig, run_judgment

    config = JudgeConfig.from_env()
    if config is None:
        print(
            "judgment (--judge) needs BYO-LLM config: set PLATAO_JUDGE_MODEL and PLATAO_JUDGE_API_KEY "
            "(optionally PLATAO_JUDGE_BASE_URL). Skipping judgment.",
            file=sys.stderr,
        )
        return []

    from platao.engine import iter_python_files

    out = []
    seen: set[str] = set()
    for p in args.paths:
        for file in iter_python_files(Path(p)):
            real = str(file.resolve())
            if real in seen:
                continue
            seen.add(real)
            try:
                display = os.path.relpath(file, root).replace("\\", "/")
            except ValueError:
                display = str(file).replace("\\", "/")
            source = Path(file).read_text(encoding="utf-8", errors="ignore")
            out.extend(run_judgment(display, source, config))
    return out


def _run_mcp() -> int:
    try:
        from platao.mcp_server import run
    except ImportError:
        print(
            "The MCP server needs the optional extra:\n    pip install 'platao[mcp]'",
            file=sys.stderr,
        )
        return 2
    run()
    return 0


def _list_checks() -> int:
    from platao.polyglot import POLYGLOT_CHECKS

    for chk in sorted(REGISTRY.values(), key=lambda c: (c.category, c.id)):
        scope = "  (test-only)" if chk.test_only else "  (Python, AST)"
        print(f"{chk.severity.value:<6} {chk.category:<12} {chk.id}{scope}")
    for chk in sorted(PROJECT_REGISTRY.values(), key=lambda c: (c.category, c.id)):
        print(f"{chk.severity.value:<6} {chk.category:<12} {chk.id}  (Python, project-wide)")
    for chk in sorted(POLYGLOT_CHECKS, key=lambda c: (c.category, c.check_id)):
        print(f"{chk.severity.value:<6} {chk.category:<12} {chk.check_id}  (any language)")
    return 0


def _add_audit_args(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("paths", nargs="+", help="files or directories to audit")
    sp.add_argument("--root", help="repo root for relative display paths (default: cwd)")
    sp.add_argument("--json", action="store_true", help="machine-readable output")
    sp.add_argument("--no-color", action="store_true", help="disable ANSI color")
    sp.add_argument(
        "--fail-on",
        choices=["high", "medium", "low", "never"],
        default="high",
        help="minimum severity that makes the exit code non-zero (default: high)",
    )
    sp.add_argument(
        "--judge",
        action="store_true",
        help="also run the opt-in 'skeptical senior' LLM layer (BYO-LLM via PLATAO_JUDGE_*; "
             "advisory — does not affect the exit code)",
    )


def _force_utf8() -> None:
    """Emit UTF-8 regardless of the console codepage.

    Platão's output carries non-ASCII (marks, em-dashes, its own accented name). On a legacy Windows
    console (cp1252) that raises ``UnicodeEncodeError`` mid-print. Reconfiguring to UTF-8 makes every
    character encodable; modern terminals render it, legacy ones may show a wrong glyph — but never
    crash. A crash on output would be the worst kind of "looks done, isn't".
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            # contextlib.suppress states the intent — this is a deliberate best-effort, not a
            # dropped error (and, fittingly, it's what Platão's own swallowed_error check asks for).
            with contextlib.suppress(ValueError, OSError):
                reconfigure(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    _force_utf8()
    parser = argparse.ArgumentParser(
        prog="platao",
        description="Deterministic completeness auditor — it reads the AST, it doesn't guess.",
    )
    parser.add_argument("--version", action="version", version=f"platao {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    _add_audit_args(sub.add_parser("check", help="audit files or directories (detailed)"))
    _add_audit_args(sub.add_parser("sweep", help="audit a whole tree for placebo & unfinished work"))
    sub.add_parser("list-checks", help="show the registered checks")
    sub.add_parser("mcp", help="run the MCP server (stdio) — exposes Platão to agents")

    args = parser.parse_args(argv)
    if args.cmd == "list-checks":
        return _list_checks()
    if args.cmd == "mcp":
        return _run_mcp()
    return _audit(args)


if __name__ == "__main__":
    sys.exit(main())
