"""Human-readable rendering of findings. The only module that knows about terminals and color.

Kept separate from the engine so the same findings can go to a terminal, a JSON payload, or an MCP
result without the analysis caring how it's shown.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from collections.abc import Sequence

from platao.finding import Finding, Severity

_MARK = {Severity.HIGH: "⚠", Severity.MEDIUM: "•", Severity.LOW: "·"}


def _color(text: str, code: str, on: bool) -> str:
    return f"\x1b[{code}m{text}\x1b[0m" if on else text


def render(findings: Sequence[Finding], *, color: bool | None = None) -> str:
    """Format findings for a terminal, grouped by file, most-severe-first, with a summary line.

    Args:
        findings: the findings to show.
        color: ``True``/``False`` to force; ``None`` auto-detects a TTY.
    """
    if color is None:
        color = sys.stdout.isatty()

    if not findings:
        return _color("✓ Platão: no concerns — nothing left unfinished that I can see.", "32", color)

    by_file: dict[str, list[Finding]] = defaultdict(list)
    for f in findings:
        by_file[f.path].append(f)

    lines: list[str] = []
    for path in sorted(by_file):
        lines.append(_color(f"Platão — {path}", "1", color))
        for f in sorted(by_file[path], key=lambda f: f.sort_key):
            head = f"  {_MARK[f.severity]} [{f.check_id}]"
            if f.severity is Severity.HIGH:
                head = _color(head, "31", color)
            lines.append(f"{head}  {f.message}")
            if f.snippet:
                lines.append(_color(f"        {f.line}: {f.snippet}", "2", color))
        lines.append("")

    counts = {s: sum(1 for f in findings if f.severity is s) for s in Severity}
    summary = (
        f"{counts[Severity.HIGH]} critical · "
        f"{counts[Severity.MEDIUM]} concern · "
        f"{counts[Severity.LOW]} note"
    )
    lines.append(_color(summary, "1", color))
    return "\n".join(lines).rstrip()
