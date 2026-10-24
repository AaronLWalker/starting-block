# Security

## Reporting a problem

Report security problems privately through GitHub: **Security → Report a vulnerability** on this repo.
Please don't open a public issue for them. You'll get a reply within a week.

Examples worth reporting:
- a skill that could lead Claude to leak a secret (print it, commit it, or send it somewhere);
- a way for repository content (an issue file, a commit message) to make the skills run unintended
  commands;
- `secret_scan.py` printing a secret's value instead of redacting it.

A secret the scanner *misses* is a detection gap, not a vulnerability. Open a normal issue with the
"Secret scanner miss or false positive" template, and never include the real secret.

## What the plugin does with your data

- The scripts run locally and make no network calls.
- `secret_scan.py` hands off to `gitleaks` only if you've installed it, and that also runs locally.
- The skills tell Claude never to print, commit or paste secret values. Verifying a secret with its
  provider (e.g. trufflehog's `--only-verified`) sends it over the network, so the skills don't do it.
