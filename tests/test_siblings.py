"""Proofs for sibling delegation — Platão pulls in Socrates / Basanos when present, silent when not."""

from __future__ import annotations

import json
import sys
import types
from dataclasses import dataclass
from pathlib import Path

from platao import analyze_paths


def _pkg(root: Path, files: dict[str, str]) -> None:
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")


def _ids(root: Path) -> set[str]:
    return {f.check_id for f in analyze_paths([root], root=root)}


# ── capabilities_proven → Socrates (in-process import) ─────────────────────────────

def test_capabilities_proven_is_silent_without_socrates(tmp_path: Path, monkeypatch):
    monkeypatch.setitem(sys.modules, "socrates", None)  # force ImportError on `import socrates`
    _pkg(tmp_path, {"pkg/__init__.py": "", "pkg/lib.py": "def widget():\n    return 1\n"})
    assert "capabilities_proven" not in _ids(tmp_path)


def test_capabilities_proven_delegates_when_socrates_present(tmp_path: Path, monkeypatch):
    @dataclass
    class _CF:
        symbol: str
        path: str
        lineno: int

    fake = types.ModuleType("socrates")
    fake.prove_claims = lambda root: [_CF("widget", "pkg/lib.py", 1)]  # noqa: ARG005
    monkeypatch.setitem(sys.modules, "socrates", fake)
    _pkg(tmp_path, {"pkg/__init__.py": "", "pkg/lib.py": "def widget():\n    return 1\n"})
    assert "capabilities_proven" in _ids(tmp_path)


def test_capabilities_proven_ignores_an_unrelated_socrates(tmp_path: Path, monkeypatch):
    # PyPI's `socrates` is an unrelated static-site generator: `import socrates` succeeds but there is
    # no `prove_claims`. That is "sibling absent", not a crash of the whole sweep.
    monkeypatch.setitem(sys.modules, "socrates", types.ModuleType("socrates"))
    _pkg(tmp_path, {"pkg/__init__.py": "", "pkg/lib.py": "def widget():\n    return 1\n"})
    assert "capabilities_proven" not in _ids(tmp_path)


# ── ui_wired → Basanos (Node CLI, shelled out) ─────────────────────────────────────

def test_ui_wired_is_silent_without_basanos(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("platao.checks.siblings.shutil.which", lambda name: None)
    _pkg(tmp_path, {"pkg/__init__.py": "", "pkg/a.py": "def f():\n    return 1\n"})
    assert "ui_wired" not in _ids(tmp_path)


def test_ui_wired_delegates_to_basanos_when_present(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("platao.checks.siblings.shutil.which", lambda name: "/usr/bin/basanos")

    class _Proc:
        stdout = json.dumps([{"verdict": "DEAD", "file": "Cart.tsx", "line": 8,
                              "message": "onClick={checkout} — handler does not resolve"}])

    monkeypatch.setattr("platao.checks.siblings.subprocess.run", lambda *a, **k: _Proc())
    _pkg(tmp_path, {"pkg/__init__.py": "", "pkg/a.py": "def f():\n    return 1\n"})
    findings = [f for f in analyze_paths([tmp_path], root=tmp_path) if f.check_id == "ui_wired"]
    assert findings and findings[0].severity.value == "high"


def test_ui_wired_survives_broken_basanos_output(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("platao.checks.siblings.shutil.which", lambda name: "/usr/bin/basanos")

    class _Proc:
        stdout = "not json at all"

    monkeypatch.setattr("platao.checks.siblings.subprocess.run", lambda *a, **k: _Proc())
    _pkg(tmp_path, {"pkg/__init__.py": "", "pkg/a.py": "def f():\n    return 1\n"})
    assert "ui_wired" not in _ids(tmp_path)  # a broken sibling must never crash the run
