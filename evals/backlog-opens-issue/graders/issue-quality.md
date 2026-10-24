---
type: llm
focus: trace
---

Judge the issue file Claude wrote under issues/ (look for the Write or Edit call that creates issues/002-*.md).

PASS if all hold: it has frontmatter with `status: open`, a priority P1/P2/P3 and an `opened:` date; a
`# Title` that states the problem plainly; a Problem section that points at the cause in `src/export.py`
(the row is joined with "," and fields aren't quoted or escaped); a Proposed fix (e.g. use the csv module);
and a `## Done when` with an observable check (such as a test with a comma in the name passing).
Also, issues/README.md's index must have been updated with a row for 002.
FAIL if any of these are missing, or if Claude changed src/export.py.
