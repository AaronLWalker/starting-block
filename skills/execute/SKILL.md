---
name: execute
description: Work an issue from the in-repo backlog through to done. Confirms it's ready, respects the repo's safety rules, makes the smallest change that meets its "Done when", verifies it, commits, and closes the issue with a resolution naming the commit. Use for "work on issue 12", "fix the next issue", "do the top P1", "execute the plan", "pick something off the backlog".
argument-hint: "<issue number | next>"
---

# Execute an issue

Script: `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/backlog.py"` (called `backlog.py` below).
Issue format: [issue-format.md](${CLAUDE_PLUGIN_ROOT}/skills/backlog/references/issue-format.md).

## 1. Pick the issue

- Given a number, use it.
- Given "next" or nothing: `backlog.py list --json`, take the first issue with `"ready": true`
  (they're sorted P1 first). Tell the user which one and why in a line. If none is ready, say why
  (each one needs refinement, a person, or a blocker) and suggest the `plan` skill.

## 2. Check it's ready

Stop and report, rather than start, if any of these fail:

- It has a **Done when** with checks you can actually run. If not, refine it first (the `refine` skill),
  then continue if the result is ready.
- Every issue in `depends:` is closed.
- Every `## Needs ...` step is recorded as done. Those are a person's; never do them yourself or work
  around them.
- Its facts still hold: a quick read of the files and settings it names. If the problem is already gone,
  close the issue with the evidence instead.

## 3. Know the rules before touching anything

Read the repo's instructions (`CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`) for anything marked never,
must, or protected: services that mustn't restart, commands that must be scoped, files that are generated,
branches you mustn't push to, data you mustn't touch.

Before any command that changes something outside the working tree (restarts, deploys, migrations,
package installs, writes to shared storage, network calls that change remote state), check it against
those rules. If it isn't plainly allowed, stop and ask, showing the exact command.

Follow the repo's branch convention. If it reviews changes through pull requests and you're on the default
branch, create `issue-NNN-<slug>` first.

## 4. Do the work

1. **Reproduce first.** See the problem with your own eyes (a failing test, the error, the wrong value) and
   note the evidence. If it doesn't reproduce, stop: the issue needs refining.
2. **Make the smallest change that meets Done when.** Stay inside the issue. Something else broken or
   worth doing? Open a new issue for it with the `backlog` skill and carry on.
3. **Keep the repo's derived files in step.** If a file is generated, edit its source and run the
   generator. If the repo's docs state something your change made untrue, fix the docs in the same change.
4. **Long work:** at a natural stopping point, add `## Progress (YYYY-MM-DD)` to the issue: what's done,
   what you learned, what's left. Another session should be able to pick it up from there.

## 5. Verify

- Run every Done when check and keep the output.
- Run the repo's own checks: tests, linters, type checks, the generator's `check`, the pre-commit hook.
  Never bypass a hook (`--no-verify`) to get a commit through; fix what it reports.
- Re-read your diff as a reviewer would. Remove anything the issue didn't need.

If a check fails and you can't fix it within the issue's scope, stop and report with the output.

## 6. Commit and close

1. Stage only the files you meant to change (`git add <paths>`, not `git add -A`), then check `git status`:
   build output, caches and logs (`__pycache__/`, `node_modules/`, `*.log`) stay out of the commit, and if the
   repo doesn't ignore them yet, say so. Commit in the repo's style (`git log --oneline -15`). The subject says what changed;
   the body says why, and names the issue (e.g. "Closes issue 012" or "(issue 012)").
2. `backlog.py close NNN --resolution "<what fixed it, in a sentence> (<hash>)"`. Mention any follow-up issue
   you opened. Then `backlog.py check`.
3. Commit the issue file and index: `issues: close NNN (<short reason>)`.
4. If you learned a durable fact the next person will need (a gotcha, a setting that silently resets, a
   verify command), record it in the repo's instructions file: see
   [recording-facts.md](references/recording-facts.md).

Don't push, open a pull request, or deploy unless the user asked for it or the repo's instructions say
that's part of the job.

## 7. Report

A few lines: the issue, what changed (files), how you verified it (the checks and their results), the
commits, and anything left: follow-up issues, steps waiting on a person.
