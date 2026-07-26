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
import sys
from pathlib import Path

from platao import __version__
from platao.checks import PROJECT_REGISTRY, REGISTRY
from platao.engine import analyze_paths
from platao.report import render

# Lower rank = more severe. A finding fails the run when its rank <= the threshold's rank.
_RANK = {"high": 0, "medium": 1, "low": 2, "never": 99}


def _audit(args: argparse.Namespace) -> int:
    root = Path(args.root) if args.root else Path.cwd()
    findings = analyze_paths([Path(p) for p in args.paths], root=root)

    if args.json:
        print(json.dumps([f.to_dict() for f in findings], indent=2, ensure_ascii=False))
    else:
        print(render(findings, color=False if args.no_color else None))

    threshold = _RANK[args.fail_on]
    worst = min((_RANK[f.severity.value] for f in findings), default=99)
    return 1 if worst <= threshold else 0


def _list_checks() -> int:
    for chk in sorted(REGISTRY.values(), key=lambda c: (c.category, c.id)):
        scope = "  (test-only)" if chk.test_only else ""
        print(f"{chk.severity.value:<6} {chk.category:<12} {chk.id}{scope}")
    for chk in sorted(PROJECT_REGISTRY.values(), key=lambda c: (c.category, c.id)):
        print(f"{chk.severity.value:<6} {chk.category:<12} {chk.id}  (project-wide)")
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

    args = parser.parse_args(argv)
    if args.cmd == "list-checks":
        return _list_checks()
    return _audit(args)


if __name__ == "__main__":
    sys.exit(main())
