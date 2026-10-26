---
name: review
description: Independently review a change against the backlog issue it's meant to fix, before the issue closes or the change merges. Two passes, requirements (does it meet every "Done when", and only that?) and standards (the repo's rules, the issue's Scope, secrets, weakened checks), each returning pass or blocked with evidence. Read-only. Use for "review this against issue 12", "check my last commit before I close it", "review PR #34 against its issue", and when execute or run hands over a candidate.
argument-hint: "<issue> [<commit | A..B | branch | PR>] [--pass requirements|standards]"
---

# Review a change

A review is a second look at the exact change, by a session that didn't write it. The author's account of
the change (a report, a commit message, a PR description) is a claim to check, not evidence. Read
`${CLAUDE_PLUGIN_ROOT}/skills/backlog/references/workflow.md` first.

**Read-only.** Don't edit, stage, commit, push, comment on or close anything, and don't fix what you find.
Running the repo's checks and the issue's Done when commands is allowed: they're how you get evidence.

## 1. Pin the change

- **The candidate**: the commit, range, branch or PR you were given; nothing given means `HEAD`. For a PR,
  `git fetch origin pull/N/head` and use the range from its merge base with the default branch.
- Write down the base and candidate hashes (`git rev-parse`) and review exactly `git diff <base>..<candidate>`.
  Uncommitted changes aren't part of the candidate; say if there are any.
- Load the issue (`sb-backlog list --json --status all`, then its file; or the GitHub issue), the repo's
  rules and protected list (workflow.md), and the decision records and glossary for the area.

## 2. Two passes

Each pass runs in its own fresh context so neither is swayed by the other: with `--pass`, run only that one
(that's how `execute` and `run` call you). Without `--pass`, start a subagent for each, giving it the issue,
the base and candidate, the protected list and its pass, and nothing else; without a subagent tool, run them
one after the other yourself and say so.

**Requirements**: does the change do what the issue asks, and only that?
- For every Done when item, the evidence that it holds at the candidate: run the command or test and quote
  the result. A test that would pass without the fix isn't evidence; where it's cheap, show it fails on the
  base (in a `git worktree add` outside the repo, removed afterwards).
- Behaviour the Problem describes that the change doesn't handle.
- Changes no Done when or Proposed fix item calls for.

**Standards**: does it follow the repo's rules?
- `sb-backlog scope-check N --range <base>..<candidate>` (GitHub: `--body <file>`), and the Scope's `Not:` lines.
- The protected list and the rules no repo overrides: secrets (`sb-secret-scan --since <base>`), hooks
  bypassed, commands that change a running system outside `## Allowed commands`.
- Checks weakened: tests deleted or skipped, assertions loosened, a check dropped from CI or `.backlog.toml`.
- Generated files edited by hand, docs the change made untrue, dependencies the issue didn't call for, a
  decision record contradicted.
- The repo's checks at the candidate (`sb-backlog run-checks`, or as workflow.md says).

## 3. Verdict

- **pass**: every Done when item has concrete evidence, the checks pass, and nothing needs changing.
- **blocked**: anything else. Each finding gives the file and line, what's wrong, the evidence, and what
  would fix it.

Style preferences and ideas go under **Notes**: they never block and never add to the issue's scope. A
failing check blocks whatever the passes conclude: agreement between reviewers is not the gate.

Report the findings per pass, then end with one line `execute` and `run` can read:
`REVIEW: pass|blocked | <issue> | <candidate hash> | <requirements, standards or both> | <one-line reason>`
With both passes, it's `pass` only if both pass.
