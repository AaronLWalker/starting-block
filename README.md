# Starting Block

A Claude Code plugin for working from an issue backlog. Claude plans what's next, refines
an issue until it's clear what "done" means, then executes it: fix, verify, commit, and close the issue
with the commit that fixed it.

Issues are plain Markdown files (`issues/001-login-fails-after-reset.md`), versioned with the code and
needing no tracker account, or, if your project already uses them, GitHub Issues.

**Good fit:** a repo where you (or a small team) want Claude to pick up well-defined work and finish it
end to end.
**Not yet:** Jira, Linear and other trackers.

## Install

In Claude Code:

```
/plugin marketplace add AaronLWalker/starting-block
/plugin install starting-block@starting-block
```

It runs in Claude Code (terminal, desktop and IDE) on macOS, Linux and Windows; it isn't built for
skill uploads to claude.ai. You need git and Python 3.9 or later. On Windows, install Python from python.org, which adds the `py`
launcher; the plugin finds `python3`, `python` or `py` itself. Update with
`claude plugin update starting-block@starting-block`; remove with
`claude plugin uninstall starting-block@starting-block`.

## First 10 minutes

Using GitHub Issues already? Skip step 1: Claude reads and writes your GitHub issues (it needs the `gh`
CLI logged in, or GitHub tools in Claude Code), and closes them through `Fixes #N` in your PRs.

1. **Start a backlog.** Ask: *"Set up an issue backlog in this repo."* Claude creates `issues/README.md`
   (conventions and an index table).
2. **Log something.** *"Log an issue: the signup form accepts an empty email."* Claude checks the code,
   then writes `issues/001-signup-form-accepts-empty-email.md` with the problem, a proposed fix and a
   **Done when** (the checks that prove it's fixed).
3. **Make it ready** (only if it's vague): *"Refine issue 1."* Claude checks each claim against the code and
   tightens the fix and the Done when.
4. **Do it.** *"Work on issue 1."* Claude reproduces the bug, makes the fix, runs the Done when checks and
   your tests, commits, and closes the issue citing the commit.
5. **Next.** *"What should I work on next?"* Claude triages the backlog and names the issues that are
   ready.

Claude asks before running commands that change things outside the repo, and never pushes unless you ask.
Only *execute* commits on its own; the other skills leave their changes for you to review.

## Skills

| Skill | Use it to | Say |
|---|---|---|
| `/starting-block:backlog` | Start the backlog; log, update and list issues | "log this as an issue", "what's open?" |
| `/starting-block:plan` | Triage everything: done, stale, blocked, waiting on you, what's next | "what should I work on next?" |
| `/starting-block:refine` | Make one issue ready: check its facts, fix plan, Done when | "refine issue 14" |
| `/starting-block:execute` | Take a ready issue to done: fix, verify, commit, close | "work on issue 12" |
| `/starting-block:run` | Work through every ready issue, one after another, unattended if you like | "work through the backlog" |

**Also included**, for keeping a repo safe to share:

| Skill | Use it to | Say |
|---|---|---|
| `/starting-block:secrets-audit` | Find committed secrets in files and history and fix them in the safe order | "is this repo safe to make public?" |
| `/starting-block:drift-guard` | Keep a generated file in sync with its source, with a check and a hook | "the API docs keep going stale" |

## An issue

```markdown
---
status: open          # open | closed (closed issues also get `closed: YYYY-MM-DD`)
priority: P2          # P1 fix soon, P2 worth doing, P3 tidy-up
area: auth            # optional
opened: 2026-09-14
depends: 004          # optional: issues that must close first
---

# Login fails after a password reset

## Problem
What's wrong, with evidence: file and line, the error, when it was seen.

## Proposed fix
Concrete steps.

## Done when
- `pytest tests/test_auth.py -k reset` passes, including a new test for this.
```

**Words used here:**
- **Done when**: observable checks that prove the issue is fixed.
- **Needs \<someone\>**: a checklist of steps only a person can do (credentials, admin rights, a decision).
  Claude stops there until every box is ticked.
- **Ready**: has a Done when, nothing blocking it, and nothing waiting on a person.

Full spec: [issue-format.md](skills/backlog/references/issue-format.md).
How the skills commit, close issues and handle teams and pull requests: [workflow.md](skills/backlog/references/workflow.md).

## Running the backlog unattended

`/starting-block:run` works the ready issues in order. Each issue gets a fresh subagent running `execute`.
The run stops after `--max N` issues attempted (default 5), when nothing ready is left, after two failures
in a row, or at once if your checks are already failing or its own setup breaks (a denied tool, a refused
push). It never does a person's steps, never pushes to your default branch, and never merges.

**It doesn't retry what it can't do.** When an issue needs a person, a decision, or a machine the run can't
reach, `execute` records why on the issue and puts it on hold (`hold:` in the file, or an `on-hold` label);
the next run skips it until someone clears the hold. Mark work that has to happen on a server or device
with `runs-on: host` and runs skip it from the start.

**Tell it how to check the repo** in `issues/.backlog.toml`, so it can tell a green tree from a red one:
`checks = ["npm test", "npm run lint"]`. Unattended, it runs no command that changes a running system
(`docker`, `systemctl`, `sudo`, deploys) unless the issue lists it under `## Allowed commands`.

- **Local:** commits each issue on the current branch. From a terminal or cron, in a dedicated clone (not on
  a production host): `claude -p "/starting-block:run --max 3" --permission-mode acceptEdits --allowedTools Bash Read Write Edit Glob Grep Skill Agent`.
  (Narrower Bash rules must cover your checks, `git` and `sb-backlog`, or issues fail on a permission denial.)
- **Pull requests:** `--pr` gives each issue its own branch and PR for you to review. Issues that already have
  an `issue-NNN-*` branch on the remote are skipped, so a daily run doesn't redo work awaiting review.
- **On a schedule:** copy [`skills/run/templates/backlog-run.yml`](skills/run/templates/backlog-run.yml) to
  `.github/workflows/`. It runs weekdays in PR mode with a cost cap and a pinned plugin version; the comments
  at its top cover the secrets. A runner can't reach your servers, so it suits repos whose work is in the
  repo; for an ops repo, it will only pick the repo-only issues.
- **GitHub Issues on a public repo:** anyone can open an issue, and its text becomes Claude's instructions.
  The run only works issues carrying a label you apply (`--label agent-ok`); only people with triage
  rights can add labels.

## Teams, pull requests and monorepos

- Close an issue on the same branch as its fix, and cite the PR (`Fixed in #123`): squash merges change
  commit hashes.
- If two branches add the same issue number, whoever merges second renumbers theirs. On an index
  conflict, take either side and run `sb-backlog index`.
- Add `owner: <name>` when you pick an issue up.
- Monorepo: one backlog at the root with `area:` per package, or one per package (`--dir packages/api/issues`).

## Using the scripts without Claude

The plugin puts two commands on Claude's shell PATH: `sb-backlog` and `sb-secret-scan`. They're thin
launchers for two standard-library Python scripts, which you can also copy into your repo for hooks or CI:

```bash
python scripts/backlog.py check            # fail if an issue file is malformed or the index is stale
python scripts/secret_scan.py --history    # fail if anything looks like a committed secret
```

`sb-backlog install-hook --with-secret-scan` does the copying for you and adds both checks to a
`.githooks/pre-commit` hook (it keeps anything already there). A CI step, after checking out with
`fetch-depth: 0`:

```yaml
- run: python scripts/backlog.py check && python scripts/secret_scan.py --history
```

## Where this came from

Extracted from the workflows of a self-hosted media-server repo that has run its work this way since
2026-09: an in-repo backlog with evidence-based issues, closing with the fixing commit, stripping secrets
before going public, and a generated page guarded by a check and a pre-commit hook.

Contributing: [CONTRIBUTING.md](CONTRIBUTING.md). License: [MIT](LICENSE).
