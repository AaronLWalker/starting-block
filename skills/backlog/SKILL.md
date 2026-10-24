---
name: backlog
description: Keep the project's issue backlog, as Markdown files in the repo (issues/NNN-slug.md) or in GitHub Issues. Use to set one up, file or log a new issue, update or reopen one, list what's open, or fix a malformed backlog. Triggers include "log this as an issue", "add this to the backlog", "write up an issue for this", "what's open in the backlog?", "set up an issue tracker in the repo".
argument-hint: "[init | new <title> | list | check]"
---

# Backlog

Read these before writing to the backlog:
- `${CLAUDE_PLUGIN_ROOT}/skills/backlog/references/issue-format.md`: the file format.
- `${CLAUDE_PLUGIN_ROOT}/skills/backlog/references/workflow.md`: running the script, commits, teams and PRs.

```bash
sb-backlog init                      # create issues/ and its README (conventions + index table)
sb-backlog list                      # open issues, P1 first; --status all|closed, --priority, --area, --json
sb-backlog new --title "..." --priority P2 --area api   # create from the template, update the index
sb-backlog close 7 --resolution "Fixed in #123"         # status, closed date, Resolution, index
sb-backlog index                     # rewrite the README index table from the files
sb-backlog check                     # fail on malformed files or a stale index; --strict fails on warnings too
```

It uses `issues/` (or an existing `backlog/`) at the git root; `--dir` points it elsewhere, e.g. one backlog
per package in a monorepo.

## Set one up

If the repo tracks work in GitHub Issues, there's nothing to set up: work there (workflow.md, "Where the
backlog lives"). If it uses another tracker (Jira, a TODO file), say so and ask before creating a second
one. Otherwise `sb-backlog init`, then show the user `issues/README.md`.

## Open an issue

1. **Look for a duplicate**: `sb-backlog list --status all`, and search `issues/` for the key words. If one
   covers it, update or reopen that one instead.
2. **Check the facts.** Read the code, run read-only commands, and note what you saw with the date.
3. **Create it**: `sb-backlog new --title "<what's wrong, in plain words>" --priority <P1|P2|P3>`, then
   fill in Problem, Proposed fix and Done when. One issue per outcome.
4. `sb-backlog check` must pass.

If the issue is vague or you couldn't pin down the cause, say so and suggest the `refine` skill.

## Update or reopen

Add new facts with a date (`## Progress (YYYY-MM-DD)`, or a corrected line in Problem). After changing a
title, priority or status, run `sb-backlog index`; never edit index rows by hand. Never delete an issue
file. Reopening: see workflow.md.

Closing an issue belongs to the `execute` skill, which verifies the Done when first.

## Repair

Run `sb-backlog check` and fix what it reports. Fix index drift and missing dates directly. Content
warnings (no Done when, closed without a Resolution) need `refine` or facts from git history; don't
invent a resolution you can't trace to a commit or PR.
