"""Proof for `platao install-hook`."""
from __future__ import annotations

import subprocess
from pathlib import Path


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def _git_hooks_dir(cwd: Path) -> Path:
    """Where git itself will look for hooks from ``cwd`` (the ground truth the hook must land in)."""
    return (cwd / _git("rev-parse", "--git-path", "hooks", cwd=cwd).strip()).resolve()


def test_install_hook_creates_pre_commit(tmp_path: Path, monkeypatch):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    monkeypatch.chdir(tmp_path)
    from platao.cli import main
    assert main(["install-hook"]) == 0
    hook = tmp_path / ".git" / "hooks" / "pre-commit"
    assert hook.is_file()
    assert "platao pre-commit" in hook.read_text(encoding="utf-8")
    assert "platao check" in hook.read_text(encoding="utf-8")


def test_install_hook_respects_core_hooks_path(tmp_path: Path, monkeypatch):
    # With `core.hooksPath` set (husky, shared hook dirs) git never reads `.git/hooks` — a hook
    # written there is installed-but-dead, the exact placebo this tool exists to catch.
    _git("init", cwd=tmp_path)
    _git("config", "core.hooksPath", ".githooks", cwd=tmp_path)
    monkeypatch.chdir(tmp_path)
    from platao.cli import main
    assert main(["install-hook"]) == 0
    assert (_git_hooks_dir(tmp_path) / "pre-commit").is_file()
    assert (tmp_path / ".githooks" / "pre-commit").is_file()


def test_install_hook_from_a_linked_worktree_lands_where_git_reads_it(tmp_path: Path, monkeypatch):
    # In a linked worktree `--git-dir` is `.git/worktrees/<name>`, whose `hooks/` git ignores; hooks
    # live in the common dir. The installed hook must be the one git will actually run.
    repo, wt = tmp_path / "repo", tmp_path / "wt"
    repo.mkdir()
    _git("init", cwd=repo)
    _git("-c", "user.name=t", "-c", "user.email=t@example.invalid",
         "commit", "--allow-empty", "-m", "init", cwd=repo)
    _git("worktree", "add", str(wt), cwd=repo)
    monkeypatch.chdir(wt)
    from platao.cli import main
    assert main(["install-hook"]) == 0
    assert (_git_hooks_dir(wt) / "pre-commit").is_file()
