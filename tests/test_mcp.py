"""Proofs for the MCP tools. Skipped unless the optional 'mcp' extra is installed."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("mcp")
pytest.importorskip("pydantic")

from platao.mcp_server import CheckInput, platao_check, platao_list_checks  # noqa: E402


def test_platao_check_tool_flags_defects(tmp_path: Path):
    (tmp_path / "m.py").write_text("def execute():\n    pass\n", encoding="utf-8")
    result = platao_check(CheckInput(path=str(tmp_path)))
    assert result["ok"] is False
    assert any(f["check_id"] == "not_stub" for f in result["findings"])


def test_platao_check_tool_missing_path_raises():
    with pytest.raises(FileNotFoundError):
        platao_check(CheckInput(path="definitely/not/here_xyz"))


def test_platao_list_checks_tool():
    result = platao_list_checks()
    ids = {c["id"] for c in result["checks"]}
    assert {"not_stub", "unwired", "dangling_import"} <= ids
