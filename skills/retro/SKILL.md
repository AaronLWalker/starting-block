---
name: retro
description: Look back at a session, a backlog run or a stretch of closed issues for recurring mistakes, checks that caught problems late or not at all, wrong or missing instructions, and wasted effort, then propose concrete fixes with evidence. Mechanical mistakes become checks; judgement calls become instructions. Proposes only. Use for "do a retro on this session", "what went wrong in last night's run?", "why do we keep breaking the export?", "what should we change after this sprint?".
argument-hint: "[this session | <run report> | since <date or commit>]"
---

# Retrospective

Find what would stop the next session from repeating this one's mistakes, and propose it. A retro
**changes nothing**: no edits to instructions, checks, hooks, CI or the backlog, and no issues opened,
until the user accepts a proposal. Read `${CLAUDE_PLUGIN_ROOT}/skills/backlog/references/workflow.md` first.

## 1. Gather the evidence

- **This session** (the default): what was asked, what was tried, what failed and why, what the user had
  to correct.
- **A run**: its report (the `run` table, an Actions `run-report.md`), plus each issue's Progress notes,
  hold reasons and `REVIEW:` findings.
- **A stretch of work** (`since <date or commit>`): `git log --since`, issues closed in that time
  (`sb-backlog list --status closed --json`), reopened ones (an `## Earlier resolution`), holds, and CI
  failures you can see.

Follow the pointers the work left (issues, decision records, instructions) rather than guessing.

## 2. Look for

- **Escapes**: a problem found by CI, review, the user or production that an earlier check could have
  caught; a closed issue that had to be reopened.
- **Repeats**: the same mistake twice, in this work or in earlier Progress notes.
- **Avoidable stops**: holds and stops that `refine` could have prevented (no Done when, a Scope too
  narrow, a missing `runs-on` or Needs step), and issues too big for one session.
- **Instructions**: rules that were wrong, missing, contradictory or hard to find; time spent
  rediscovering a fact.
- **Cost**: commands run over and over, long searches for where something lives, retries.

Check what already exists first. A check that exists but isn't wired in (a hook not enabled, a command
missing from `.backlog.toml` `checks` or CI) is a different fix from a check that's missing.

## 3. Propose

For each finding:

| Field | What goes in it |
|---|---|
| Problem | What happened, in a sentence. |
| Evidence | Commit, issue, file and line, command output: something the user can check. |
| Severity | **High**: will recur and cost real damage or time. **Medium**: will recur, cheap to absorb. **Low**: one-off friction. |
| Change | Where it goes (below) and what it says or does. |
| Verify | How to show the change works: the check failing on the old mistake, an eval, a command. |
| Covered by | An existing issue, check or instruction that already covers it, if any. |

Where a change goes:
- **Mechanical** (a script could tell right from wrong): a check: `.backlog.toml` `checks`, a pre-commit
  hook, a test, or the `drift-guard` skill for generated files.
- **Judgement**: the instructions file, as `${CLAUDE_PLUGIN_ROOT}/skills/execute/references/recording-facts.md`
  says.
- **One issue's gap**: `refine` that issue.

Keep findings that recurred or escaped review ahead of hypothetical ones. Drop any that an existing issue,
check or instruction already covers, and say which.

## 4. Report

The proposals, most severe first, then what you looked at. **No findings is a complete retro**: say so,
and don't invent work to fill the report.

For each proposal the user accepts, open a backlog issue with the `backlog` skill (the change, the
evidence and the Verify as its Done when); the work then goes through `refine` and `execute` like any other.
