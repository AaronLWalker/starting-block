# Shared rules for the backlog skills

`backlog`, `plan`, `refine` and `execute` all follow these. Where the repo's own docs or history say
otherwise, follow the repo.

## Where the backlog lives

1. An `issues/` (or `backlog/`) directory at the git root: the file backlog. Everything below applies.
2. Otherwise, if the repo says it tracks work in GitHub Issues (README, CONTRIBUTING, `.github/ISSUE_TEMPLATE/`),
   or the user says so: GitHub Issues. Read `${CLAUDE_PLUGIN_ROOT}/skills/backlog/references/github.md`,
   which maps each step onto GitHub.
3. Anything else (another tracker, or nothing yet): ask before starting a file backlog.

## Running the script

Run `sb-backlog <command>`. The plugin puts it on the shell's PATH, and it finds Python itself (`python3`,
`python`, or the Windows `py` launcher). If `sb-backlog` isn't found, run the script directly:
`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/backlog.py" <command>` (on Windows, `py -3` in place of `python3`).
If Python isn't available at all, do the steps by hand: see "Without the script" in
`${CLAUDE_PLUGIN_ROOT}/skills/backlog/references/issue-format.md`, and say you did.

## Read the repo's rules first

Before changing anything, read the repo's instructions (`CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`,
`issues/README.md`). Note what's marked never, must or protected: services that mustn't restart, commands
that must be scoped, generated files, branches you mustn't push to.

## Is the problem still there?

To check whether an issue is stale or already fixed, read-only:

- `git log --oneline --since=<opened> -- <paths the issue names>`
- `git log --oneline --grep=<issue number>`
- `git log -S '<string from the issue>' --oneline`
- then look at the file, setting or test the issue describes.

## Who closes an issue

- **execute** closes the issue it was asked to work, once every Done when check passes. If the problem
  turns out to be already fixed, it closes the issue with that evidence.
- **plan** and **refine** never close issues on their own. They propose closing (as done or as a
  duplicate) with the evidence, and close only if the user agrees or asked them to groom the backlog.
- A closed issue that turns out not to be fixed is reopened with `sb-backlog reopen N`: it sets
  `status: open`, deletes `closed:`, and renames `## Resolution` to `## Earlier resolution (YYYY-MM-DD)`
  so the history stays readable.

## Commits

- **When.** `execute` commits its fix and the closing of the issue: that's its job. The other skills
  leave their changes in the working tree and say so, unless the user asked for a commit or the repo's
  instructions say backlog changes are committed as they happen.
- **What.** Stage the files you changed by name, never `git add -A`, and keep build output and caches out.
- **Messages**, unless `git log --oneline -- issues/` shows the repo uses another style:
  - `issues: open 016 <title>`
  - `issues: refine 014`
  - `issues: close 007 (<short reason>)`
  - `issues: triage (close 004, 009; reprioritize 012)`
- Never push, open a pull request or deploy unless the user asked for it.

## Teams and pull requests

- **Numbers.** Two branches can pick the same next number. Whoever merges second renumbers their
  still-unmerged issue (rename the file, fix `depends:` references) and runs `sb-backlog index`. That's the
  only time an issue is ever renumbered.
- **Index conflicts.** Don't hand-merge `issues/README.md`: take either side, then run `sb-backlog index`.
- **Closing with a PR.** Close the issue on the same branch as the fix, and have the Resolution name the
  pull request (`Fixed in #123`) instead of a commit hash: squash and rebase merges change hashes. The
  issue then reads as closed exactly when the PR merges.
- **Who's on it.** Add `owner: <name>` to the frontmatter when someone picks an issue up, so others skip it.
