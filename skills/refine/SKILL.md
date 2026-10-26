---
name: refine
description: Make one backlog issue ready to work on. Checks its claims against the code, investigates the cause, writes a concrete fix, its Scope and an observable "Done when", sets priority, splits it into one-session slices if it's too big, and moves steps only a person can do into a Needs checklist. Use for "refine issue 14", "flesh out this issue", "is issue 3 still accurate?", or before executing an issue with no "Done when".
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
  closing rather than refining. If the fix shipped but its effect can only be seen later, replace the
  remaining work with an `## Observe` section (what to look at, `after YYYY-MM-DD`).

Running something that changes state (restarting a service, re-running a job, migrating data) is
execution, not checking. Don't.

## 3. Investigate, if the cause isn't known

If the issue has an `## Investigate` section, or the Problem is still a guess, answer the questions
read-only: read code and history, run read-only commands, reproduce it in a scratch copy outside the
repo. Record what you found in `## Progress (YYYY-MM-DD)`, keeping what you saw apart from what you infer.
Once the questions that decide the fix are answered, replace `## Investigate` with the Problem's cause and
go on to write it up. If an answer needs an experiment that changes something (a live service, real data,
money), don't run it: make it a `## Needs <who>` step, and leave the section in place.

## 4. Write it up

- **Problem**: the cause, not only the symptom. If it's still a hypothesis, say so and what would confirm it.
- **Proposed fix**: steps naming files, settings and commands. With real alternatives, number them and
  recommend one.
- **Scope**: `- Paths:` with the backticked files and directories the fix may change (tests and docs
  included), and `- Not:` for what it must not do (an interface to keep, data not to touch). Keep it as
  narrow as the fix; `execute` stops rather than go outside it.
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
- **Size and split.** One issue is what one session can do with its review and verification. Split an issue
  that's bigger, or that has more than one independent outcome, into vertical slices: each changes
  something observable end to end and has its own Done when, rather than one per layer. Create them with
  `sb-backlog new`, link them with `depends:`, and say what each delivers. A migration, a deployment or an
  observation is its own issue, not a step inside a code change.
- **Priority**: change it if the facts changed, and say why.

## 5. Finish

Run `sb-backlog index` if the title or priority changed, then `sb-backlog check`. Report in a few lines:
what you corrected, what you found, what you couldn't verify, and a verdict: **ready**, **split into NNN,
NNN**, **blocked by NNN**, **investigate: <the open questions>**, **observe after <date>**,
**needs <person>: <the ask>**, or **close: <evidence>**.

Keep the person's request apart from your suggestions: what they asked for goes in the issue as the
requirement; your ideas go in the report, or a new issue if they agree.

Ask the user only for decisions that are theirs. Look up everything else.
