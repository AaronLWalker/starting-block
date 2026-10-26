---
type: regex
pattern: "status: closed"
match: not_contains
target:
  source: file
  path: issues/001-export-crashes-on-every-row.md
---
