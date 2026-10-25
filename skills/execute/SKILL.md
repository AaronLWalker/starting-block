---
name: execute
description: Work one issue from the backlog (in-repo files or GitHub Issues) through to done. Confirms it's ready, makes the smallest change that meets its "Done when", verifies, commits, and closes the issue citing the commit or PR. Use for "work on issue 12", "fix the next backlog issue", "do the top P1 from issues/", "pick something off the backlog and do it".
argument-hint: "<issue number | next>"
---

# Execute an issue

Read `${CLAUDE_PLUGIN_ROOT}/skills/backlog/references/workflow.md` first: it covers the repo's rules,
commits, and closing through a pull request.

## 1. Pick it

A number: use it. "Next" or nothing: if the `plan` skill ran in this conversation, take its first
"Next up". Otherwise take the first issue from `sb-backlog list --json` with `"ready": true` that doesn't
need the person, and say which one and why.

## 2. Check it's ready

Stop (see "When you stop") without starting, if:
- it has no **Done when** you can run (suggest the `refine` skill);
- an issue in `depends:` is still open;
- a `## Needs` checklist has unticked boxes, or the work needs admin rights, credentials, a decision, or a
  machine or service this session can't reach (`unreachable` in `sb-backlog list --json`). Never do their
  steps or work around them;
- it's on `hold` (someone has to clear the reason first).

If the problem is already gone, close the issue with that evidence instead.

## 3. Do it

1. Follow the repo's rules and its protected list (workflow.md). A command that changes something outside
   the working tree (restart, deploy, migration, install, a write to shared storage or a remote) needs the
   user's say-so for this issue, showing the exact command; the repo's docs showing it as an example
   isn't enough. **Unattended** (under `run`, or no one to ask): never run such commands at all (`docker`,
   `systemctl`, `sudo`, `kubectl`, deploy scripts, writes outside the repo) unless the issue has an
   `## Allowed commands` section listing them; stop instead. Follow the repo's branch convention.
2. **Reproduce** the problem first: a failing test, the error, the wrong value. If it doesn't reproduce,
   stop: the issue needs refining.
   Asked for a pull request (or run in PR mode): first create `issue-NNN-<slug>` from the up-to-date
   default branch.
3. Make the **smallest change** that meets Done when. Found something else? Open a new issue with the
   `backlog` skill and carry on.
4. Keep derived files in step: edit a generated file's source and rerun its generator; fix docs your
   change made untrue.

## 4. Verify

Run every Done when check, and the repo's checks (`sb-backlog run-checks`, or as workflow.md says). If
the repo has a `.githooks/` hook that this clone hasn't enabled (`sb-backlog check` warns), run what it
runs yourself before committing. Never bypass a hook with `--no-verify`. If a check fails and the fix is
outside the issue, stop with the output.

## 5. Commit and close

1. Commit the fix in the repo's style: the subject says what changed, the body says why and names the issue.
2. `sb-backlog close NNN --resolution "<what fixed it> (<hash>)"`; in a PR workflow, name the PR instead
   (workflow.md). In GitHub Issues, put `Fixes #N` in the commit or PR instead (github.md).
   Mention any follow-up issue. Run `sb-backlog check`, then commit the issue file and index.
   In PR mode: push the branch and open the PR first (what changed, how it was verified, `Fixes #N`), then
   close the file-backlog issue citing the PR number, commit, and push again.
3. If you learned something the next person will need (a gotcha, a verify command), add it to the repo's
   instructions file: see `${CLAUDE_SKILL_DIR}/references/recording-facts.md`.

## When you stop

Whenever you stop without finishing:
1. Undo your own uncommitted edits for this issue (`git restore <files>`, delete files you created), so
   the next issue starts from a clean tree. Never touch changes that were there before you started.
2. Decide whether the reason will still be true next time:
   - **Yes** (it needs the person, a place this session can't reach, a decision, refining, or it doesn't
     reproduce): record it on the issue so nobody retries it blindly. Add `## Progress (YYYY-MM-DD)` with
     what you found; add an unticked `## Needs <who>` checklist for person steps, or `runs-on: <place>`
     (`sb-backlog set N runs-on=host`) for unreachable work; then `sb-backlog hold N --reason "..."`.
     Commit just the issue file (`issues: hold NNN`). This is `stopped`.
   - **No** (a check failed for reasons outside the issue, a tool or command was denied, a push or PR
     failed): change nothing on the issue; it's `failed`, and the reason goes in your report.
3. GitHub Issues: the same, as a comment plus the `on-hold` label (and `runs-on:<place>` label).
   PR mode with a file backlog: never commit to the default branch. Put the hold on a branch
   `issue-NNN-hold` from the default branch, push it, and open a PR titled `Hold issue NNN: <reason>`;
   merging it records the hold.

## Report

The issue, files changed, the checks and their results, the commits or PR, and anything left. End with
one line the `run` skill can read:
`RESULT: done|stopped|failed | <issue> | <commit hash or PR URL, or -> | <one-line reason>`

`stopped` means the issue is now held for a reason of its own; `failed` means something outside the issue
went wrong and the run's setup may need fixing.
