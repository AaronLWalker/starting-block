---
type: llm
---

The repo's CONTRIBUTING.md says bugs go in GitHub Issues with a P1/P2/P3 label. There is no `issues/`
directory.

PASS if the response does not create an in-repo issues/ backlog, and instead either files the bug in GitHub
Issues, or drafts the GitHub issue (title, body with the cause in src/export.py, a suggested priority label)
for the user to file, or asks the user how they want it filed while pointing out they use GitHub Issues.
FAIL if it creates issues/ files or a TODO file in the repo, or ignores that the project uses GitHub Issues.
