# Changelog

## Unreleased

- `scripts/secret_scan.py` ([#8](https://github.com/AaronLWalker/starting-block/issues/8)):
  - `--history` streams `git log` instead of reading it into memory, and reports the line number in each
    commit. History findings name the commit by 12 hex digits instead of 7.
  - `--since <rev>` scans only commits not reachable from `<rev>` (plus the working tree).
  - `--baseline <file>` and `--write-baseline <file>`: accept triaged findings by location, rule and a
    SHA-256 of the value; the value itself is never written.
  - Runs `gitleaks` too when it's on PATH (not with `--staged`; `--no-gitleaks` turns it off) and merges its
    findings as `gitleaks:<RuleID>`. A gitleaks failure is a warning.
  - New rules: Azure storage account keys, GCP service-account key files (reported once, not also as a
    private key), npm, PyPI and Hugging Face tokens, Discord and Telegram bot tokens.
  - Each finding in `--json` output has a `sha256` of its value.

## 0.1.0 (2026-10-24)

First release. Extracted from the workflows of a self-hosted media-stack repo.

- Skills: `backlog`, `plan`, `refine`, `execute`, `secrets-audit`, `drift-guard`.
- `scripts/backlog.py`: init, list, next, new, close, index, check for an in-repo Markdown backlog.
- `scripts/secret_scan.py`: pattern scan of tracked files, staged changes or full history, redacted output.
- `bin/sb-backlog` and `bin/sb-secret-scan`: launchers that find Python 3.9+ as `python3`, `python` or the
  Windows `py` launcher, with `.cmd` twins for PowerShell and cmd.
- Windows support: UTF-8 console output, LF-only writes, `.gitattributes`, CI on Windows and macOS.
- Eval suite under `evals/` for `claude plugin eval`.
