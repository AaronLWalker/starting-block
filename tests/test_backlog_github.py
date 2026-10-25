import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import backlog_github as gh  # noqa: E402

DONE = "## Problem\nBroken.\n\n## Done when\n- tests pass\n"


def issue(number, title="A thing", labels=(), body=DONE, state="OPEN", assignees=(), created="2026-09-14T10:00:00Z"):
    return {"number": number, "title": title, "body": body, "state": state, "url": "https://x/" + str(number),
            "labels": [{"name": n} for n in labels], "assignees": [{"login": a} for a in assignees],
            "createdAt": created, "closedAt": "2026-09-20T10:00:00Z" if state == "CLOSED" else None}


class NormalizeTest(unittest.TestCase):
    def one(self, **kw):
        return gh.normalize([issue(1, **kw)])[0]

    def test_fields(self):
        i = self.one(labels=["P1", "area:auth", "bug"], assignees=["sam"])
        self.assertEqual((i["number"], i["priority"], i["area"], i["owner"]), ("#1", "P1", ["auth", "bug"], "sam"))
        self.assertEqual((i["status"], i["opened"], i["closed"]), ("open", "2026-09-14", None))
        self.assertEqual(i["sections"], ["Problem", "Done when"])
        self.assertTrue(i["ready"])

    def test_priority_label_spellings(self):
        for label in ("P2", "p2", "priority: P2", "priority/p2", "Priority - P2"):
            self.assertEqual(self.one(labels=[label])["priority"], "P2", label)
        self.assertEqual(self.one(labels=["bug"])["priority"], "")

    def test_not_ready_without_done_when(self):
        self.assertFalse(self.one(body="## Problem\nx\n")["ready"])

    def test_needs_checklist(self):
        todo = self.one(body=DONE + "\n## Needs the owner\n- [ ] Add the API key\n")
        done = self.one(body=DONE + "\n## Needs the owner\n- [x] Add the API key\n")
        self.assertEqual(todo["needs_human"], ["Needs the owner"])
        self.assertFalse(todo["ready"])
        self.assertEqual(done["needs_human"], [])
        self.assertTrue(done["ready"])

    def test_depends_lines(self):
        issues = gh.normalize([
            issue(1, body=DONE + "\nDepends on #2\n**Blocked by** #3, #2\n"),
            issue(2),
            issue(3, state="CLOSED"),
        ])
        first = issues[0]
        self.assertEqual(first["depends"], ["#2", "#3"])
        self.assertEqual(first["open_depends"], ["#2"])
        self.assertFalse(first["ready"])

    def test_rest_field_names_and_body_priority(self):
        raw = {"number": 4, "title": "T", "state": "closed", "html_url": "https://x/4", "labels": ["docs"],
               "assignees": ["ana"], "created_at": "2026-09-01T00:00:00Z", "closed_at": "2026-09-02T00:00:00Z",
               "body": "**Priority:** P1. Urgent.\n\n" + DONE}
        i = gh.normalize([raw])[0]
        self.assertEqual((i["priority"], i["area"], i["owner"], i["status"]), ("P1", ["docs"], "ana", "closed"))
        self.assertEqual((i["opened"], i["closed"], i["file"]), ("2026-09-01", "2026-09-02", "https://x/4"))

    def test_runs_on_labels(self):
        i = self.one(labels=["P2", "runs-on:Host", "RUNS-ON: gpu", "docs"])
        self.assertEqual((i["runs_on"], i["unreachable"], i["area"]), (["Host", "gpu"], ["Host", "gpu"], ["docs"]))
        self.assertFalse(i["ready"])
        i = gh.normalize([issue(1, labels=["runs-on:Host", "runs-on:gpu"])], reachable=["repo", "host"])[0]
        self.assertEqual((i["unreachable"], i["ready"]), (["gpu"], False))
        i = gh.normalize([issue(1, labels=["runs-on:host", "runs-on:gpu"])], reachable=["host", "GPU"])[0]
        self.assertEqual((i["unreachable"], i["ready"]), ([], True))
        i = self.one(labels=["runs-on:repo"])
        self.assertEqual((i["runs_on"], i["unreachable"], i["ready"]), (["repo"], [], True))
        i = self.one()
        self.assertEqual((i["runs_on"], i["unreachable"], i["hold"]), ([], [], None))

    def test_on_hold_label(self):
        i = self.one(labels=["P1", "On-Hold", "bug"])
        self.assertEqual((i["hold"], i["area"], i["ready"]), ("on-hold label", ["bug"], False))

    def test_crlf_bodies(self):
        self.assertTrue(self.one(body=DONE.replace("\n", "\r\n"))["ready"])


class CommandTest(unittest.TestCase):
    def test_label_filter(self):
        issues = gh.normalize([issue(1, labels=["P2", "Agent-OK"]), issue(2, labels=["P1"]), issue(3)])
        self.assertEqual([i["number"] for i in gh.select(issues, "open", "agent-ok")], ["#1"])
        self.assertEqual(len(gh.select(issues, "open")), 3)
        self.assertEqual(issues[0]["labels"], ["P2", "Agent-OK"])

    def test_from_json_sorts_and_filters(self):
        data = [issue(5, labels=["P3"]), issue(7, labels=["P1"]), issue(6, state="CLOSED", labels=["P1"]), issue(8)]
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f)
        try:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(gh.main(["from-json", path, "--json"]), 0)
            self.assertEqual([i["number"] for i in json.loads(out.getvalue())], ["#7", "#5", "#8"])
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                gh.main(["from-json", path])
            self.assertIn("no priority label", out.getvalue())
        finally:
            os.remove(path)


    def test_from_json_reachable_and_flags(self):
        data = [issue(1, labels=["P1", "runs-on:host"]), issue(2, labels=["P2", "on-hold"]),
                issue(3, labels=["P3", "runs-on:gpu"])]
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f)

        def call(*flags):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(gh.main(["from-json", path] + list(flags)), 0)
            return out.getvalue()
        try:
            ready = {i["number"]: i["ready"] for i in json.loads(call("--json"))}
            self.assertEqual(ready, {"#1": False, "#2": False, "#3": False})
            for flags in (["--reachable", "host,gpu"], ["--reachable", "host", "--reachable", "gpu"]):
                ready = {i["number"]: i["ready"] for i in json.loads(call("--json", *flags))}
                self.assertEqual(ready, {"#1": True, "#2": False, "#3": True}, flags)
            text = call()
            self.assertIn("[runs on host]", text)
            self.assertIn("[on hold: on-hold label]", text)
            self.assertNotIn("no 'Done when'", text)
            self.assertNotIn("runs on host", call("--reachable", "host"))
        finally:
            os.remove(path)

    def test_version_matches_the_other_scripts(self):
        import backlog
        import secret_scan
        self.assertEqual(gh.__version__, backlog.__version__)
        self.assertEqual(gh.__version__, secret_scan.__version__)


if __name__ == "__main__":
    unittest.main()
