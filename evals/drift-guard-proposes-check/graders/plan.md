---
type: llm
---

Facts: the README table lists api on 8000 (compose says 9000), lists a `scheduler` that isn't in compose,
and is missing `worker`.

PASS if the response proposes one source of truth (docker-compose.yml, plus a small manifest for the
descriptions), generating the table or checking it with a script that fails on disagreement, and running
that check in a pre-commit hook and/or CI; AND points out at least two of the three current mismatches.
FAIL if it only suggests fixing the table by hand or "remember to update it".
