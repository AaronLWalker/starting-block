# Issue format

## File

`issues/NNN-short-slug.md`: a three-digit number (never reused) and a few lowercase words.
`issues/README.md` holds the conventions and an index table that `sb-backlog index` regenerates:

```markdown
| # | Priority | Issue |
|---|---|---|
| [001](001-login-fails-after-password-reset.md) | P1 (closed) | Login fails after a password reset |
| [004](004-api-docs-out-of-sync-with-routes.md) | P2 | API docs list routes that no longer exist |
```

Text around the table is kept; only the table is rewritten.

## Frontmatter

```yaml
---
status: open          # open | closed
closed: 2026-09-20    # required when closed, absent when open
priority: P2          # P1 | P2 | P3
area: api, docs       # optional, comma-separated, the repo's own words (in a monorepo: the package)
opened: 2026-09-14
depends: 004, 012     # optional; these must close first
owner: sam            # optional; who's working on it
runs-on: host         # optional; where the work must happen, if not in the repo (see workflow.md)
hold: 2026-10-25 needs the SMTP password   # optional; set by `sb-backlog hold` when an agent stopped
---
```

One `key: value` per line. Lists are comma-separated on one line; `check` rejects YAML lists and indented
lines.

| Priority | Meaning |
|---|---|
| **P1** | Fix soon: a real risk (data loss, security, outage) or it blocks other work. |
| **P2** | Worth doing: a visible defect or a clear improvement. |
| **P3** | Tidy-up: cleanup, docs, small inconsistencies. |

`issues/.backlog.toml` (optional; reading it needs Python 3.11 or later) tunes the backlog:

```toml
priorities = ["P0", "P1", "P2"]   # highest first (default P1, P2, P3)
reachable = ["host"]               # places this repo's sessions can reach (default: only the repo)
checks = ["python3 -m pytest -q", "python3 scripts/landing-page.py check --offline"]  # sb-backlog run-checks
```

It also takes `statuses` (must include `"open"` and `"closed"`) and `done_sections` (heading prefixes that
count as Done when). Keys it leaves out keep their defaults.

## Body

A `# Title` line, then the sections that apply, in this order:

| Section | When | What goes in it |
|---|---|---|
| `## Problem` | always | What's wrong and the evidence: file and line, the error text, the command and its output, when it was seen. |
| `## Proposed fix` | always | Concrete steps naming the files or settings. With several options, number them and recommend one. |
| `## Needs <someone>` | if any | Steps only a person can take, as a checklist (`- [ ] ...`). Agents stop here until every box is ticked (`- [x]`). |
| `## Done when` | always | Observable checks: a command and what it prints, a test that passes, a page that loads. Not "it works". |
| `## Allowed commands` | if any | Exact commands that change a running system (a restart, a deploy) which an unattended run may use for this issue. Nothing else of that kind runs unattended. |
| `## Verify` | risky changes | How to confirm the change in the running system. |
| `## Roll back` | risky changes | The exact steps to undo it. |
| `## Progress (YYYY-MM-DD)` | multi-session work | Dated facts: what's done, what was found, what's left. |
| `## Resolution` | when closed | What fixed it, and the commit hash or pull request; where any leftover went (another issue number). |

`Needs` steps are anything that takes the person's account, money, credentials, physical access, admin
rights (`sudo`, a production console), their own devices, a machine or service the agent's session can't
reach, or a decision that's theirs to make.

## Writing it

- **Title** says what's wrong in plain words, so the index reads as a list of problems:
  "Login fails after a password reset", not "Auth improvements".
- **State facts, with dates.** "On 2026-09-14 CI failed with `ECONNRESET` in `test_upload`", not "uploads
  seem flaky". Say what you couldn't check.
- **Quote the evidence**: the error line, the config value, the count. Link other issues by number.
- **Keep it short.** Bullets over paragraphs. No changelog, no hedging.
- **No secrets.** Never paste a key, password, token or cookie into an issue. Name the file it lives in.

## Example

```markdown
---
status: open
priority: P2
area: auth
opened: 2026-09-14
---

# Login fails after a password reset

## Problem
After resetting a password, the first login returns 401. On 2026-09-14, `POST /login` logged
`session token expired` for 3 users. `reset_password()` in `src/auth/reset.py:41` rotates the user's
token secret but leaves the old session cookie, and `login()` checks that cookie before the password.

## Proposed fix
- Clear the session cookie in `reset_password()`.
- Add a test: reset, then log in with the new password.

## Done when
- `pytest tests/test_auth.py -k reset` passes, including the new test.
- Logging in right after a reset on the staging site succeeds.
```

## Without the script

If neither `sb-backlog` nor Python is available, do the steps by hand: the next number is one more than
the highest `NNN-` file; the file follows the example above; the index row is
`| [NNN](NNN-slug.md) | P2 | Title |`, with `P2 (closed)` once it's closed, sorted by number.
