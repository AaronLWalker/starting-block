# Changelog

## 0.2.0 (2026-10-24)

**GitHub Issues as the backlog** ([#3](https://github.com/AaronLWalker/starting-block/issues/3))
- Repos that track work in GitHub Issues no longer need an `issues/` directory. `sb-backlog github list`
  (via `gh api`, REST only) and `github from-json` give the same JSON as the file backlog: priority from
  `P1`–`P3` labels or a `Priority:` body line, `Depends on #N` lines, Needs checklists. The skills pick the
  backend from where the repo tracks work, and close GitHub issues through `Fixes #N`
  (`skills/backlog/references/github.md`).

**backlog.py** ([#7](https://github.com/AaronLWalker/starting-block/issues/7))
- `reopen N`: `status: open`, drops `closed:`, renames `## Resolution` to `## Earlier resolution (date)`.
- `set N key=value ...`: sets frontmatter fields (`key=` removes one) and re-indexes, with validation.
- `install-hook [--with-secret-scan]`: copies the scripts into `scripts/` and adds a marked block to
  `.githooks/pre-commit` that runs `check` (and `secret_scan.py --staged`), keeping what's there.
- Optional `issues/.backlog.toml` sets `statuses`, `priorities` and `done_sections` (Python 3.11+).
- `check` reports frontmatter it can't parse (indented lines, YAML lists) instead of misreading it;
  `close`, `reopen` and `new` reject a malformed `--date`.

**secret_scan.py** ([#8](https://github.com/AaronLWalker/starting-block/issues/8))
- `--history` streams `git log` and reports line numbers; commits are named by 12 hex digits.
- `--since <rev>`, `--baseline <file>` and `--write-baseline <file>` (location, rule and a SHA-256 of the
  value; the value itself is never written). `--json` findings carry that `sha256`.
- Runs `gitleaks` too when it's on PATH (not with `--staged`; `--no-gitleaks` turns it off).
- New rules: Azure storage keys, GCP service-account files, npm, PyPI and Hugging Face tokens, Discord and
  Telegram bot tokens.

**Skills**
- plan and execute treat work needing a machine or service the session can't reach (a production host,
  `sudo`, a live service) as waiting on a person ([#4](https://github.com/AaronLWalker/starting-block/issues/4)).
- drift-guard ships a starter `templates/check_manifest.py` (build, check, `--offline`).

**Project**
- `SECURITY.md`, issue templates and a pull request template.
- Evals workflow, weekly and on demand ([#5](https://github.com/AaronLWalker/starting-block/issues/5)); new
  eval cases `backlog-respects-existing-tracker` and `plan-holds-person-steps`; execute must not `git add -A`.
- README states where the plugin runs: Claude Code on macOS, Linux and Windows, not claude.ai uploads.

## 0.1.0 (2026-10-24)

First release. Extracted from the workflows of a self-hosted media-stack repo.

- Skills: `backlog`, `plan`, `refine`, `execute`, `secrets-audit`, `drift-guard`.
- `scripts/backlog.py`: init, list, next, new, close, index, check for an in-repo Markdown backlog.
- `scripts/secret_scan.py`: pattern scan of tracked files, staged changes or full history, redacted output.
- `bin/sb-backlog` and `bin/sb-secret-scan`: launchers that find Python 3.9+ as `python3`, `python` or the
  Windows `py` launcher, with `.cmd` twins for PowerShell and cmd.
- Windows support: UTF-8 console output, LF-only writes, `.gitattributes`, CI on Windows and macOS.
- Eval suite under `evals/` for `claude plugin eval`.
