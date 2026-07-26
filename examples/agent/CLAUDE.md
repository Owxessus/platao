# Project rule for agents working here

**You may not report a task as done until `platao_check` is clean on the files you changed** (and
`basanos_audit` is clean on any UI component you touched). "It compiles" and "it renders" are not
"it works" — the audit is what tells them apart.

If a finding is a deliberate choice, keep it *and say so explicitly*, with the reason. Never silence a
check, weaken a test, or delete an assertion to make an audit pass — that is the exact failure these
tools exist to catch.
