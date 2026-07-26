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


# ── declared no-op exemption (FP guard from gson @Override flush) ──────────────────

def test_java_override_noop_is_exempt():
    # `@Override public void flush() {}` — an intentional no-op impl of Flushable, not a placebo.
    src = "class W {\n  @Override\n  public void flush() {}\n}"
    assert "not_stub" not in ids(src, "W.java")


def test_java_plain_empty_action_still_caught():  # prove_effect — exemption didn't blind it
    assert "not_stub" in ids("class W {\n  public void deploy() {}\n}", "W.java")


def test_ts_override_modifier_noop_is_exempt():
    src = "class C extends B {\n  override save() {}\n}"
    assert "not_stub" not in ids(src, "app.ts")


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


# ── empty_test (JS/TS: it/test with no assertion) ─────────────────────────────────

def test_empty_test_no_assertion_is_caught():
    src = 'it("does a thing", () => {\n  const r = run();\n});'
    assert "empty_test" in ids(src, "x.test.ts")


def test_empty_test_empty_body_is_caught():
    assert "empty_test" in ids('test("todo", () => {});', "x.test.ts")


def test_test_with_expect_is_silent():  # negative control
    src = 'it("works", () => {\n  expect(run()).toBe(1);\n});'
    assert "empty_test" not in ids(src, "x.test.ts")


def test_test_with_assert_is_silent():
    src = 'test("works", () => {\n  assert.equal(run(), 1);\n});'
    assert "empty_test" not in ids(src, "x.test.ts")


def test_skipped_test_is_not_flagged():
    # it.skip / test.only are member calls, not `it(...)` — deliberately excluded.
    src = 'it.skip("later", () => {\n  const r = run();\n});'
    assert "empty_test" not in ids(src, "x.test.ts")


# ── Ruby empty rescue (swallowed_error via deep AST) ──────────────────────────────

def test_ruby_empty_bare_rescue_is_caught():
    assert "swallowed_error" in ids("begin\n  risky\nrescue\nend\n", "app.rb")


def test_ruby_empty_rescue_with_class_is_caught():
    assert "swallowed_error" in ids("def f\n  risky\nrescue StandardError\nend\n", "app.rb")


def test_ruby_handled_rescue_is_silent():  # negative control
    assert "swallowed_error" not in ids("begin\n  risky\nrescue => e\n  log(e)\nend\n", "app.rb")
