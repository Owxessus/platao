#!/usr/bin/env python3
"""MCP server exposing Platão as agent tools — the "verify before you say done" hook.

Optional extra: this module needs ``mcp`` (the MCP Python SDK) and ``pydantic``, installed via
``pip install 'platao[mcp]'``. The core auditor stays zero-dependency; only this thin adapter pulls
them in, and only when the server is actually run.

The engine does the work (``platao.engine.check_payload``); everything here is input validation and
the tool surface. Run it with ``platao mcp`` or ``platao-mcp``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

from platao import __version__
from platao.checks import PROJECT_REGISTRY, REGISTRY
from platao.engine import check_payload

mcp = FastMCP("platao_mcp")


class CheckInput(BaseModel):
    """Input for ``platao_check``."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(
        ...,
        description="File or directory to audit — absolute, or relative to the working directory. "
        "Pass the file you just wrote, or a directory to sweep.",
        min_length=1,
    )
    fail_on: Literal["high", "medium", "low", "never"] = Field(
        default="high",
        description="Minimum severity that makes 'ok' false (high | medium | low | never).",
    )


@mcp.tool(
    name="platao_check",
    annotations={
        "title": "Audit completeness (Platão)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
def platao_check(params: CheckInput) -> dict:
    """Audit code for completeness defects before you claim a task is done.

    Deterministic (reads the AST — never guesses): catches island/dead code, tests that assert
    nothing, pipelines that can't fail, stub functions, swallowed errors, dynamic-execution risks,
    broken imports, and untracked debt. Call it on a file you just wrote (or a directory) and act on
    the findings before reporting completion.

    Args:
        params (CheckInput):
            - path (str): file or directory to audit.
            - fail_on (str): severity threshold for the 'ok' flag (default 'high').

    Returns:
        dict: {
            "ok": bool,                 # true if nothing at or above fail_on was found
            "fail_on": str,
            "summary": {"high": int, "medium": int, "low": int},
            "findings": [
                {"check_id": str, "category": str, "severity": str,
                 "path": str, "line": int, "message": str, "snippet": str},
                ...
            ]
        }

    Raises:
        FileNotFoundError: if 'path' does not exist (message names the bad path).
    """
    target = Path(params.path)
    if not target.exists():
        raise FileNotFoundError(f"path not found: {params.path}")
    root = target if target.is_dir() else target.parent
    return check_payload([target], root=root, fail_on=params.fail_on)


@mcp.tool(
    name="platao_list_checks",
    annotations={
        "title": "List Platão checks",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
def platao_list_checks() -> dict:
    """List every check Platão can run, with its category, severity, and scope.

    Returns:
        dict: {
            "version": str,
            "checks": [
                {"id": str, "category": str, "severity": str,
                 "scope": "file" | "test-only" | "project"},
                ...
            ]
        }
    """
    checks = [
        {
            "id": c.id,
            "category": c.category,
            "severity": c.severity.value,
            "scope": "test-only" if c.test_only else "file",
        }
        for c in REGISTRY.values()
    ]
    checks += [
        {"id": c.id, "category": c.category, "severity": c.severity.value, "scope": "project"}
        for c in PROJECT_REGISTRY.values()
    ]
    return {"version": __version__, "checks": checks}


def run() -> None:
    """Start the stdio MCP server."""
    mcp.run()


if __name__ == "__main__":
    run()
