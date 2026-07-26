"""Proofs for the optional .platao.json config."""
from __future__ import annotations

import json
from pathlib import Path

from platao.config import Config


def test_no_config_disables_nothing(tmp_path: Path):
    assert Config.load(tmp_path).disable == set()


def test_disable_list_is_read(tmp_path: Path):
    (tmp_path / ".platao.json").write_text(json.dumps({"disable": ["debt_tracked", "not_stub"]}))
    assert Config.load(tmp_path).disable == {"debt_tracked", "not_stub"}


def test_malformed_config_degrades_to_default(tmp_path: Path):
    (tmp_path / ".platao.json").write_text("{ not valid json")
    assert Config.load(tmp_path).disable == set()


def test_disable_filters_findings_via_cli(tmp_path: Path):
    (tmp_path / "m.py").write_text("def execute():\n    pass\nx = 1  # TODO later\n")
    (tmp_path / ".platao.json").write_text(json.dumps({"disable": ["not_stub"]}))
    from platao.cli import main
    # exit 0 because the only HIGH (not_stub) is disabled; debt_tracked (low) remains
    rc = main(["check", str(tmp_path), "--no-color", "--root", str(tmp_path)])
    assert rc == 0
