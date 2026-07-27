"""Project-wide index: the graph a single file can't see.

Some questions are cross-file — "does anyone import this module?", "does this ``from x import y``
actually resolve?". Answering them needs the whole set of files at once, with real Python import-name
resolution (src-layouts, packages, relative imports). This module builds that index once; the
project checks in ``checks/project.py`` read it.

Import resolution is done properly (walking ``__init__.py`` boundaries to find the import root, and
resolving relative imports against each file's own package) rather than by string munging, so it
behaves on real repos instead of only flat ones.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from platao.context import _looks_like_test
from platao.finding import Finding, Severity


def module_name_of(path: Path) -> str | None:
    """The dotted import name of ``path`` (e.g. ``src/platao/checks/x.py`` -> ``platao.checks.x``).

    Found by walking up while a ``__init__.py`` exists — so the import root is the package boundary,
    not the repo root, and src-layouts resolve correctly. ``None`` for a package ``__init__`` sitting
    at the import root (nothing above it), which has no importable name of its own.
    """
    parts: list[str] = []
    if path.stem != "__init__":
        parts.append(path.stem)
    parent = path.parent
    while (parent / "__init__.py").exists():
        parts.append(parent.name)
        parent = parent.parent
    if not parts:
        return None
    return ".".join(reversed(parts))


def _package_of(module: str, is_pkg_init: bool) -> str:
    """The package that contains ``module`` (for resolving relative imports)."""
    if is_pkg_init:
        return module
    return module.rsplit(".", 1)[0] if "." in module else ""


def _has_main_guard(tree: ast.Module) -> bool:
    """Does the module have an ``if __name__ == "__main__":`` guard (i.e. it's an entry point)?"""
    for node in ast.walk(tree):
        if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
            continue
        if len(node.test.comparators) != 1:
            continue
        operands = [node.test.left, node.test.comparators[0]]
        has_name = any(isinstance(o, ast.Name) and o.id == "__name__" for o in operands)
        has_main = any(isinstance(o, ast.Constant) and o.value == "__main__" for o in operands)
        if has_name and has_main:
            return True
    return False


@dataclass(slots=True)
class ModuleInfo:
    """One indexed module, with everything the project checks need to reason about it."""

    path: Path
    display: str
    module: str
    is_test: bool
    is_pkg_init: bool
    is_entrypoint: bool
    imports: set[str] = field(default_factory=set)          # dotted targets any import touches
    from_imports: list[tuple[int, str, str]] = field(default_factory=list)  # (line, base_module, name)
    bound_names: set[str] = field(default_factory=set)      # top-level names this module exposes
    has_star_import: bool = False
    guarded_from_lines: set[int] = field(default_factory=set)  # `from … import` lines under try/except-ImportError
    lines: list[str] = field(default_factory=list)

    def snippet(self, line: int) -> str:
        idx = line - 1
        return self.lines[idx].strip()[:160] if 0 <= idx < len(self.lines) else ""


@dataclass(slots=True)
class ProjectIndex:
    """The whole set of modules, plus the union of every import target (for the "is X imported?" query)."""

    root: Path
    modules: dict[str, ModuleInfo]
    imported_targets: set[str]
    # True when a directory/tree was scanned. `unwired` needs this — over a single named file the
    # importer set is unknowable, so "nobody imports it" would be a false positive.
    whole_project: bool = True

    def finding(self, m: ModuleInfo, check_id: str, category: str, severity: Severity,
                line: int, message: str) -> Finding:
        return Finding(check_id, category, severity, m.display, line, message, m.snippet(line))


def _resolve_from_base(node: ast.ImportFrom, package: str) -> str:
    """Resolve the base module of a ``from ... import ...`` (handles relative imports)."""
    if node.level == 0:
        return node.module or ""
    parts = package.split(".") if package else []
    up = node.level - 1
    parts = parts[: len(parts) - up] if up <= len(parts) else []
    if node.module:
        parts = [*parts, node.module]
    return ".".join(parts)


def _index_one(path: Path, display: str, tree: ast.Module, source: str) -> ModuleInfo:
    module = module_name_of(path) or path.stem
    is_pkg_init = path.name == "__init__.py"
    info = ModuleInfo(
        path=path,
        display=display,
        module=module,
        is_test=_looks_like_test(display),
        is_pkg_init=is_pkg_init,
        is_entrypoint=_has_main_guard(tree) or _is_script_path(display),
        lines=source.splitlines(),
    )
    package = _package_of(module, is_pkg_init)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                info.imports.add(alias.name)
                info.bound_names.add((alias.asname or alias.name).split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_from_base(node, package)
            if base:
                info.imports.add(base)
            for alias in node.names:
                if alias.name == "*":
                    info.has_star_import = True
                    continue
                if base:
                    info.imports.add(f"{base}.{alias.name}")
                info.from_imports.append((node.lineno, base, alias.name))
                info.bound_names.add(alias.asname or alias.name)
    # Top-level definitions expose names too (for `dangling_import` re-export resolution).
    _collect_module_binds(tree.body, info.bound_names)
    _collect_guarded_from_lines(tree, info.guarded_from_lines)
    return info


_OPTIONAL_IMPORT_EXC = frozenset({
    "ImportError", "ModuleNotFoundError", "AttributeError", "Exception", "BaseException",
})


def _catches_import_error(handlers: list[ast.ExceptHandler]) -> bool:
    """True if any handler catches an import-ish error (or is a bare ``except:``)."""
    for h in handlers:
        if h.type is None:
            return True  # bare except swallows ImportError too
        names = h.type.elts if isinstance(h.type, ast.Tuple) else [h.type]
        if any(isinstance(n, ast.Name) and n.id in _OPTIONAL_IMPORT_EXC for n in names):
            return True
    return False


def _collect_guarded_from_lines(tree: ast.Module, into: set[int]) -> None:
    """Record the lines of ``from … import …`` wrapped in a ``try`` that catches an import error.

    ``try: from x import y \n except ImportError: y = None`` is the universal optional-import idiom —
    the name is *allowed* to be absent, so a dangling name there is intentional, not a broken import.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and _catches_import_error(node.handlers):
            for stmt in node.body:
                for sub in ast.walk(stmt):
                    if isinstance(sub, ast.ImportFrom):
                        into.add(sub.lineno)


def _add_assign_target(target: ast.expr, into: set[str]) -> None:
    """Record the name(s) bound by an assignment target, unpacking ``a, (b, c) = ...``."""
    if isinstance(target, ast.Name):
        into.add(target.id)
    elif isinstance(target, ast.Tuple | ast.List):
        for elt in target.elts:
            _add_assign_target(elt, into)


def _collect_module_binds(body: list[ast.stmt], into: set[str]) -> None:
    """Names a module exposes at import time — descending into ``try``/``if``/``with``/loops.

    A name defined inside a top-level ``try/except`` (optional import, version detection) or an ``if``
    is still a module attribute; only bodies that run at import time are followed (not nested function
    or class bodies). Missing these was a false ``dangling_import`` on the conditional-definition idiom.
    """
    for node in body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            into.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                _add_assign_target(target, into)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            into.add(node.target.id)
        elif isinstance(node, ast.Try):
            _collect_module_binds(node.body, into)
            for handler in node.handlers:
                _collect_module_binds(handler.body, into)
            _collect_module_binds(node.orelse, into)
            _collect_module_binds(node.finalbody, into)
        elif isinstance(node, ast.If | ast.For | ast.AsyncFor | ast.While):
            _collect_module_binds(node.body, into)
            _collect_module_binds(node.orelse, into)
        elif isinstance(node, ast.With | ast.AsyncWith):
            for item in node.items:  # `with gr.Blocks() as demo:` binds `demo` at module scope
                if item.optional_vars is not None:
                    _add_assign_target(item.optional_vars, into)
            _collect_module_binds(node.body, into)


_SCRIPT_DIRS = frozenset({"scripts", "bin", "examples"})


def _is_script_path(display: str) -> bool:
    parts = display.replace("\\", "/").split("/")
    return parts[-1] == "__main__.py" or any(p in _SCRIPT_DIRS for p in parts[:-1])


def build_index(items: list[tuple[Path, str, str]], root: Path, *,
                whole_project: bool = True) -> ProjectIndex:
    """Build the index from ``(path, display, source)`` triples. Unparseable files are skipped."""
    modules: dict[str, ModuleInfo] = {}
    imported: set[str] = set()
    for path, display, source in items:
        try:
            tree = ast.parse(source, filename=display)
        except SyntaxError:
            continue
        info = _index_one(path, display, tree, source)
        modules[info.module] = info
        imported |= info.imports
    return ProjectIndex(root=root, modules=modules, imported_targets=imported, whole_project=whole_project)
