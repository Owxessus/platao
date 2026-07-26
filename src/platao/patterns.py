"""Shared patterns for the security checks — kept in one place so the Python and polyglot layers agree.

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
    r"""\s*[:=]\s*(['"])([^'"\s]{%d,})\2""" % MIN_SECRET_LEN
)
