# Recording what you learned

The repo's instructions file (`CLAUDE.md`, `AGENTS.md` or similar) is what the next session starts from.
Add a fact there when someone would otherwise rediscover it the hard way.

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

When a fact changes, edit the old entry; don't add a second one that contradicts it.
