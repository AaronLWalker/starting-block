---
type: llm
focus: trace
---

Facts: issue 001 bundles three independent outcomes: quoting fields that contain commas, tolerating a
contact with no phone, and a new JSON export.

PASS if Claude split the work so each outcome is its own issue (001 may keep one of them), and each
resulting issue has its own `## Done when` with a checkable test or command and a `## Scope` with a
`Paths:` line naming the files it may change; `sb-backlog check` (or an equivalent check) passes at the end.
FAIL if the three outcomes stay in one issue, any resulting issue lacks a Done when or a Scope, or Claude
implemented any of the fixes.
