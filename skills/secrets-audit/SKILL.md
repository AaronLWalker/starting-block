---
name: secrets-audit
description: Find committed secrets (API keys, passwords, tokens, private keys, app configs that hold them) in a git repo's files and history, and fix them safely. Use for "scan this repo for secrets", "is this safe to make public?", "did I commit a key?", or before a repo's first push to a public remote.
argument-hint: "[path to repo]"
---

# Secrets audit

Scanner: `sb-secret-scan` (on the shell's PATH; it finds Python itself). If that isn't found, run
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/secret_scan.py"` (on Windows, `py -3` in place of `python3`).
Without Python, use `gitleaks` if it's installed, or search with `git grep` and `git log -p -G '<pattern>'`.

```bash
sb-secret-scan               # tracked files in the working tree
sb-secret-scan --history     # also every line ever added, on every branch and tag
sb-secret-scan --staged      # only what's staged (for a pre-commit hook)
```

It prints matches redacted. **Never print, paste or commit a secret's value**: not in chat, an issue, a
commit message or a PR. Refer to it by file, line and kind.

## 1. Scan

1. `sb-secret-scan --history`. If `gitleaks` is installed, also run `gitleaks detect --redact`: patterns
   miss things. (Skip trufflehog's `--only-verified`: verifying sends the secret to its provider.)
2. Read the `git ls-files` list for files that hold secrets by nature: app config the app writes itself,
   `.env` files, key files, database dumps, backups, exported sessions.
3. Check `.gitignore` covers `.env`, key files and those configs.

## 2. Triage

Open each finding at its line, without echoing the value. **Real**: a live credential, or one that ever
was. **False positive**: suppress it with `secret-scan: ignore` on the line, or a path glob in
`.secretscanignore`, so the next scan is clean.

## 3. Fix, in this order

1. **Rotate.** A secret that has reached any remote, or might have, is compromised: forks, clones and
   caches keep it. If only the owner can revoke it, list each one and where to rotate it as a
   `Needs <owner>` step.
2. **Untrack the file; don't redact it.** `git rm --cached <file>`, and add it to `.gitignore` with a
   comment. An app that rewrites its config puts the secret back on its next save.
3. **Read secrets at runtime** from the ignored file or the environment. Add a `.env.example` with names
   and no values.
4. **Document** the settings the untracked file held (without values) if they matter.
5. Commit, and rerun `sb-secret-scan`: the working tree must be clean.

## 4. History

If `--history` still finds real secrets and the repo is or will be shared, the history has to be
rewritten. That's destructive and changes every later commit hash, so **ask first**. Then:

1. Back up: `git bundle create ../<repo>-pre-rewrite-<YYYY-MM-DD>.bundle --all` (write the date out).
   The bundle still holds the secrets: keep it local.
2. Rewrite with `git filter-repo` (`pip install git-filter-repo` if it's missing):
   `git filter-repo --invert-paths --path <file>` drops a file everywhere;
   `git filter-repo --replace-text <expressions-file>` replaces values.
3. Rerun `sb-secret-scan --history` until it's clean.
4. Publishing the result needs a force-push of every branch and tag, and every other clone has to
   re-clone. That's the owner's call: describe it and wait.
5. Note the rewrite date in the repo's docs, since older commit hashes cited anywhere no longer exist.

## 5. Prevent and report

Offer a pre-commit check. Copy `${CLAUDE_PLUGIN_ROOT}/scripts/secret_scan.py` into the repo so the hook
doesn't depend on this plugin, and have the hook run `<python> scripts/secret_scan.py --staged`.

Report a table of findings (where, kind, real or false positive, what you did), then what's left for the
owner: rotations, the history rewrite and force-push, anything you couldn't check.
