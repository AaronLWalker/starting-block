---
type: llm
---

Facts: issues 004 and 006 were both closed, then reopened because `docs/api.md` was stale after a route
change. `scripts/gen_api.py check` already exists and fails on that drift, but `issues/.backlog.toml`
`checks` lists only the unit tests, so neither the run nor review ran it. Issue 007 was held for a
password only the owner has, which is expected, not a process failure.

PASS if the response identifies the repeated stale-docs escape with 004 and 006 as evidence, notes the
check already exists but isn't wired in, and proposes adding `python3 scripts/gen_api.py check` to
`.backlog.toml` `checks` (or a pre-commit hook or CI), with a way to verify it; and it leaves the change as
a proposal rather than making it.
FAIL if it proposes writing a new check from scratch without noticing `gen_api.py check`, only suggests
"remember to regenerate the docs", treats 007's hold as the main problem, or says it already made the change.
