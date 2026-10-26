# Contributing

Issues and pull requests are welcome.

## Layout

```
.claude-plugin/plugin.json        plugin manifest (bump "version" to ship an update)
.claude-plugin/marketplace.json   this repo is also its own marketplace
skills/<name>/SKILL.md            one directory per skill; references/ holds detail loaded on demand
skills/<name>/agents/openai.yaml  display name and short description for Codex's skill list
skills/backlog/references/        the issue format and the workflow rules shared by the backlog skills
scripts/                          stdlib-only Python used by the skills, runnable on its own
bin/                              launchers on Claude's shell PATH: sh for macOS/Linux/Git Bash, .cmd for Windows
tests/                            unittest tests for scripts/
evals/                            claude plugin eval cases (prompt.md, case.yaml, scaffold.sh, graders/)
```

## Rules

- **Scripts use the Python standard library only** and run on Python 3.9+. Users shouldn't need to
  install anything.
- **Skills call scripts through the `bin/` launchers** (`sb-backlog`, `sb-secret-scan`), never `python3`
  directly: Windows often has no `python3`. Give the `${CLAUDE_PLUGIN_ROOT}/scripts/...` form only as the
  fallback. Bundled files are referenced as `${CLAUDE_PLUGIN_ROOT}/...` paths, never `${CLAUDE_SKILL_DIR}`:
  other agents (Codex) set only `CLAUDE_PLUGIN_ROOT`.
- **Works on Windows.** Scripts write UTF-8 with LF endings and must not assume a POSIX shell. Shell
  snippets in skills avoid bash-only syntax such as `$(date ...)`. `.gitattributes` pins LF for `bin/sb-*`,
  `*.py` and `*.sh`, and CRLF for `*.cmd`; keep it that way.
- **Shared rules live in one place**: `skills/backlog/references/workflow.md` (commits, closing, teams,
  running the script). Don't restate them in each skill.
- **Keep each `SKILL.md` under 500 lines.** Put detail in `references/` and say when to read it.
- **A skill's `description` says what it does and when to use it**, with phrases people actually say.
  It decides whether Claude picks the skill up, so test it with an eval.
- **No real secrets anywhere**, including tests and eval fixtures: build fake tokens from pieces
  (`"ghp_" + "..."`) so scanners and GitHub push protection don't flag them.

## Develop locally

```bash
claude --plugin-dir .          # try the skills against any repo
```

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

The **Evals** workflow (`.github/workflows/evals.yml`) runs every case weekly and on demand (Actions → Evals →
Run workflow) once the repo has an `ANTHROPIC_API_KEY` secret; results are attached to the run.

Cases tagged `needs-bash` (backlog, execute, review, run, refine-splits-oversized, secrets-audit) need `--allow-tools Bash Write Edit`, and Bash in
evals runs inside Claude Code's sandbox: on Linux that needs `bubblewrap` and `socat`, and the run must not be
root (as root the sandbox mounts the workspace read-only and every command fails). Without Bash, run the
read-only cases: `--tag plan --tag retro --tag drift-guard --tag negative --case refine-vague-issue`.

## Releasing

1. Bump `version` in `.claude-plugin/plugin.json`. Installed copies only update when it changes.
2. Add a `CHANGELOG.md` entry.
3. Merge to `main` and tag `vX.Y.Z`.
