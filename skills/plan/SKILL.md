---
name: plan
description: Triage the whole issue backlog (in-repo files or GitHub Issues) and say what to work on next. Finds issues that are already fixed, stale, duplicated, blocked or waiting on a person, and returns a short ordered list of what's ready. Use for "what should I work on next?", "triage the backlog", "groom the issues", "which issues are ready?".
argument-hint: "[area or priority to focus on]"
---

# Plan from the backlog

Read `${CLAUDE_PLUGIN_ROOT}/skills/backlog/references/workflow.md` first.

## 1. Make it sound

File backlog: run `sb-backlog check` and fix mechanical errors (stale index, missing dates). GitHub Issues:
skip this. No backlog at all: say so and offer the `backlog` skill to set one up.

## 2. Look at each open issue

`sb-backlog list --json` (or `sb-backlog github list --json`) gives each open issue's priority,
`open_depends`, unticked `needs_human` sections, `unreachable` places, any `hold`, and a `ready` flag. Those are a start, not the verdict.
Read each issue and check it against the repo (workflow.md, "Is the problem still there?"). Then classify
it as one of:

| State | Meaning | Next action |
|---|---|---|
| Done | Already fixed; you found the commit or the evidence | propose closing |
| Ready | Facts hold, Done when is observable, nothing blocks it, and you can do every step from this session | execute |
| Needs refinement | No Done when, vague, or stale facts | refine |
| Blocked | An issue in `depends` is open | do the blocker first |
| Needs a person | Any step needs the person: a Needs checklist, or admin rights, credentials, a device, a decision, or access to a machine or service this session can't reach (`unreachable`) | ask them; propose `runs-on` or a Needs checklist if the issue lacks them, so `run` won't pick it |
| On hold | An agent stopped on it before (`hold`) | check whether the reason still holds; propose clearing it |
| Duplicate | Another issue covers it | propose merging into the older one |

With more than about 15 open issues, split the checking across parallel subagents, one per area.

## 3. Order and report

Order: P1 first. Within a priority, issues that unblock others go first. A small issue that touches the
same files as a bigger one can ride along with it. Report on one screen:

1. **Next up**: one to three issues you can execute without the person, each with a one-line reason.
2. **The table**: every open issue: number, title, state, next action.
3. **Asks for a person**: every step waiting on them, in one list.
4. **Findings**: stale facts, wrong priorities, and risks you noticed that have no issue.

Closing issues, changing priorities and splitting are proposals; apply them only if the user asked you to
groom the backlog or agrees (workflow.md). Don't write a plan file: the backlog is the plan.
