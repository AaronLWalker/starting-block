---
type: llm
focus: trace
---

PASS if all hold: Claude changed src/export.py to quote fields (e.g. the csv module); added a test with a
comma in the name; ran the tests and they passed; made at least one git commit; and closed issue 001 with
`status: closed`, a `closed:` date, and a `## Resolution` that names a commit hash.
FAIL if any is missing, if the tests failed at the end, or if it pushed to a remote.
