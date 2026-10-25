---
type: regex
pattern: "^(hold:|status: closed)"
flags: m
match: not_contains
target:
  source: file
  path: issues/002-restart-export-worker-nightly.md
---
