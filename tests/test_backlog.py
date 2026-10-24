import contextlib
import io
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import backlog  # noqa: E402


def remove_tree(path):
    """rmtree that also clears the read-only bits git puts on object files (Windows can't delete those)."""
    def retry(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=retry)


ISSUE = """---
status: {status}
priority: {priority}
area: docs
opened: 2026-09-14
{extra}---

# {title}

## Problem
Something is wrong.

## Done when
It isn't.
{tail}"""


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = backlog.main(list(argv))
    return code, out.getvalue()


class BacklogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.dir = Path(self.tmp) / "issues"
        run("--dir", str(self.dir), "init")

    def tearDown(self):
        remove_tree(self.tmp)

    def write(self, name, status="open", priority="P2", title="A thing", extra="", tail=""):
        (self.dir / name).write_text(ISSUE.format(status=status, priority=priority, title=title,
                                                  extra=extra, tail=tail))

    def check(self):
        return backlog.check(self.dir)

    def test_init_then_check_is_clean(self):
        self.assertEqual(self.check(), ([], []))

    def test_new_numbers_slugs_and_indexes(self):
        code, out = run("--dir", str(self.dir), "new", "--title", "The cache isn't cleared on deploy",
                        "--priority", "P1", "--area", "ci")
        self.assertEqual(code, 0)
        path = Path(out.strip())
        self.assertEqual(path.name, "001-cache-isnt-cleared-deploy.md")
        self.assertIn("| [001](001-cache-isnt-cleared-deploy.md) | P1 | The cache isn't cleared on deploy |",
                      (self.dir / "README.md").read_text())
        _, out = run("--dir", str(self.dir), "next")
        self.assertEqual(out.strip(), "002")
        errors, warnings = self.check()
        self.assertEqual(errors, [])

    def test_close_sets_date_resolution_and_index(self):
        self.write("001-thing.md")
        run("--dir", str(self.dir), "index")
        code, _ = run("--dir", str(self.dir), "close", "1", "--date", "2026-09-20", "--resolution", "Fixed in abc123.")
        self.assertEqual(code, 0)
        text = (self.dir / "001-thing.md").read_text()
        self.assertIn("status: closed\nclosed: 2026-09-20\n", text)
        self.assertTrue(text.rstrip().endswith("## Resolution\nFixed in abc123."))
        self.assertIn("| P2 (closed) |", (self.dir / "README.md").read_text())
        self.assertEqual(self.check(), ([], []))

    def test_writes_lf_line_endings(self):
        run("--dir", str(self.dir), "new", "--title", "Line endings", "--priority", "P3")
        for f in self.dir.glob("*.md"):
            self.assertNotIn(b"\r\n", f.read_bytes(), f.name)

    def test_reads_crlf_files(self):
        self.write("001-thing.md")
        crlf = (self.dir / "001-thing.md").read_bytes().replace(b"\n", b"\r\n")
        (self.dir / "001-thing.md").write_bytes(crlf)
        run("--dir", str(self.dir), "index")
        self.assertEqual(self.check(), ([], []))

    def test_stale_index_is_an_error(self):
        self.write("001-thing.md")
        errors, _ = self.check()
        self.assertTrue(any("index is out of date" in e and "missing 001" in e for e in errors), errors)

    def test_index_preserves_surrounding_readme_text(self):
        readme = self.dir / "README.md"
        readme.write_text("# Issues\n\nIntro.\n\n| # | Priority | Issue |\n|---|---|---|\n| [009](gone.md) | P1 | Old |\n\nFooter.\n")
        self.write("001-thing.md")
        run("--dir", str(self.dir), "index")
        text = readme.read_text()
        self.assertIn("Intro.", text)
        self.assertIn("Footer.", text)
        self.assertNotIn("Old", text)
        self.assertIn("| [001](001-thing.md) | P2 | A thing |", text)

    def test_field_errors(self):
        self.write("001-a.md", status="done", priority="high")
        self.write("002-b.md", status="closed")
        self.write("003-c.md", extra="depends: 042\n")
        (self.dir / "4-Bad Name.md").write_text("x")
        run("--dir", str(self.dir), "index")
        errors, warnings = self.check()
        joined = "\n".join(errors)
        self.assertIn("status `done`", joined)
        self.assertIn("priority `high`", joined)
        self.assertIn("002-b.md: closed, but has no `closed:` date", joined)
        self.assertIn("depends on 042", joined)
        self.assertIn("4-Bad Name.md: filename", joined)
        self.assertIn("002-b.md: closed without a `## Resolution`", "\n".join(warnings))

    def test_duplicate_numbers(self):
        self.write("001-a.md")
        self.write("001-b.md")
        errors, _ = self.check()
        self.assertTrue(any("number 001 is used by" in e for e in errors), errors)

    def test_list_json_readiness(self):
        self.write("001-a.md", priority="P3")
        self.write("002-b.md", priority="P1", extra="depends: 001\n")
        self.write("003-c.md", priority="P2", tail="\n## Needs the account holder\nTurn on billing.\n")
        code, out = run("--dir", str(self.dir), "list", "--json")
        data = {d["number"]: d for d in json.loads(out)}
        self.assertEqual([d["number"] for d in json.loads(out)], ["002", "003", "001"])
        self.assertTrue(data["001"]["ready"])
        self.assertEqual(data["002"]["open_depends"], ["001"])
        self.assertFalse(data["002"]["ready"])
        self.assertEqual(data["003"]["needs_human"], ["Needs the account holder"])
        self.assertFalse(data["003"]["ready"])

    def test_needs_section_done_when_all_ticked(self):
        self.write("001-a.md", tail="\n## Needs the account holder\n- [x] Turn on billing.\n- [ ] Add a card.\n")
        self.write("002-b.md", tail="\n## Needs the account holder\n- [x] Turn on billing.\n- [X] Add a card.\n")
        _, out = run("--dir", str(self.dir), "list", "--json")
        data = {d["number"]: d for d in json.loads(out)}
        self.assertFalse(data["001"]["ready"])
        self.assertTrue(data["002"]["ready"])
        self.assertEqual(data["002"]["needs_human"], [])

    def test_missing_done_when_warns(self):
        (self.dir / "001-a.md").write_text("---\nstatus: open\npriority: P2\nopened: 2026-01-01\n---\n\n# A\n\n## Problem\nx\n")
        run("--dir", str(self.dir), "index")
        errors, warnings = self.check()
        self.assertEqual(errors, [])
        self.assertIn("no `## Done when`", warnings[0])

    def test_check_exit_codes(self):
        self.assertEqual(run("--dir", str(self.dir), "check")[0], 0)
        (self.dir / "001-a.md").write_text("---\nstatus: open\npriority: P2\nopened: 2026-01-01\n---\n\n# A\n")
        run("--dir", str(self.dir), "index")
        self.assertEqual(run("--dir", str(self.dir), "check")[0], 0)
        self.assertEqual(run("--dir", str(self.dir), "check", "--strict")[0], 1)


if __name__ == "__main__":
    unittest.main()
