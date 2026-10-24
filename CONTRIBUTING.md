# Contributing

Issues and pull requests are welcome.

## Layout

```
.claude-plugin/plugin.json        plugin manifest (bump "version" to ship an update)
.claude-plugin/marketplace.json   this repo is also its own marketplace
skills/<name>/SKILL.md            one directory per skill; references/ holds detail loaded on demand
scripts/                          stdlib-only Python used by the skills, runnable on its own
tests/                            unittest tests for scripts/
evals/                            claude plugin eval cases (prompt.md, case.yaml, scaffold.sh, graders/)
```

## Rules

- **Scripts use the Python standard library only** and run on Python 3.9+. Users shouldn't need to
  install anything.
- **Skills reference bundled files through `${CLAUDE_PLUGIN_ROOT}`** (or a relative link for files in the
  skill's own directory), never an absolute path.
- **Keep each `SKILL.md` under 500 lines.** Put detail in `references/` and say when to read it.
- **A skill's `description` says what it does and when to use it**, with phrases people actually say.
  It decides whether Claude picks the skill up, so test it with an eval.
- **No real secrets anywhere**, including tests and eval fixtures: build fake tokens from pieces
  (`"ghp_" + "..."`) so scanners and GitHub push protection don't flag them.

## Before opening a pull request

```bash
python3 -m unittest discover -s tests
python3 scripts/secret_scan.py --history
claude plugin validate . --strict
```

If you changed a skill, run its evals (they make real model calls):

```bash
claude plugin eval . --tag <skill> --runs 3 --scaffold --trust-plugin --allow-tools Bash Write Edit
```

Cases tagged `needs-bash` (backlog, execute, secrets-audit) need `--allow-tools Bash Write Edit`, and Bash in
evals runs inside Claude Code's sandbox: on Linux that needs `bubblewrap` and `socat`, and the run must not be
root (as root the sandbox mounts the workspace read-only and every command fails). Without Bash, run the
read-only cases: `--tag plan --tag refine --tag drift-guard --tag negative`.

## Releasing

1. Bump `version` in `.claude-plugin/plugin.json`. Installed copies only update when it changes.
2. Add a `CHANGELOG.md` entry.
3. Merge to `main` and tag `vX.Y.Z`.
