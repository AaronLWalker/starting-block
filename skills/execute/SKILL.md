---
name: execute
description: Work one issue from the backlog (in-repo files or GitHub Issues) through to done. Confirms it's ready, makes the smallest change that meets its "Done when" within its Scope, verifies, commits, has the change reviewed independently, and closes the issue citing the commit or PR. Use for "work on issue 12", "fix the next backlog issue", "do the top P1 from issues/", "pick something off the backlog and do it".
argument-hint: "<issue number | next>"
---

# Execute an issue

Read `${CLAUDE_PLUGIN_ROOT}/skills/backlog/references/workflow.md` first: it covers the repo's rules,
scope, commits, and closing through a pull request.

## 1. Pick it

A number: use it. "Next" or nothing: if the `plan` skill ran in this conversation, take its first
"Next up". Otherwise take the first issue from `sb-backlog list --json` with `"ready": true` that doesn't
need the person, and say which one and why.

## 2. Check it's ready

Stop (see "When you stop") without starting, if:
- it has no **Done when** you can run (suggest the `refine` skill);
- it has an `## Investigate` section: the cause isn't known yet, so it needs `refine`, not a fix;
- an issue in `depends:` is still open;
- a `## Needs` checklist has unticked boxes, or the work needs admin rights, credentials, a decision, or a
  machine or service this session can't reach (`unreachable` in `sb-backlog list --json`). Never do their
  steps or work around them;
- it's on `hold` (someone has to clear the reason first);
- it's too big for one session, review included (suggest `refine` to split it).

If the problem is already gone, close the issue with that evidence instead. If it has an `## Observe`
section, the fix has shipped: when it's due, do the passive check (workflow.md, "Waiting and
investigating") and close with what you saw, or report that it isn't due yet. Don't change code for it.

## 3. Do it

1. Follow the repo's rules and its protected list (workflow.md). A command that changes something outside
   the working tree (restart, deploy, migration, install, a write to shared storage or a remote) needs the
   user's say-so for this issue, showing the exact command; the repo's docs showing it as an example
   isn't enough. **Unattended** (under `run`, or no one to ask): never run such commands at all (`docker`,
   `systemctl`, `sudo`, `kubectl`, deploy scripts, writes outside the repo) unless the issue has an
   `## Allowed commands` section listing them; stop instead. Follow the repo's branch convention.
2. Note the commit you start from (`git rev-parse HEAD`): the **start**. Review and undo use it.
   Asked for a pull request (or run in PR mode): first create `issue-NNN-<slug>` from the up-to-date
   default branch; the start is its first commit.
3. **Reproduce** the problem first: a failing test, the error, the wrong value. If it doesn't reproduce,
   stop: the issue needs refining.
4. Make the **smallest change** that meets Done when, inside the issue's `## Scope` if it has one: only
   its paths, and nothing its `Not:` lines rule out. If the fix needs more than that, stop: the Scope goes
   back to `refine`. Found something else? Open a new issue with the `backlog` skill and carry on.
5. Keep derived files in step: edit a generated file's source and rerun its generator; fix docs your
   change made untrue.

## 4. Verify and commit

1. Run every Done when check, and the repo's checks (`sb-backlog run-checks`, or as workflow.md says). If
   the repo has a `.githooks/` hook that this clone hasn't enabled (`sb-backlog check` warns), run what it
   runs yourself before committing. Never bypass a hook with `--no-verify`. If a check fails and the fix is
   outside the issue, stop with the output.
2. `sb-backlog scope-check NNN` (GitHub: `--body <file>`) must pass; exit 3 means there's no Scope.
3. Commit the fix in the repo's style: the subject says what changed, the body says why and names the
   issue. Don't close the issue yet: this commit is the **candidate**.

## 5. Review

The change is reviewed by a session that didn't write it, before the issue closes or anything is pushed.
Skip this only if the user said to.

- **Under `run`** (it told you "review: by run"): end here with `RESULT: candidate`, the candidate's hash
  and the start. `run` reviews it and closes the issue.
- **With a subagent tool**: start two fresh subagents, each told to use the `starting-block:review` skill
  with the issue, the range `<start>..<candidate>`, and one pass: `--pass requirements` or
  `--pass standards`. Give them nothing else of yours: your account of the change is a claim for them to check.
- **Without one**: run the `review` skill yourself on that range, and say in your report that the review
  wasn't independent.

Both passes `pass`: go on to close. `blocked`: fix the findings that are within the issue (a new commit,
then verify again) and review again; style notes never block. Still blocked after the second review, or a
finding needs more than the issue allows: stop, with the findings as the reason.

## 6. Close

1. `sb-backlog close NNN --resolution "<what fixed it> (<hash>)"`; in a PR workflow, name the PR instead
   (workflow.md). In GitHub Issues, put `Fixes #N` in the commit or PR instead (github.md). Mention any
   follow-up issue, and keep the other records that track the issue in step (workflow.md, "Keep the records
   in step"). Run `sb-backlog check`, then commit the issue file, the index and those records.
2. In PR mode: push the branch and open the PR first (what changed, how it was verified, the review result,
   `Fixes #N`), then close the file-backlog issue citing the PR number, commit, and push again.
3. If you learned something the next person will need (a gotcha, a verify command), add it to the repo's
   instructions file: see `${CLAUDE_PLUGIN_ROOT}/skills/execute/references/recording-facts.md`.

## When you stop

Whenever you stop without finishing:
1. Undo your own work for this issue, so the next issue starts from a clean tree: uncommitted edits
   (`git restore <files>`, delete files you created), and commits you made since the start that aren't
   pushed (`git reset --keep <start>`). Never touch changes that were there before you started, or anything
   already pushed.
2. Decide whether the reason will still be true next time:
   - **Yes** (it needs the person, a place this session can't reach, a decision, refining, a wider Scope, or
     it doesn't reproduce, or review stayed blocked): record it on the issue so nobody retries it blindly.
     Add `## Progress (YYYY-MM-DD)` with what you found (for a review, its findings); add an unticked
     `## Needs <who>` checklist for person steps, or `runs-on: <place>` (`sb-backlog set N runs-on=host`) for
     unreachable work; then `sb-backlog hold N --reason "..."`. Commit just the issue file
     (`issues: hold NNN`). This is `stopped`.
   - **No** (a check failed for reasons outside the issue, a tool or command was denied, a push or PR
     failed): change nothing on the issue; it's `failed`, and the reason goes in your report.
3. GitHub Issues: the same, as a comment plus the `on-hold` label (and `runs-on:<place>` label).
   PR mode with a file backlog: never commit to the default branch. Put the hold on a branch
   `issue-NNN-hold` from the default branch, push it, and open a PR titled `Hold issue NNN: <reason>`;
   merging it records the hold.

## Report

The issue, files changed, the checks and their results, the review result, the commits or PR, and anything
left. End with one line the `run` skill can read:
`RESULT: done|candidate|stopped|failed | <issue> | <commit hash or PR URL, or -> | <one-line reason>`

`candidate` (only under `run`) means committed and verified, waiting for its review; put
`start=<hash>` in the reason. `stopped` means the issue is now held for a reason of its own; `failed`
means something outside the issue went wrong and the run's setup may need fixing.
