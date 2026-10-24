import contextlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import backlog  # noqa: E402


def remove_tree(path):
    """rmtree that also clears the read-only bits git puts on object files (Windows can't delete those)."""
    def retry(func, p, exc):
        if issubclass(exc[0], FileNotFoundError):
            return  # gone already, e.g. a lock file git's background maintenance just removed
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


def fails(*argv):
    """Run a command that should exit with an error; return the error message."""
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            backlog.main(list(argv))
        except SystemExit as e:
            return str(e.code)
    raise AssertionError("no error from {}".format(argv))


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

    def test_reopen_reverses_close_and_keeps_the_resolution(self):
        self.write("001-thing.md")
        run("--dir", str(self.dir), "close", "1", "--date", "2026-09-20", "--resolution", "Fixed in abc123.")
        code, _ = run("--dir", str(self.dir), "reopen", "1", "--date", "2026-10-01")
        self.assertEqual(code, 0)
        text = (self.dir / "001-thing.md").read_text()
        self.assertIn("---\nstatus: open\npriority: P2\n", text)
        self.assertNotIn("closed:", text)
        self.assertIn("## Earlier resolution (2026-10-01)\nFixed in abc123.", text)
        self.assertNotIn("## Resolution", text)
        self.assertIn("| [001](001-thing.md) | P2 | A thing |", (self.dir / "README.md").read_text())
        self.assertEqual(self.check(), ([], []))
        code, _ = run("--dir", str(self.dir), "close", "1", "--resolution", "Fixed in def456.")
        self.assertEqual(code, 0)
        self.assertEqual(self.check(), ([], []))

    def test_reopen_errors(self):
        self.write("001-thing.md")
        self.write("002-done.md", status="closed", extra="closed: 2026-09-20\n")
        self.assertIn("isn't closed (status: open)", fails("--dir", str(self.dir), "reopen", "1"))
        self.assertIn("No issue 009", fails("--dir", str(self.dir), "reopen", "9"))
        self.assertIn("YYYY-MM-DD", fails("--dir", str(self.dir), "reopen", "2", "--date", "1 Oct"))
        self.assertIn("status: closed", (self.dir / "002-done.md").read_text())

    def test_set_updates_removes_and_reindexes(self):
        self.write("001-a.md")
        self.write("002-b.md", extra="owner: kim\n")
        run("--dir", str(self.dir), "index")
        code, _ = run("--dir", str(self.dir), "set", "2", "priority=P1", "owner=", "depends=1", "area=api, docs")
        self.assertEqual(code, 0)
        text = (self.dir / "002-b.md").read_text()
        self.assertIn("priority: P1\narea: api, docs\nopened: 2026-09-14\n", text)
        self.assertIn("status: open\ndepends: 1\n", text)
        self.assertNotIn("owner", text)
        self.assertIn("| [002](002-b.md) | P1 | A thing |", (self.dir / "README.md").read_text())
        self.assertEqual(self.check(), ([], []))
        run("--dir", str(self.dir), "set", "1", "owner=sam", "owner=")
        self.assertNotIn("owner", (self.dir / "001-a.md").read_text())

    def test_set_rejects_bad_values(self):
        self.write("001-a.md")
        self.write("002-b.md", status="closed", extra="closed: 2026-09-20\n", tail="\n## Resolution\nDone.\n")
        run("--dir", str(self.dir), "index")
        before = (self.dir / "001-a.md").read_text()
        for pair, message in [
            ("priority=P9", "priority `P9` isn't one of P1, P2, P3"),
            ("priority=", "`priority:` is required"),
            ("status=closed", "`close 001` or `reopen 001`"),
            ("status=done", "status `done` isn't one of open, closed"),
            ("opened=2026-9-1", "YYYY-MM-DD"),
            ("opened=2026-02-30", "YYYY-MM-DD"),
            ("closed=2026-10-01", "only a closed issue"),
            ("depends=042", "depends on 042, which doesn't exist"),
            ("depends=1", "itself"),
            ("depends=two", "isn't an issue number"),
            ("title=New title", "edit it there"),
            ("note=a # b", "starts a comment"),
            ("owner", "isn't key=value"),
            ("bad key=x", "isn't key=value"),
        ]:
            self.assertIn(message, fails("--dir", str(self.dir), "set", "1", "owner=sam", pair), pair)
        self.assertEqual((self.dir / "001-a.md").read_text(), before)
        self.assertIn("`reopen 002`", fails("--dir", str(self.dir), "set", "2", "status=open"))
        self.assertIn("`reopen 002`", fails("--dir", str(self.dir), "set", "2", "closed="))
        code, _ = run("--dir", str(self.dir), "set", "2", "closed=2026-09-21")
        self.assertEqual(code, 0)
        self.assertEqual(self.check(), ([], []))

    def test_frontmatter_rejects_what_it_cant_parse(self):
        for name, extra in [
            ("001-a.md", "depends:\n  - 004\n"),
            ("002-b.md", "depends:\n- 004\n"),
            ("003-c.md", "note: first line\n  carries on: here\n"),
            ("004-d.md", "- stray\n"),
            ("005-e.md", "note: |\n  block text\n"),
        ]:
            self.write(name, extra=extra)
        run("--dir", str(self.dir), "index")
        errors, _ = self.check()
        joined = "\n".join(errors)
        self.assertIn("001-a.md: frontmatter line 6: `depends:` is followed by indented or `- ` lines", joined)
        self.assertIn("002-b.md: frontmatter line 6: `depends:` is followed by", joined)
        self.assertIn("003-c.md: frontmatter line 7 is indented", joined)
        self.assertIn("004-d.md: frontmatter line 6 is a YAML list item", joined)
        self.assertIn("005-e.md: frontmatter line 6: `note:` is followed by", joined)
        self.assertEqual(run("--dir", str(self.dir), "check")[0], 1)
        self.assertIn("Fix the frontmatter first", fails("--dir", str(self.dir), "close", "1"))
        self.assertIn("Fix the frontmatter first", fails("--dir", str(self.dir), "set", "3", "owner=sam"))

    def test_frontmatter_still_accepts_comments_blanks_and_empty_values(self):
        self.write("001-a.md", extra="# a comment\n\n  # an indented comment\nowner:\nnote: x  # trailing comment\n")
        run("--dir", str(self.dir), "index")
        self.assertEqual(self.check(), ([], []))

    def test_config_needs_tomllib(self):
        (self.dir / ".backlog.toml").write_text('priorities = ["high", "low"]\n')
        with mock.patch.object(backlog, "tomllib", None):
            self.assertIn("needs Python 3.11 or later", fails("--dir", str(self.dir), "check"))
            (self.dir / ".backlog.toml").unlink()
            self.assertEqual(run("--dir", str(self.dir), "check")[0], 0)

    @unittest.skipIf(backlog.tomllib is None, "the config file needs tomllib (Python 3.11+)")
    def test_config_sets_statuses_priorities_and_done_sections(self):
        (self.dir / ".backlog.toml").write_text(
            'statuses = ["open", "in-progress", "closed"]\n'
            'priorities = ["high", "medium", "low"]\n'
            'done_sections = ["Acceptance tests"]\n')
        self.write("001-a.md", status="in-progress", priority="low")
        self.write("002-b.md", priority="high", tail="\n## Acceptance tests\nThey pass.\n")
        run("--dir", str(self.dir), "index")
        self.assertEqual(self.check(), ([], [
            "001-a.md: in-progress with no `## Done when` (refine it before executing)"]))
        _, out = run("--dir", str(self.dir), "list", "--status", "all", "--json")
        self.assertEqual([d["number"] for d in json.loads(out)], ["002", "001"])
        _, out = run("--dir", str(self.dir), "list", "--status", "in-progress")
        self.assertIn("001  low", out)
        self.assertIn("one of open, in-progress, closed, all", fails("--dir", str(self.dir), "list", "--status", "x"))
        self.assertIn("one of high, medium, low", fails("--dir", str(self.dir), "new", "--title", "X", "--priority", "P2"))
        _, out = run("--dir", str(self.dir), "new", "--title", "Default priority")
        self.assertIn("priority: medium\n", Path(out.strip()).read_text())
        self.assertEqual(run("--dir", str(self.dir), "set", "2", "status=in-progress")[0], 0)
        self.assertEqual(run("--dir", str(self.dir), "set", "2", "status=open")[0], 0)
        self.assertIn("isn't one of high, medium, low", fails("--dir", str(self.dir), "set", "2", "priority=P1"))
        self.write("004-c.md", priority="P1")
        run("--dir", str(self.dir), "index")
        self.assertIn("004-c.md: priority `P1` isn't one of high, medium, low", "\n".join(self.check()[0]))

    @unittest.skipIf(backlog.tomllib is None, "the config file needs tomllib (Python 3.11+)")
    def test_config_errors(self):
        for text, message in [
            ('statuses = ["open", "done"]\n', '`statuses` must include "closed"'),
            ('priority = ["P1"]\n', "unknown key `priority`"),
            ('priorities = "P1"\n', "must be a non-empty list of strings"),
            ("priorities = []\n", "must be a non-empty list of strings"),
            ('priorities = ["P 1"]\n', "must be one word"),
            ('statuses = ["open", "closed", "all"]\n', "must be one word"),
            ('priorities = ["P1", "P1"]\n', "lists a value twice"),
            ("statuses = [\n", ".backlog.toml: "),
        ]:
            (self.dir / ".backlog.toml").write_text(text)
            self.assertIn(message, fails("--dir", str(self.dir), "check"), text)

    def test_install_hook_needs_git(self):
        self.assertIn("isn't inside a git repository", fails("--dir", str(self.dir), "install-hook"))


class InstallHookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = Path(self.tmp)
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "T"],
                     ["config", "gc.auto", "0"], ["config", "maintenance.auto", "false"]):
            subprocess.run(["git", *args], cwd=self.root, check=True)
        self.dir = self.root / "issues"
        run("--dir", str(self.dir), "init")
        self.hook = self.root / ".githooks" / "pre-commit"

    def tearDown(self):
        remove_tree(self.tmp)

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True)

    def install(self, *flags):
        return run("--dir", str(self.dir), "install-hook", *flags)

    def test_writes_hook_and_copies_scripts(self):
        code, out = self.install("--with-secret-scan")
        self.assertEqual(code, 0)
        scripts = Path(backlog.__file__).resolve().parent
        for name in ("backlog.py", "secret_scan.py"):
            self.assertEqual((self.root / "scripts" / name).read_text(encoding="utf-8"),
                             (scripts / name).read_text(encoding="utf-8"))
        text = self.hook.read_text()
        self.assertTrue(text.startswith("#!/bin/sh\n"))
        self.assertIn('for PY in python3 python "py -3"; do $PY -c "" >/dev/null 2>&1 && break; done', text)
        self.assertIn("grep -q '^issues/'", text)
        self.assertIn("$PY scripts/backlog.py --dir issues check", text)
        self.assertIn("$PY scripts/secret_scan.py --staged", text)
        self.assertIn("git config core.hooksPath .githooks", out)
        if os.name != "nt":
            self.assertTrue(os.stat(str(self.hook)).st_mode & stat.S_IXUSR)
        code, out = self.install("--with-secret-scan")
        self.assertEqual(code, 0)
        self.assertEqual(self.hook.read_text(), text)
        self.assertEqual(text.count(backlog.HOOK_START), 1)
        self.assertIn("Already current: .githooks/pre-commit", out)
        self.assertIn("Already current: scripts/backlog.py", out)
        self.install()
        self.assertNotIn("secret_scan", self.hook.read_text())

    def test_extends_an_existing_hook(self):
        self.hook.parent.mkdir()
        self.hook.write_text("#!/bin/sh\necho existing\nexit 0\n")
        self.install()
        text = self.hook.read_text()
        self.assertTrue(text.startswith("#!/bin/sh\n" + backlog.HOOK_START), text)
        self.assertTrue(text.endswith("\necho existing\nexit 0\n"), text)
        self.install()
        self.assertEqual(self.hook.read_text(), text)

    def test_refuses_a_hook_that_isnt_sh(self):
        self.hook.parent.mkdir()
        self.hook.write_text("#!/usr/bin/env python3\nprint('hi')\n")
        self.assertIn("isn't a shell script", fails("--dir", str(self.dir), "install-hook"))
        self.assertEqual(self.hook.read_text(), "#!/usr/bin/env python3\nprint('hi')\n")
        self.assertFalse((self.root / "scripts" / "backlog.py").exists())

    def test_refuses_a_different_script_unless_forced(self):
        (self.root / "scripts").mkdir()
        (self.root / "scripts" / "backlog.py").write_text("print('mine')\n")
        self.assertIn("--force", fails("--dir", str(self.dir), "install-hook"))
        self.assertEqual((self.root / "scripts" / "backlog.py").read_text(), "print('mine')\n")
        self.assertFalse(self.hook.exists())
        self.assertEqual(self.install("--force")[0], 0)
        self.assertNotEqual((self.root / "scripts" / "backlog.py").read_text(), "print('mine')\n")

    def test_leaves_another_hooks_path_alone(self):
        self.git("config", "core.hooksPath", ".husky")
        _, out = self.install()
        self.assertIn("core.hooksPath is set to `.husky`", out)
        self.assertEqual(self.git("config", "--get", "core.hooksPath").stdout.strip(), ".husky")
        self.git("config", "core.hooksPath", ".githooks")
        _, out = self.install()
        self.assertIn("core.hooksPath is already .githooks", out)

    def test_hook_blocks_a_commit_with_a_broken_backlog(self):
        self.install()
        self.git("config", "core.hooksPath", ".githooks")
        (self.dir / "001-a.md").write_text("---\nstatus: open\npriority: P9\nopened: 2026-01-01\n---\n\n# A\n")
        self.git("add", "-A")
        result = self.git("commit", "-qm", "broken")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("priority `P9`", result.stdout + result.stderr)
        run("--dir", str(self.dir), "set", "1", "priority=P2")
        self.git("add", "-A")
        result = self.git("commit", "-qm", "fixed")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
