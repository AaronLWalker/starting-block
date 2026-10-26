# Recording what you learned

The repo's instructions file (`CLAUDE.md`, `AGENTS.md` or similar) is what the next session starts from.
Add a fact there when someone would otherwise rediscover it the hard way. When `CLAUDE.md` is a symlink to
`AGENTS.md` or says that file is canonical, edit `AGENTS.md`; when a directory has its own instructions
file, a fact about that directory goes there.

**Worth recording:** a setting that's easy to undo by accident and what breaks when it is; a gotcha that
took real time to find; the command that shows something is still right; a rule, with its reason.

**Not worth recording:** what the diff or `git log` already says; a log of today's work (the issue's
Resolution holds that); anything you haven't confirmed.

Put it in the section it's about, not at the end. Lead with the rule, then why it matters and the symptom
someone would search for, the date you verified it, and a check command:

```markdown
**Run the test suite with `TZ=UTC`.** Verified 2026-09-14.
- Why: date fixtures assume UTC; on a machine in another time zone, 6 tests in `tests/test_reports.py`
  fail with off-by-one-day errors that look like real bugs.
- Check: `TZ=UTC pytest tests/test_reports.py` passes.
```

When a fact changes, edit the old entry; don't add a second one that contradicts it. Reasoning that
argues for a decision belongs in the repo's decision record (`docs/adr/`), cited from the instructions
by number, so a correction lands in one place.

If a script could catch the mistake, a check beats a fact: propose one (`.backlog.toml` `checks`, a hook,
or the `drift-guard` skill) instead of, or as well as, writing it down.
