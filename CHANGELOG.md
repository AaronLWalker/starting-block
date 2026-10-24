# Changelog

## Unreleased

- GitHub Issues as the backlog: `sb-backlog github list` (via `gh api`, REST only) and `github from-json`
  give the same JSON as the file backlog; priority from `P1`–`P3` labels or a `Priority:` body line,
  `Depends on #N` lines, Needs checklists. Skills pick the backend from where the repo tracks work, and close
  GitHub issues through `Fixes #N`. See `skills/backlog/references/github.md`.

## 0.1.0 (2026-10-24)

First release. Extracted from the workflows of a self-hosted media-stack repo.

- Skills: `backlog`, `plan`, `refine`, `execute`, `secrets-audit`, `drift-guard`.
- `scripts/backlog.py`: init, list, next, new, close, index, check for an in-repo Markdown backlog.
- `scripts/secret_scan.py`: pattern scan of tracked files, staged changes or full history, redacted output.
- `bin/sb-backlog` and `bin/sb-secret-scan`: launchers that find Python 3.9+ as `python3`, `python` or the
  Windows `py` launcher, with `.cmd` twins for PowerShell and cmd.
- Windows support: UTF-8 console output, LF-only writes, `.gitattributes`, CI on Windows and macOS.
- Eval suite under `evals/` for `claude plugin eval`.
