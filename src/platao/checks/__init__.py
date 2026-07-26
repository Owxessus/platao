"""The check registry.

A check is a generator: given a :class:`~platao.context.FileContext`, it yields ``(line, message)``
tuples (or a full :class:`~platao.finding.Finding`). The ``@register`` decorator stamps each yielded
tuple with the check's id, category and default severity, so a check body stays about *detection* and
never about bookkeeping.

Adding a check is: write the generator, decorate it, done. There is no plugin manifest to edit — the
decorator is the registration. Contributors must still ship the proof fixtures (see CONTRIBUTING.md);
that is enforced by CI, not by this module.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass

from platao.context import FileContext
from platao.finding import Finding, Severity
from platao.project import ProjectIndex

# What a raw check body may yield: a bare (line, message), a (line, message, severity), or a
# fully-formed Finding for the rare check that wants total control.
Yielded = tuple[int, str] | tuple[int, str, Severity] | Finding
RawCheck = Callable[[FileContext], Iterable[Yielded]]
Check_fn = Callable[[FileContext], Iterator[Finding]]


@dataclass(frozen=True, slots=True)
class Check:
    """Registered check: its identity plus the stamped generator the engine calls."""

    id: str
    category: str
    severity: Severity
    fn: Check_fn
    test_only: bool = False


REGISTRY: dict[str, Check] = {}


def register(
    check_id: str,
    category: str,
    severity: Severity,
    *,
    test_only: bool = False,
) -> Callable[[RawCheck], Check_fn]:
    """Register a check. The wrapper turns yielded tuples into stamped :class:`Finding` objects.

    Args:
        check_id: stable, unique id (also the config key to enable/disable it).
        category: reporting group.
        severity: default severity for this check's findings.
        test_only: if true, the engine runs it only on test files.
    """

    def decorator(raw: RawCheck) -> Check_fn:
        def wrapped(ctx: FileContext) -> Iterator[Finding]:
            for item in raw(ctx):
                if isinstance(item, Finding):
                    yield item
                    continue
                line, message = item[0], item[1]
                sev = item[2] if len(item) > 2 else severity  # type: ignore[misc]
                yield Finding(check_id, category, sev, ctx.path, line, message, ctx.snippet(line))

        if check_id in REGISTRY or check_id in PROJECT_REGISTRY:
            raise ValueError(f"duplicate check id: {check_id!r}")
        REGISTRY[check_id] = Check(check_id, category, severity, wrapped, test_only)
        return wrapped

    return decorator


# ── project-wide checks (need the whole file set, not one file) ────────────────────────────────
ProjectCheckFn = Callable[[ProjectIndex], Iterator[Finding]]


@dataclass(frozen=True, slots=True)
class ProjectCheck:
    """A check that reads the whole :class:`~platao.project.ProjectIndex` and yields findings."""

    id: str
    category: str
    severity: Severity
    fn: ProjectCheckFn


PROJECT_REGISTRY: dict[str, ProjectCheck] = {}


def project_check(
    check_id: str, category: str, severity: Severity
) -> Callable[[ProjectCheckFn], ProjectCheckFn]:
    """Register a project-wide check. Its body yields fully-formed :class:`Finding` objects."""

    def decorator(fn: ProjectCheckFn) -> ProjectCheckFn:
        if check_id in REGISTRY or check_id in PROJECT_REGISTRY:
            raise ValueError(f"duplicate check id: {check_id!r}")
        PROJECT_REGISTRY[check_id] = ProjectCheck(check_id, category, severity, fn)
        return fn

    return decorator


# Importing the submodules is what populates the registries (each decorator runs at import time).
# Kept at the bottom so `register` / `project_check` are defined before the submodules import them.
from platao.checks import hygiene, placebo, project, robustness  # noqa: E402,F401
