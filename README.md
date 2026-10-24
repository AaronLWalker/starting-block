# Starting Block

A Claude Code plugin for working from an issue backlog that lives in the repo: plan what's next, refine
issues until they're executable, and execute them through to a verified, committed, closed issue. It also
carries two guards that keep a repo safe to share: a secrets audit and a drift check for generated files.

Issues are plain Markdown files (`issues/NNN-slug.md`), so the backlog is versioned with the code, works
offline, and needs no tracker account. A small bundled Python script (standard library only) does the
mechanical parts: numbering, the index, validation.

## Install

In Claude Code:

```
/plugin marketplace add AaronLWalker/starting-block
/plugin install starting-block@starting-block
```

or from a shell: `claude plugin marketplace add AaronLWalker/starting-block`, then
`claude plugin install starting-block@starting-block`.

Requires Python 3.9+ and git on the machine running Claude Code.

## Skills

Claude picks these up from what you ask; you can also call them directly.

| Skill | Use it to | Example |
|---|---|---|
| `/starting-block:backlog` | Set up the backlog, open, update, close and list issues, repair the index | "log this as an issue", "close issue 7", "what's open?" |
| `/starting-block:plan` | Triage the whole backlog: what's done, stale, blocked, waiting on a person; what's next | "what should I work on next?" |
| `/starting-block:refine` | Verify an issue's facts against the code and make it executable: cause, fix, observable *Done when*, priority, splits | "refine issue 14" |
| `/starting-block:execute` | Take a ready issue to done: reproduce, smallest fix, verify, commit, close with the commit hash | "work on the next issue" |
| `/starting-block:secrets-audit` | Find committed secrets in files and history and fix them in the safe order | "is this repo safe to make public?" |
| `/starting-block:drift-guard` | Keep a generated or derived file in step with its source, with a check and a pre-commit hook | "keep the README table in sync with the config" |

A typical loop: `plan` → `refine` the top issue if it isn't ready → `execute` it → repeat.

## The backlog format

```markdown
---
status: open          # open | closed
priority: P2          # P1 fix soon, P2 worth doing, P3 tidy-up
area: ci, docs
opened: 2026-09-14
depends: 004          # optional
---

# The deploy cache isn't cleared between releases

## Problem
...evidence: file and line, the error, when it was seen...

## Proposed fix
...concrete steps...

## Done when
...observable checks...
```

Optional sections: `## Needs <someone>` for steps only a person can do (agents stop there),
`## Verify`, `## Roll back`, `## Progress (date)`, and `## Resolution` once closed.
`issues/README.md` holds the conventions and an index table the script regenerates.
The full spec is in [skills/backlog/references/issue-format.md](skills/backlog/references/issue-format.md).

## The scripts

Both run on their own, outside Claude Code, and can go in a repo's hooks or CI.

```bash
python3 scripts/backlog.py init | list | next | new | close N | index | check [--strict]
python3 scripts/secret_scan.py [--history] [--staged] [--json]
```

`backlog.py check` exits non-zero when an issue file is malformed or the index is stale;
`secret_scan.py` exits non-zero when it finds anything. Run either with `--help` for details.

## Where this came from

The workflows were extracted from a self-hosted media server repo that has run its work this way since
2026-09: an in-repo issue backlog, issues written with evidence and an observable *Done when*, closing
with the fixing commit, stripping secrets before the repo went to GitHub, and a generated landing page
guarded by a manifest check and a pre-commit hook. The plugin keeps the method and drops the
media-server specifics.

## Development

```bash
python3 -m unittest discover -s tests     # script tests
claude plugin validate .                  # manifest and skill checks
claude --plugin-dir .                     # try the skills locally
claude plugin eval . --runs 1             # skill evals (real model calls)
```

See [CONTRIBUTING.md](CONTRIBUTING.md). Licensed under [MIT](LICENSE).
