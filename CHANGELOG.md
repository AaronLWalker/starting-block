# Changelog

## Unreleased

- `backlog.py reopen N`: sets `status: open`, drops `closed:`, and renames `## Resolution` to
  `## Earlier resolution (date)`.
- `backlog.py set N key=value ...`: sets frontmatter fields (`key=` removes one) and re-indexes. Checks
  priorities and dates; status changes to or from closed go through `close` and `reopen`.
- `check` reports frontmatter it can't parse (indented lines, YAML lists, `key:` over a nested block)
  instead of misreading it.
- Optional `issues/.backlog.toml` sets `statuses`, `priorities` and `done_sections` (Python 3.11+).
- `backlog.py install-hook [--with-secret-scan]`: copies the scripts into `scripts/` and adds a marked
  block to `.githooks/pre-commit` that runs `check` (and `secret_scan.py --staged`), keeping what's there.
- `close`, `reopen` and `new` reject a `--date` that isn't YYYY-MM-DD.

## 0.1.0 (2026-10-24)

First release. Extracted from the workflows of a self-hosted media-stack repo.

- Skills: `backlog`, `plan`, `refine`, `execute`, `secrets-audit`, `drift-guard`.
- `scripts/backlog.py`: init, list, next, new, close, index, check for an in-repo Markdown backlog.
- `scripts/secret_scan.py`: pattern scan of tracked files, staged changes or full history, redacted output.
- `bin/sb-backlog` and `bin/sb-secret-scan`: launchers that find Python 3.9+ as `python3`, `python` or the
  Windows `py` launcher, with `.cmd` twins for PowerShell and cmd.
- Windows support: UTF-8 console output, LF-only writes, `.gitattributes`, CI on Windows and macOS.
- Eval suite under `evals/` for `claude plugin eval`.
