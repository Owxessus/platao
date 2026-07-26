"""treesitter — the deep, multi-language layer (optional extra: ``pip install 'platao[deep]'``).

The regex ``polyglot`` layer catches the universal *shallow* smells in any language. This layer goes
*deep* in the languages tree-sitter can parse: a real AST, so it can answer structural questions the
regex can't — starting with ``not_stub`` (an action-named function whose body is genuinely empty,
across JS/TS/Go/Ruby/Java/…). It's the foundation of full per-language deep analysis; more checks slot
in as tree-sitter queries beside this one.

Optional by design — tree-sitter is a C-extension dependency, so the core stays zero-dep. If the
extra isn't installed the engine falls back to the polyglot layer; if it is, these deeper checks turn
on automatically. tree-sitter is only imported inside the functions, so importing this module is free.
"""

from __future__ import annotations

import re
from pathlib import Path

from platao.checks._ast import ACTION_VERBS
from platao.finding import Finding, Severity

# File extension → tree-sitter language name (as `tree_sitter_language_pack` knows it).
_EXT_TO_LANG: dict[str, str] = {
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "tsx", ".go": "go", ".rb": "ruby", ".java": "java",
    ".cs": "c_sharp", ".rs": "rust", ".php": "php", ".kt": "kotlin", ".swift": "swift",
    ".scala": "scala", ".dart": "dart",
}

# The node types that are function/method definitions, per language.
_FUNC_TYPES: dict[str, set[str]] = {
    "javascript": {"function_declaration", "function_expression", "method_definition",
                   "generator_function_declaration"},
    "typescript": {"function_declaration", "function_expression", "method_definition",
                   "generator_function_declaration"},
    "tsx": {"function_declaration", "function_expression", "method_definition",
            "generator_function_declaration"},
    "go": {"function_declaration", "method_declaration"},
    "ruby": {"method", "singleton_method"},
    "java": {"method_declaration"},
    "c_sharp": {"method_declaration", "local_function_statement"},
    "rust": {"function_item"},
    "php": {"method_declaration", "function_definition"},
    "kotlin": {"function_declaration"},
    "swift": {"function_declaration"},
    "scala": {"function_definition"},
    "dart": {"function_signature", "method_signature", "function_declaration"},
}

# Languages where an empty function simply has no body node at all (vs. an empty block). Elsewhere a
# missing body means a declaration/abstract method — honest, not a stub — so we don't flag it.
_NONE_BODY_MEANS_EMPTY = {"ruby"}


def available() -> bool:
    """Is the optional ``tree-sitter-language-pack`` dependency installed?"""
    try:
        import tree_sitter_language_pack  # noqa: F401
    except ImportError:
        return False
    return True


def _is_action(name: str) -> bool:
    """Does the function name promise a side effect? Splits snake_case *and* camelCase."""
    return any(tok.lower() in ACTION_VERBS for tok in re.findall(r"[A-Za-z][a-z]*", name))


def scan(path: str, source: str) -> list[Finding]:
    """Deep-scan one non-Python file for stub functions via tree-sitter. Empty if unsupported/unparseable."""
    lang = _EXT_TO_LANG.get(Path(path).suffix.lower())
    if lang is None:
        return []
    try:
        from tree_sitter_language_pack import get_parser

        parser = get_parser(lang)
        tree = parser.parse(source.encode("utf-8"))
    except Exception:  # noqa: BLE001 — a grammar/parse failure just means "no deep findings here"
        return []

    func_types = _FUNC_TYPES.get(lang, set())
    none_body_empty = lang in _NONE_BODY_MEANS_EMPTY
    out: list[Finding] = []
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.type in func_types:
            name_node = node.child_by_field_name("name")
            body_node = node.child_by_field_name("body")
            name = (name_node.text or b"").decode("utf-8", "ignore") if name_node is not None else ""
            is_empty = (
                body_node.named_child_count == 0 if body_node is not None
                else none_body_empty
            )
            if name and is_empty and _is_action(name):
                out.append(Finding(
                    "not_stub", "placebo", Severity.HIGH, path, node.start_point[0] + 1,
                    f"'{name}' has an empty body — the announced action does nothing",
                ))
        stack.extend(node.children)
    out.sort(key=lambda f: f.sort_key)
    return out
