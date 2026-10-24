---
name: plan
description: Review the whole in-repo backlog and decide what to work on next. Validates it, finds issues that are stale, already fixed, duplicated, blocked or waiting on a person, and produces a short ordered plan with the next issues that are ready to execute. Use for "what should I work on next?", "triage the backlog", "groom the issues", "plan this session", "prioritize the backlog", or before executing several issues in a row.
argument-hint: "[area or priority to focus on]"
---

# Plan from the backlog

Script: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/backlog.py"` (called `backlog.py` below).
Issue format: [issue-format.md](${CLAUDE_PLUGIN_ROOT}/skills/backlog/references/issue-format.md).

## 1. Make the backlog sound

Run `backlog.py check`. Fix the mechanical errors (stale index, a missing `closed:` date) and run it
again. Leave content warnings for step 3; they're findings, not chores.

If there's no backlog directory, stop and say so; offer the `backlog` skill to set one up.

## 2. Load it

`backlog.py list --json` gives every open issue with its priority, `depends`, `open_depends`,
`needs_human` sections and a `ready` flag (has a Done when, nothing blocking, no person needed).
Narrow it if the user named an area or priority. Read the issue files themselves; the flags are a start,
not the verdict.

## 3. Check each open issue against the repo

For every open issue, a quick look, read-only:

- **Still a problem?** Has anything changed since it was opened?
  `git log --oneline --since=<opened> -- <paths it names>`, `git log --oneline --grep=<number>`,
  and a look at the file or setting it describes.
- **Classify it** as exactly one of:

| State | Meaning | Next action |
|---|---|---|
| Done | Fixed already; you found the commit or the evidence | close it, citing the evidence |
| Ready | Facts hold, Done when is observable, nothing blocks it | execute |
| Needs refinement | No Done when, vague, or its facts are stale | refine |
| Blocked | An issue in `depends` is open | do the blocker first |
| Needs a person | Has a `## Needs ...` section not yet done | ask them, once, together |
| Duplicate | Another issue covers it | merge into the older one and close |

With more than about 15 open issues, split the checks across parallel subagents (e.g. one per area),
each returning a row per issue: number, state, evidence, next action.

## 4. Order the work

1. P1, then P2, then P3.
2. Within a tier: issues that unblock others first, then the ones reducing risk, then the smallest.
3. A P3 that takes minutes and touches the same files as a P1 can ride along with it; say so.

Check the priorities against the rubric in the format guide while you're here, and flag any that look
wrong with a reason.

## 5. Apply or propose

- **Apply** without asking: mechanical fixes from step 1.
- **Propose**, and apply only if the user asked you to groom the backlog or agrees: closing issues as done
  or duplicate, priority changes, splits, new `depends`. When you apply, write the reason into each issue,
  run `backlog.py index` and `backlog.py check`, and commit the issue files together
  (e.g. `issues: triage, close 004 and 009`).

## 6. Report

Keep it to one screen:

1. **Next up:** the one to three ready issues to execute, in order, each with one line on why.
2. **The table:** every open issue: number, title, state, next action.
3. **Asks for a person:** every `Needs ...` step across the backlog, in one list, so they can do them in
   one sitting.
4. **Findings:** stale facts, wrong priorities, gaps (a risk you noticed that has no issue: offer to open one).

Don't write a plan file unless the user asks for one; the backlog is the plan.
