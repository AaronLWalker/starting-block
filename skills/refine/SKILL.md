---
name: refine
description: Make one backlog issue ready to work on. Checks its claims against the code, finds the cause, writes a concrete fix and an observable "Done when", sets priority, splits it if it's several jobs, and moves steps only a person can do into a Needs checklist. Use for "refine issue 14", "flesh out this issue", "is issue 3 still accurate?", or before executing an issue with no "Done when".
argument-hint: "<issue number>"
---

# Refine an issue

The result should be an issue the `execute` skill can finish without asking anything except decisions
that belong to a person. Read first:
- `${CLAUDE_PLUGIN_ROOT}/skills/backlog/references/issue-format.md`
- `${CLAUDE_PLUGIN_ROOT}/skills/backlog/references/workflow.md`

## 1. Load

Read `issues/NNN-*.md`, the repo's rules (workflow.md), and the issues it names or that share its `area`.
If there's no issue yet, open one with the `backlog` skill first.

## 2. Check every claim

For each fact in the issue (path, line number, setting, command output, version), check it now, read-only.
In the issue:
- correct what has changed, and date the correction;
- mark what you couldn't check, and why;
- if the problem is gone, find the evidence (workflow.md, "Is the problem still there?") and recommend
  closing rather than refining.

Running something that changes state (restarting a service, re-running a job, migrating data) is
execution, not checking. Don't.

## 3. Write it up

- **Problem**: the cause, not only the symptom. If it's still a hypothesis, say so and what would confirm it.
- **Proposed fix**: steps naming files, settings and commands. With real alternatives, number them and
  recommend one.
- **Needs <who>**: a `- [ ]` checklist of everything that takes the person's account, money, credentials,
  admin rights, devices, or a decision that's theirs.
- **Where it runs**: if any step must happen somewhere this repo's sessions can't reach (a production host,
  a device, a live service), set `runs-on` (`sb-backlog set N runs-on=host`). If a step must run a
  command that changes a running system, list the exact commands under `## Allowed commands`; unattended
  runs run nothing else of that kind.
- **Hold**: if the issue is on `hold` and you've fixed the reason (e.g. added the missing Done when), clear
  it with `sb-backlog set N hold=`.
- **Done when**: checks you can observe: a command and its expected output, a test, a page.
- **Verify** and **Roll back**: when a step restarts, migrates, deletes or publishes anything.
- **Split** an issue with more than one independent outcome into several (`sb-backlog new`, linked with
  `depends:`).
- **Priority**: change it if the facts changed, and say why.

## 4. Finish

Run `sb-backlog index` if the title or priority changed, then `sb-backlog check`. Report in a few lines:
what you corrected, what you couldn't verify, and a verdict: **ready**, **blocked by NNN**,
**needs <person>: <the ask>**, or **close: <evidence>**.

Ask the user only for decisions that are theirs. Look up everything else.
