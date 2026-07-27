# Changelog

All notable changes to Platão are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — first public cut

The completeness auditor, carved out of Athena to run standalone.

### Added

- **Deterministic floor ($0, offline, no LLM).** AST/static checks that read the
  syntax tree instead of guessing:
  - `not_stub` — an action-named function that returns success without doing the work
  - `swallowed_error` — an `except` that silently discards the error (empty body / bare `pass`)
  - `hardcoded_secret` — a literal that looks like a real credential
  - `dangling_import` — a `from .x import y` whose target doesn't exist (whole-repo pass)
  - `unwired` — a module nobody imports
  - `god_function` / `not_god_function` — a function past the size/stage threshold
  - `empty_test` / placebo-test detection — a test that runs the target and asserts nothing
  - `debt_tracked` — a `TODO` with no owner or issue reference
- **`platao check <file>`** — review a single file (the diff an agent just wrote).
- **`platao sweep <dir>`** — whole-repo pass for cross-file findings (dangling imports, dead modules, placebos).
- **Judgment ceiling (`--judge`, opt-in, BYO-LLM).** The skeptical-senior layer for
  what a tree can't see — a mock wearing a real face, an abstraction with no caller.
  Advisory only; never the gate.
- **MCP server (`platao-mcp`)** — the primary surface: a coding agent calls Platão
  after each chunk and can't claim "finished" while a completeness check is red.
- **Universal (polyglot) layer** — empty `catch`, `eval`, leftover debugger, untracked
  `TODO` matched robustly on JS/TS/Go/Ruby/PHP/Java and more, no parser required.
- **Optional deep layer (`platao[deep]`)** — real tree-sitter ASTs for `not_stub` and
  `empty_test` on non-Python languages.
- **CI gate** (`action.yml`) and **pre-commit hook**.
- **Sibling delegation** — with [Basanos](https://github.com/Owxessus/basanos) and/or
  [Socrates](https://github.com/Owxessus/socrates) installed, `ui_wired` and
  `capabilities_proven` fold into the same report.

### Hardened

- Every check ships with a `prove_effect` + `negative_control` pair; CI enforces both.
- Tuned on real codebases (10k–90k★): **15 classes of false positive eliminated**, each
  with a regression test. Notably robust handling of stdlib/compiled-submodule/generated
  names so `dangling_import` doesn't fire on legitimate optional or Cython imports.
