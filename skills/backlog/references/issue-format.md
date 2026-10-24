# Issue format

## File

`issues/NNN-short-slug.md`: a three-digit number (never reused) and a few lowercase words.
`issues/README.md` holds the conventions and an index table that `backlog.py index` regenerates:

```markdown
| # | Priority | Issue |
|---|---|---|
| [001](001-docs-recommend-bare-compose-up.md) | P1 (closed) | Docs tell you to run a bare `docker compose up -d` |
| [006](006-weekly-upgrade-fails-silently.md) | P2 | Weekly upgrade+reboot fails silently |
```

Text around the table is kept; only the table is rewritten.

## Frontmatter

```yaml
---
status: open          # open | closed
closed: 2026-09-20    # required when closed, absent when open
priority: P2          # P1 | P2 | P3
area: docs, ci        # optional, comma-separated, the repo's own words
opened: 2026-09-14
depends: 004, 012     # optional; these must close first
---
```

| Priority | Meaning |
|---|---|
| **P1** | Fix soon: a real risk (data loss, security, outage) or it blocks other work. |
| **P2** | Worth doing: a visible defect or a clear improvement. |
| **P3** | Tidy-up: cleanup, docs, small inconsistencies. |

## Body

A `# Title` line, then the sections that apply, in this order:

| Section | When | What goes in it |
|---|---|---|
| `## Problem` (or `## Background`) | always | What's wrong and the evidence: file and line, the error text, the command and its output, when it was seen. |
| `## Proposed fix` | always | Concrete steps naming the files or settings. With several options, number them and recommend one. |
| `## Needs <someone>` | if any | Steps only a person can take: an account setting, a purchase, a credential, a decision that's theirs. Agents stop here. |
| `## Done when` (or `## Close when`) | always | Observable checks: a command and what it prints, a page that loads, a file that's gone. Not "it works". |
| `## Verify` | risky changes | How to confirm the change in the running system. |
| `## Roll back` | risky changes | The exact steps to undo it. |
| `## Progress (YYYY-MM-DD)` | multi-session work | Dated facts: what's done, what was found, what's left. |
| `## Resolution` | when closed | What fixed it and the commit hash(es); where any leftover went (another issue number). |

## Writing it

- **Title** says what's wrong in plain words, so the index reads as a list of problems:
  "Weekly upgrade+reboot fails silently", not "Cron improvements".
- **State facts, with dates.** "On 2026-09-14 the log showed `DownloadLimitExceeded`", not "it seems to be
  rate limited". Say what you couldn't check.
- **Quote the evidence**: the error line, the config value, the count. Link other issues by number.
- **Explain why** a step matters when it isn't obvious: what breaks without it.
- **Keep it short.** Bullets and tables over paragraphs. No changelog, no hedging, no filler.
- **No secrets.** Never paste a key, password, token or cookie into an issue, even redacted beyond recognition
  in a public repo. Name the file it lives in instead.

## Example

```markdown
---
status: open
priority: P2
area: host, monitoring
opened: 2026-09-14
---

# Weekly upgrade+reboot fails silently

## Problem
`/etc/cron.d/weekly-reboot` runs `apt-get update && apt-get dist-upgrade -y && /sbin/reboot`.
If an apt step fails (lock held, dpkg prompt), the chain stops: no reboot, a half-applied upgrade,
and nothing tells anyone. Cron output goes to root's mail, which nobody reads.

## Proposed fix
- Wrap the job in a script that mails on non-zero exit.
- Add `DEBIAN_FRONTEND=noninteractive` and `-o Dpkg::Options::=--force-confold`.
- Log to `/var/log/weekly-upgrade.log`.

## Done when
A deliberately failing apt step produces an email, and a normal run reboots.
```
