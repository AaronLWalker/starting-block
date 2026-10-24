---
name: secrets-audit
description: Check a git repo for committed secrets (API keys, passwords, tokens, private keys, app configs holding them) in the current files and in all history, before it's pushed or made public, and fix what's found in the safe order. Rotate, untrack, gitignore, read at runtime, and rewrite history only with the owner's go-ahead. Use for "scan for secrets", "is this safe to make public?", "did I commit a key?", "prepare this repo for open source", or before the first push to a new remote.
argument-hint: "[path to repo]"
---

# Secrets audit

Scanner: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/secret_scan.py"` (called `secret_scan.py` below).
It needs only Python 3 and git, and prints matches redacted.

```bash
secret_scan.py               # tracked files in the working tree
secret_scan.py --history     # also every line ever added, on every branch and tag
secret_scan.py --staged      # only what's staged (for a pre-commit hook)
secret_scan.py --json
```

**Never print, paste or commit a secret's value**: not in chat, an issue, a commit message or a PR. Refer
to it by file, line and kind.

## 1. Scan

1. `secret_scan.py --history`. If `gitleaks` or `trufflehog` is installed, run it too
   (`gitleaks detect --redact`, `trufflehog git file://. --only-verified`). Patterns miss things.
2. Look beyond the patterns. `git ls-files` and read the list for files that hold secrets by nature:
   app config written by the app itself (`config.xml`, `settings.json`, `*.db`), `.env` files, key files,
   database dumps, backups, browser or session exports, `docker-compose.override.yml`.
3. Check `.gitignore` covers `.env`, key files, and each app config you found.

## 2. Triage

For each finding, open the file at that line (don't echo the value) and decide:

- **Real**: a live credential, or one that ever was.
- **False positive**: a placeholder, a test fixture, a variable name. Suppress it with
  `secret-scan: ignore` on the line, or a path glob in `.secretscanignore`, so the next scan is clean.

## 3. Fix, in this order

1. **Rotate.** Any secret that has reached a remote, or might have, is compromised: forks, clones and
   caches keep it after history is rewritten. Revoke and reissue it. If only the owner can (it's their
   account), list each one, where it's used, and where to rotate it, as a `Needs <owner>` step.
2. **Untrack the file; don't redact it.** `git rm --cached <file>`, then add it to `.gitignore` with a
   comment saying why. A config file the app rewrites will get the secret back the next time it saves,
   so redacting it in place only works until then.
3. **Read secrets at runtime.** Code and scripts read keys from the ignored file or the environment, never
   from a constant. Add a `.env.example` (names, no values) if the project uses env files.
4. **Keep the knowledge.** If the untracked config held settings worth keeping, document them (without
   values) in the repo's docs, so untracking it doesn't lose them.
5. **Commit** the untracking and ignore rules. Rerun `secret_scan.py`: the working tree must be clean.

## 4. History

If `--history` still finds real secrets and the repo is, or will be, shared beyond its owner, the history
has to be rewritten. This is destructive and changes every later commit hash, so **ask first** and
explain the consequences. Then:

1. Back up: `git bundle create ../<repo>-pre-rewrite-$(date +%F).bundle --all`. It still holds the
   secrets: keep it local, never push it or put it in the repo.
2. Rewrite with `git filter-repo` (preferred over `filter-branch`):
   `git filter-repo --invert-paths --path <file>` to drop a file everywhere, or
   `git filter-repo --replace-text <expressions-file>` to replace values.
3. Rerun `secret_scan.py --history` until it's clean.
4. Pushing needs `--force` to every branch and tag, and every other clone must re-clone. That's the
   owner's call; describe it and wait.
5. Old hashes cited in docs or issues now point nowhere. Note the rewrite date in the repo's docs so
   readers know hashes before it changed.

## 5. Prevent

Offer to add the scanner to the repo's pre-commit hook or CI:
`python3 path/to/secret_scan.py --staged || exit 1`. Copy the script into the repo (e.g. `scripts/`) so the
hook doesn't depend on this plugin being installed.

## 6. Report

A table of findings: where, kind, real or false positive, what you did. Then what's left for the owner:
rotations, the history rewrite and force-push, anything you couldn't check.
