"""Sibling delegation — Platão pulls in its siblings as extra eyes, if they're installed.

Platão answers "did you finish?" for code. Two of its questions are really its siblings' expertise, so
when a sibling is present Platão delegates and folds the answer into the same report:

* **``capabilities_proven``** → **Socrates** (Python, imported in-process): every public capability
  should be named by a test; the ones that aren't are claims with no proof.
* **``ui_wired``** → **Basanos** (a Node CLI, shelled out to): every UI control should call a handler
  that exists and does something; dead/stub controls are broken buttons.

Both are **feature-detected and silent when absent** — no error, the question simply doesn't appear.
Both stay within Platão's promise: they read code, they never *run* your app (Socrates' dynamic
mutation testing is deliberately not delegated here — only its static capability-proof is).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Iterable

from platao.checks import project_check
from platao.finding import Finding, Severity
from platao.project import ProjectIndex


@project_check("capabilities_proven", "placebo", Severity.MEDIUM)
def capabilities_proven(index: ProjectIndex) -> Iterable[Finding]:
    """Public capabilities that no test names — delegated to Socrates when it's installed.

    Runs only over a scanned tree (it needs to see both your code and your tests), and only if
    ``socrates`` imports. Socrates' capability-proof is static (an AST scan), so this stays within
    Platão's "never runs your code" guarantee.
    """
    if not index.whole_project:
        return
    try:
        import socrates  # feature-detect the sibling; silent if not installed
    except ImportError:
        return
    for f in socrates.prove_claims(index.root):
        yield Finding(
            "capabilities_proven", "placebo", Severity.MEDIUM, f.path, f.lineno,
            f"public capability '{f.symbol}' is exposed but no test names it — a claim with no proof "
            f"(via Socrates)", "",
        )


@project_check("ui_wired", "connectivity", Severity.HIGH)
def ui_wired(index: ProjectIndex) -> Iterable[Finding]:
    """UI controls wired to handlers that exist and do something — delegated to Basanos when present.

    Basanos is a Node CLI, so this shells out to it (``basanos audit … --json``) only when it's on the
    PATH. Basanos reads the source and never launches your app, so Platão's guarantee holds. Silent if
    Basanos isn't installed, or if it errors (a missing sibling must never fail the run).
    """
    if not index.whole_project:
        return
    basanos = shutil.which("basanos")
    if basanos is None:
        return
    try:
        proc = subprocess.run(
            [basanos, "audit", str(index.root), "--json"],
            capture_output=True, text=True, timeout=120,
        )
        findings = json.loads(proc.stdout or "[]")
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError):
        return
    for item in findings if isinstance(findings, list) else []:
        verdict = item.get("verdict")
        if verdict not in ("DEAD", "STUB", "PLACEBO"):
            continue
        severity = Severity.HIGH if verdict == "DEAD" else Severity.MEDIUM
        yield Finding(
            "ui_wired", "connectivity", severity,
            str(item.get("file", "")).replace("\\", "/"), int(item.get("line", 1) or 1),
            f"{item.get('message', f'{verdict} control')} (via Basanos)", "",
        )
