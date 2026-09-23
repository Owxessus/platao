"""Shared patterns for the security and debt checks — in one place so the Python and polyglot layers agree.

A hardcoded secret is one of the highest-signal defects there is, and it shows up the same way in every
language: a secret-ish name assigned a string literal. The one thing that keeps this from crying wolf is
telling a real secret from a fixture/example placeholder — so both layers use the *same* name set and the
*same* placeholder rule, and neither ever puts the secret's value in a message or a log.
"""

from __future__ import annotations

import re

# Minimum length of a string value before we'll consider it a secret (shorter is almost always a flag,
# an enum, or a label — not a credential).
MIN_SECRET_LEN = 8

# Names that announce the value is a credential.
SECRET_NAME = re.compile(
    r"(?i)\b(password|passwd|secret|api[_-]?key|apikey|access[_-]?key|"
    r"auth[_-]?token|access[_-]?token|refresh[_-]?token|token|private[_-]?key|"
    r"client[_-]?secret|credential)\b"
)

# Values that are almost always a placeholder/fixture, not a real leak — a real secret next to one of
# these words is vanishingly rare, and flagging them at full severity is the classic secret-scanner
# false alarm. Presence of a placeholder marker downgrades severity rather than silencing (a reviewer
# still gets to see it), never the reverse.
PLACEHOLDER = re.compile(
    r"(?i)(test|example|xxx+|change[_-]?me|your[_-]?|placeholder|dummy|fake|sample|"
    r"redacted|<.*>|\$\{|foo|bar|baz|1234|abcd|\.\.\.)"
)

# The polyglot (regex) match: a secret-ish name, then `=`/`:`, then a quoted string of real length.
SECRET_ASSIGN = re.compile(
    r"""(?i)\b(password|passwd|secret|api[_-]?key|apikey|access[_-]?key|auth[_-]?token|"""
    r"""access[_-]?token|refresh[_-]?token|token|private[_-]?key|client[_-]?secret|credential)\b"""
    rf"""\s*[:=]\s*(['"])([^'"\s]{{{MIN_SECRET_LEN},}})\2"""
)


def is_debt_marker(word: str, after: str) -> bool:
    """Is a matched ``TODO``/``FIXME``/``XXX``/``HACK`` really a debt marker, not a plain word?

    Shared by the Python and polyglot ``debt_tracked``. The all-caps form always counts; any other
    casing only in the conventional ``todo:`` form. "Todo"/"todo" is an everyday word in Portuguese
    and Spanish ("every"/"all") — ``# Todo arquivo de teste roda offline`` is a sentence, not a debt,
    and case-insensitive matching flagged every such comment.
    """
    return word.isupper() or after.lstrip().startswith(":")


_SCOPE_ID = re.compile(r"[a-z][a-z0-9]*(\.[a-z0-9]+)+")  # dotted lowercase: `variable.predefined`
_PATTERN_CHARS = frozenset("[](){}\\|*")  # regex/glob metachars — never in a credential


def looks_like_secret_value(value: str) -> bool:
    """Does the string have the *entropy* of a real credential, or is it a plain label/word?

    A real key/token has mixed case, digits, or symbols (``sk-live-9f3…``). ``CREDENTIAL =
    "credential"`` is an enum label — all-lowercase letters, a dictionary word. Requiring some entropy
    is what stops a secret-*named* constant assigned a plain word from being a false "hardcoded secret".

    A **dotted lowercase identifier** (``variable.predefined``, ``delimiter.curly``) is a scope / enum /
    namespace, never a credential — vscode's editor assigns 98 of these to a var literally named
    ``token`` (lexer/theme tokens). The dot alone must not read as entropy.
    """
    if _SCOPE_ID.fullmatch(value):
        return False
    if any(c in _PATTERN_CHARS for c in value):
        return False  # a regex/glob/format (`[a-z]+`, `{id}`) — a lexer pattern, not a credential
    return any(c.isdigit() or c.isupper() for c in value) \
        or any(not c.isalnum() and c != "_" for c in value)
