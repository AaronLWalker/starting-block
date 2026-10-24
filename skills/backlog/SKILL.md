---
name: backlog
description: Keep an issue backlog inside the repo, one Markdown file per issue under issues/ with a generated README index. Use to set one up, open (file, log) an issue, update or close one, list what's open, or repair a malformed backlog. Triggers include "open an issue for this", "log this in the backlog", "add a todo issue", "close issue 12", "what's open?", "set up an issue tracker in the repo".
argument-hint: "[init | new <title> | close <N> | list | check]"
---

# Backlog

An issue is a file, `issues/NNN-short-slug.md`, versioned with the code it's about. The format is in
[issue-format.md](references/issue-format.md); read it before writing or editing an issue.

Every mechanical step goes through the bundled script, which needs only Python 3. Below, `backlog.py` stands
for `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/backlog.py"`; write the full form in each command, since shell
variables don't carry over between commands.

```bash
backlog.py init                      # create issues/ and its README (conventions + index table)
backlog.py list                      # open issues, P1 first; --status all|closed, --priority, --area, --json
backlog.py next                      # next free number
backlog.py new --title "..." --priority P2 --area docs   # create from the template, update the index
backlog.py close 7 --resolution "Fixed in a1b2c3d: ..."  # status, closed date, Resolution, index
backlog.py index                     # rewrite the README index table from the files
backlog.py check                     # fail on malformed files or a stale index; --strict fails on warnings too
```

It finds `issues/` (or an existing `backlog/`) at the git root; pass `--dir` for anything else.

If the script can't run (no Python, or a sandbox that blocks it from writing), do the same steps by hand:
the next number is one more than the highest `NNN-` file, the file follows the template in the format
guide, and the index row is `| [NNN](NNN-slug.md) | P2 | Title |` (`P2 (closed)` once closed). Say that
you did it by hand.

## Before you start

- If the repo has no backlog directory but tracks work somewhere else (GitHub Issues, Jira, a TODO file),
  say so and ask before creating a second tracker.
- Read the repo's own conventions: `issues/README.md`, and `git log --oneline -- issues/` for how its
  backlog commits are worded. Where they differ from this skill, follow the repo.

## Open an issue

1. **Look for a duplicate.** `backlog.py list --status all` and `grep -ril '<keyword>' issues/`. If one covers
   it, update that issue instead, or reopen it (`status: open`, remove `closed:`) when the fix didn't hold.
2. **Check the facts first.** Read the files, run the read-only commands, and write down what you saw:
   paths, line numbers, the exact error, the date. An issue built on an unverified claim wastes the next
   person's time.
3. **Create it.** `backlog.py new --title "<what's wrong, in plain words>" --priority <P1|P2|P3> --area <area>`
   prints the new path. Fill in Problem, Proposed fix and Done when. Put steps only a person can take under
   `## Needs <someone>`. Set `depends:` when another issue must close first.
4. **Validate.** `backlog.py check` must pass.
5. **Commit** if the repo commits its backlog, with just the issue files, e.g. `Open issue 016: <title>`.

One issue per outcome. If you're writing "and also", it's probably two issues.

## Update an issue

- New facts go into the issue with a date: a `## Progress (YYYY-MM-DD)` section, or a corrected line in
  Problem. Don't leave a stale claim standing next to the new one.
- Changing priority, title or status: edit the file, then `backlog.py index`. Never edit the index rows by hand.
- Never renumber or delete an issue file. Closed issues are the history.

## Close an issue

1. Confirm every **Done when** item holds now: run the checks, don't infer from the diff.
2. `backlog.py close N --resolution "<what fixed it> (<commit hash>)"`. If the fix landed in several commits
   or partly elsewhere, say where each part went, and name any follow-up issue.
3. `backlog.py check`, then commit, e.g. `issues: close 007 (<short reason>)`.

When the fix itself is still uncommitted, commit it first so the Resolution can name its hash.

## Repair a backlog

Run `backlog.py check` and fix what it reports. Index drift and missing dates are mechanical: fix them.
Content warnings (no Done when, closed without a Resolution) need the `refine` skill or the facts from
git history; don't invent a resolution you can't trace to a commit.
