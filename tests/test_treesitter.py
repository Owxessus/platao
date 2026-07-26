"""Proofs for the deep multi-language layer. Skipped unless the 'deep' extra is installed."""

from __future__ import annotations

import pytest

pytest.importorskip("tree_sitter_language_pack")

from platao.treesitter import scan  # noqa: E402


def ids(source: str, path: str) -> set[str]:
    return {f.check_id for f in scan(path, source)}


# ── TypeScript / JavaScript ───────────────────────────────────────────────────────

def test_empty_action_function_ts_is_caught():
    assert "not_stub" in ids("function saveUser() {}", "app.ts")


def test_camelcase_action_name_is_recognized():
    assert "not_stub" in ids("function handleClick() {}", "app.tsx")


def test_non_empty_function_is_silent():  # negative control
    assert "not_stub" not in ids("function saveUser() { db.write(); }", "app.ts")


def test_non_action_empty_function_is_silent():
    # `parse` doesn't promise a side effect — an empty body isn't a placebo.
    assert "not_stub" not in ids("function parse() {}", "app.ts")


def test_empty_method_in_class_is_caught():
    assert "not_stub" in ids("class C {\n  save() {}\n}", "app.ts")


# ── Go ────────────────────────────────────────────────────────────────────────────

def test_empty_action_function_go_is_caught():
    assert "not_stub" in ids("package main\nfunc Deploy() {}\n", "main.go")


def test_non_empty_go_is_silent():
    assert "not_stub" not in ids("package main\nfunc Deploy() { run() }\n", "main.go")


# ── Ruby ──────────────────────────────────────────────────────────────────────────

def test_empty_action_method_ruby_is_caught():
    assert "not_stub" in ids("def save\nend\n", "app.rb")


def test_non_empty_ruby_is_silent():
    assert "not_stub" not in ids("def save\n  persist!\nend\n", "app.rb")


# ── unsupported / robustness ──────────────────────────────────────────────────────

def test_unsupported_extension_returns_empty():
    assert scan("notes.txt", "function save() {}") == []
