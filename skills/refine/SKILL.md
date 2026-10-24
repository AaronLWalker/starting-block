---
name: refine
description: Turn a rough, vague or stale backlog issue into one that can be executed without guesswork. Verifies each claim against the code, finds the cause, pins down the fix and an observable "Done when", sets priority, splits multi-part issues, and moves steps only a person can do into their own section. Use when asked to refine, groom, flesh out, scope, sanity-check or write up an issue, or before executing an issue that has no "Done when".
argument-hint: "<issue number | rough description>"
---

# Refine an issue

The goal is an issue the `execute` skill can finish without asking anything except the decisions that
belong to a person. Issue format: [issue-format.md](${CLAUDE_PLUGIN_ROOT}/skills/backlog/references/issue-format.md).
Script: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/backlog.py"` (called `backlog.py` below).

## 1. Load

- Given a number, read `issues/NNN-*.md`. Given a description with no issue yet, open one first with the
  `backlog` skill, then refine it.
- Read the repo's instructions (`CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, `issues/README.md`). Note
  anything the fix must respect: protected services, commands that must be scoped, review rules.
- Read the issues it names or that share its `area`; the right answer may be "duplicate of 012".

## 2. Verify every claim

For each fact in the issue (a path, a line number, a setting's value, a command's output, a version):
check it now, read-only. Then in the issue:

- Correct what's changed, and date the correction.
- Mark what you couldn't check, and why (needs production access, needs a credential).
- If the problem is already gone, find out why (`git log --since=<opened> -- <paths>`,
  `git log --grep=<number>`, `git log -S '<string>'`). Recommend closing it with that evidence instead of
  refining it.

Don't run anything that changes state to "check" a claim. Restarting a service or re-running a job belongs
to execution.

## 3. Find the cause

Trace the symptom to where it starts, as far as reading code, configs and logs allows. A proposed fix
for a symptom becomes the next issue. Record what you found under Problem; if it's still a hypothesis,
say so and say what would confirm it.

## 4. Write the fix

- **Proposed fix:** steps that name the files, settings and commands. With real alternatives, number
  them, recommend one, and give the reason in a line.
- **Blast radius:** say what else the change touches. If a step restarts, migrates, deletes or
  publishes anything, add `## Verify` and `## Roll back` with exact commands.
- **Needs a person:** anything requiring an account login, money, a credential, physical access, or a
  decision that's the owner's to make goes under `## Needs <who>`, as numbered steps they can follow.
- **Done when:** each item is something you can observe: a command and its expected output, a test that
  passes, a page that loads, a value in a file. Replace "works", "is fixed" and "is faster" with the check.

## 5. Size and priority

- **Split** when the issue has more than one independent outcome, or would take more than one focused
  session. Open the parts with `backlog.py new`, link them with `depends:`, and either close the original
  pointing at them or keep it as the umbrella with a list of the parts.
- **Priority:** P1 for real risk (data loss, security, outage) or blocking other work; P2 for a clear defect
  or improvement; P3 for tidy-up. Change it if the facts changed, and say why in the issue.

## 6. Finish

1. `backlog.py index` if the title, priority or status changed, then `backlog.py check`.
2. Commit the issue files if the repo commits its backlog (e.g. `issues: refine 014`).
3. Report in a few lines: what you corrected, what you couldn't verify, and a verdict:
   **ready**, **blocked by NNN**, **needs <person>: <the ask>**, or **close: <evidence>**.

Ask the user only for decisions that are theirs (which option, whether to spend money, whether a
behavior change is acceptable). Everything that can be looked up, look up.
