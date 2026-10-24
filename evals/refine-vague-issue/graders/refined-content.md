---
type: llm
focus:
  source: file
  path: issues/001-export-is-broken.md
---

Facts: src/export.py has no email validation and is about 10 lines long, so "line 40" and "email validation"
are wrong. The real cause is that `to_csv` joins fields with "," without quoting, so a name containing a
comma shifts the columns (NOTES.md has the support ticket).

PASS if the refined issue: corrects or removes the wrong claim about email validation / line 40; names the
real cause (unquoted comma-joined fields in to_csv); proposes a concrete fix (e.g. the csv module or proper
quoting); and has a Done when that can be checked (e.g. a test with a comma in the name passes, or a
specific command's output).
FAIL if it keeps the email-validation claim, doesn't identify the comma/quoting cause, or the Done when is
vague ("export works").
