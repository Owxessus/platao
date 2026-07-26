"""Proof for `platao install-hook`."""
from __future__ import annotations

import subprocess
from pathlib import Path


def test_install_hook_creates_pre_commit(tmp_path: Path, monkeypatch):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    monkeypatch.chdir(tmp_path)
    from platao.cli import main
    assert main(["install-hook"]) == 0
    hook = tmp_path / ".git" / "hooks" / "pre-commit"
    assert hook.is_file()
    assert "platao pre-commit" in hook.read_text(encoding="utf-8")
    assert "platao check" in hook.read_text(encoding="utf-8")
