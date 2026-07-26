"""Engine-level behavior: parse errors, ordering, enable-filtering, and self-audit."""

from __future__ import annotations

from pathlib import Path

from platao import Severity, analyze_paths, analyze_source
from platao.engine import check_payload


def test_parse_error_is_reported_not_raised():
    findings = analyze_source("broken.py", "def (:\n")
    assert len(findings) == 1
    assert findings[0].check_id == "parse_error"


def test_findings_are_sorted_most_severe_first():
    src = (
        "def execute():\n"       # not_stub -> HIGH
        "    pass\n"
        "x = 1  # TODO later\n"  # debt_tracked -> LOW
    )
    findings = analyze_source("module.py", src)
    severities = [f.severity for f in findings]
    assert severities == sorted(severities, key=lambda s: {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}[s])
    assert findings[0].severity is Severity.HIGH


def test_enabled_filter_restricts_checks():
    src = "def execute():\n    pass\nx = 1  # TODO later\n"
    findings = analyze_source("module.py", src, enabled={"not_stub"})
    assert {f.check_id for f in findings} == {"not_stub"}


def test_findings_carry_snippet_and_line():
    findings = analyze_source("module.py", "def execute():\n    pass\n")
    stub = next(f for f in findings if f.check_id == "not_stub")
    assert stub.line == 1
    assert "def execute" in stub.snippet


def test_check_payload_flags_and_summarizes(tmp_path: Path):
    (tmp_path / "m.py").write_text("def execute():\n    pass\n", encoding="utf-8")
    payload = check_payload([tmp_path], root=tmp_path, fail_on="high")
    assert payload["ok"] is False
    assert payload["summary"]["high"] >= 1
    assert any(f["check_id"] == "not_stub" for f in payload["findings"])


def test_check_payload_ok_when_clean(tmp_path: Path):
    (tmp_path / "m.py").write_text(
        "def parse():\n    return compute()\nif __name__ == '__main__':\n    parse()\n",
        encoding="utf-8",
    )
    payload = check_payload([tmp_path], root=tmp_path)
    assert payload["ok"] is True
    assert payload["summary"] == {"high": 0, "medium": 0, "low": 0}
    assert payload["findings"] == []


def test_platao_is_clean_on_its_own_source():
    """The auditor must survive its own audit — no findings on the shipped package (dogfooding)."""
    src_dir = Path(__file__).resolve().parent.parent / "src" / "platao"
    findings = analyze_paths([src_dir], root=src_dir.parent)
    assert findings == [], "Platão flags its own code:\n" + "\n".join(
        f"  {f.path}:{f.line} [{f.check_id}] {f.message}" for f in findings
    )
