import base64
import contextlib
import hashlib
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
import secret_scan  # noqa: E402


def remove_tree(path):
    """rmtree that also clears the read-only bits git puts on object files (Windows can't delete those)."""
    def retry(func, p, exc):
        if issubclass(exc[0], FileNotFoundError):
            return  # gone already, e.g. a lock file git's background maintenance just removed
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=retry)


# Fixture secrets are assembled from pieces so this file doesn't look like a leak to scanners.
GH = "ghp_" + "abcdefghijklmnopqrstuvwxyzABCDEFGHIJ"
WG = "yAnz5TF+lXXJte14tji3zlMNq+hd2rYU" + "IgJBgB3fBmk="
HEX = "4f9c2b7e8a1d4e6f" + "9b0c3a5d7e8f1a2b"


def b64(seed, size=64, urlsafe=False):
    """Deterministic random-looking base64, so no token literal appears in this file."""
    raw = hashlib.sha512(seed.encode()).digest()[:size]
    return (base64.urlsafe_b64encode if urlsafe else base64.b64encode)(raw).decode()


def alnum(seed, n):
    return "".join(c for c in b64(seed) + b64(seed + "+") if c.isalnum())[:n]


def letters(seed, n):
    return "".join(c for c in b64(seed) + b64(seed + "+") if c.isalpha())[:n]


AZURE = "AccountKey=" + b64("azure")  # 64 bytes: 86 base64 characters and ==
NPM = "npm_" + alnum("npm", 36)
PYPI = "pypi-" + "AgEIcHlwaS5vcmc" + b64("pypi", urlsafe=True).rstrip("=")
HF = "hf_" + letters("hf", 34)
DISCORD = (base64.b64encode(b"1234567890" + b"12345678").decode() + "." + alnum("ts", 6) + "."
           + b64("discord", 32, urlsafe=True)[:38])
TELEGRAM = "1234567" + "89:" + "A" + b64("tg", urlsafe=True)[:34]
SERVICE_ACCOUNT = json.dumps({
    "type": "service_account",
    "project_id": "demo",
    "private_key_id": HEX,
    "private_key": "-----BEGIN " + "PRIVATE KEY-----\n" + b64("key") * 20 + "\n-----END " + "PRIVATE KEY-----\n",
    "client_email": "bot@demo.iam.gserviceaccount.com",
}, indent=2)


class ScanLineTest(unittest.TestCase):
    def rules(self, line):
        return [r for r, _ in secret_scan.scan_line(line)]

    def test_specific_shapes(self):
        self.assertEqual(self.rules("token: " + GH), ["github-token"])
        self.assertEqual(self.rules("PrivateKey = " + WG), ["wireguard-key"])
        self.assertEqual(self.rules("<ApiKey>" + HEX + "</ApiKey>"), ["xml-api-key"])
        self.assertEqual(self.rules("-----BEGIN OPENSSH " + "PRIVATE KEY-----"), ["private-key"])
        self.assertEqual(self.rules("db = postgres://admin:" + "S3cr3tPw@db:5432/x"), ["url-credentials"])

    def test_generic_assignment(self):
        self.assertEqual(self.rules('api_key = "' + HEX + '"'), ["assignment"])

    def test_not_secrets(self):
        for line in [
            "password: changeme",
            'token = os.environ.get("TOKEN")',
            "api_key: ${API_KEY}",
            '"apiKey": "{env:NEURALWATT_API_KEY}"',
            "title_tokens = set(re.findall(r'[a-z]+', title))",
            "secret = self.secret_value",
            'password = "' + HEX + '"  # secret-scan: ignore',
        ]:
            self.assertEqual(self.rules(line), [], line)

    def test_provider_tokens(self):
        for line, rule in [
            ("DefaultEndpointsProtocol=https;AccountName=demo;" + AZURE + ";EndpointSuffix=core.windows.net",
             "azure-storage-key"),
            ("//registry.npmjs.org/:_authToken=" + NPM, "npm-token"),
            ("password = " + PYPI, "pypi-token"),
            ("HF_TOKEN=" + HF, "huggingface-token"),
            ("DISCORD_TOKEN=" + DISCORD, "discord-bot-token"),
            ('bot = Bot("' + TELEGRAM + '")', "telegram-bot-token"),
        ]:
            self.assertEqual(self.rules(line), [rule], line)

    def test_provider_lookalikes(self):
        for line in [
            "AccountKey=" + "A" * 86 + "==",
            "npm_" + "x" * 36,
            "npm_config_registry=https://registry.npmjs.org/",
            "pypi-" + "AgEIcHlwaS5vcmc" + "A" * 60,
            "hf_" + "x" * 34,
            "hf_" + "abcdefghijklmnopqrstuvwxyzabcdefghij",
            "ManagementServiceProviderX." + "Config." + "SomeVeryLongPropertyNameHereXyz",
            "1234567" + "89:" + "A" * 35,
            "at 20261024:" + "b" * 35,
        ]:
            self.assertEqual(self.rules(line), [], line)

    def test_gcp_service_account_reported_once(self):
        found = secret_scan.scan_document(enumerate(SERVICE_ACCOUNT.splitlines(), 1))
        self.assertEqual([(n, rule) for n, rule, _ in found], [(5, "gcp-service-account")])

    def test_private_key_outside_service_account(self):
        lines = SERVICE_ACCOUNT.replace("service_account", "authorized_user").splitlines()
        found = secret_scan.scan_document(enumerate(lines, 1))
        self.assertEqual([rule for _, rule, _ in found], ["private-key"])
        empty = json.dumps({"type": "service_account", "private_key": ""}, indent=2).splitlines()
        self.assertEqual(secret_scan.scan_document(enumerate(empty, 1)), [])


class VersionTest(unittest.TestCase):
    def test_version_flag(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(SystemExit) as e:
                secret_scan.main(["--version"])
        self.assertEqual(e.exception.code, 0)
        self.assertEqual(out.getvalue().strip(), "secret_scan.py " + secret_scan.__version__)


class HistoryParseTest(unittest.TestCase):
    def test_groups_added_lines_by_file(self):
        commit = "a" * 40
        log = ["@@commit " + commit, "", "diff --git a/x b/x", "--- a/x", "+++ b/x", "@@ -3,0 +4,2 @@",
               "+++ not a header", "+two", "diff --git a/y b/y", "deleted file mode 100644", "--- a/y",
               "+++ /dev/null", "@@ -1 +0,0 @@", "-gone"]
        self.assertEqual(list(secret_scan.history_files(log)),
                         [(commit, "x", [(4, "++ not a header"), (5, "two")])])


class RepoScanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = Path(self.tmp)
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "T"],
                     ["config", "gc.auto", "0"], ["config", "maintenance.auto", "false"]):
            subprocess.run(["git", *args], cwd=self.root, check=True)

    def tearDown(self):
        remove_tree(self.tmp)

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)

    def scan(self, *flags, gitleaks=False):
        out, self.stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(self.stderr):
            code = secret_scan.main([str(self.root), "--json", *flags] + ([] if gitleaks else ["--no-gitleaks"]))
        return code, json.loads(out.getvalue() or "null")

    def commit(self, files, message="change"):
        for name, text in files.items():
            if text is None:
                (self.root / name).unlink()
            else:
                (self.root / name).write_text(text)
        self.git("add", "-A")
        self.git("commit", "-qm", message)

    def test_clean_repo(self):
        (self.root / "app.py").write_text("print('hi')\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "init")
        self.assertEqual(self.scan(), (0, []))

    def test_secret_only_in_history(self):
        (self.root / "settings.json").write_text('{"token": "' + GH + '"}\n')
        self.git("add", "-A")
        self.git("commit", "-qm", "add")
        (self.root / "settings.json").write_text("{}\n")
        self.git("commit", "-qam", "remove")
        self.assertEqual(self.scan()[0], 0)
        code, findings = self.scan("--history")
        self.assertEqual(code, 1)
        self.assertEqual([f["rule"] for f in findings], ["github-token"])
        self.assertNotIn(GH, json.dumps(findings))

    def test_sensitive_file_and_ignore_list(self):
        (self.root / ".env").write_text("X=1\n")
        (self.root / ".env.example").write_text("X=\n")
        (self.root / "fixture.txt").write_text("token: " + GH + "\n")
        self.git("add", "-A")
        code, findings = self.scan("--staged")
        self.assertEqual(code, 1)
        self.assertEqual(sorted(f["rule"] for f in findings), ["github-token", "sensitive-file"])
        (self.root / ".secretscanignore").write_text("# test fixtures\nfixture.txt\n.env\n")
        self.assertEqual(self.scan("--staged"), (0, []))

    def test_history_line_numbers_and_since(self):
        self.commit({"a.txt": "one\ntwo\n"})
        self.commit({"a.txt": "one\ntoken: " + GH + "\ntwo\n"})
        self.commit({"b.txt": "x\n" + "registry_auth=" + NPM + "\n"})
        self.commit({"a.txt": None, "b.txt": None})
        code, findings = self.scan("--history")
        self.assertEqual(sorted((f["rule"], f["line"]) for f in findings), [("github-token", 2), ("npm-token", 2)])
        self.assertTrue(all(len(f["where"].split("commit ")[1]) == 13 for f in findings))  # 12 digits and ")"
        code, findings = self.scan("--since", "HEAD~2")
        self.assertEqual((code, [f["rule"] for f in findings]), (1, ["npm-token"]))
        self.assertEqual(self.scan("--since", "HEAD"), (0, []))
        with self.assertRaises(SystemExit):
            self.scan("--since", "no-such-rev")

    def test_history_streams_and_checks_exit_status(self):
        self.commit({"a.txt": "one\n"})
        with self.assertRaises(subprocess.CalledProcessError):
            list(secret_scan.git_lines("log", "no-such-rev", cwd=self.root))
        lines = secret_scan.git_lines("log", "-p", cwd=self.root)
        self.assertTrue(next(lines).startswith("commit "))
        lines.close()  # stopping early must not hang or raise

    def test_service_account_file_in_history(self):
        self.commit({"sa.json": SERVICE_ACCOUNT + "\n"})
        code, findings = self.scan("--history")
        self.assertEqual([(f["rule"], f["line"]) for f in findings], [("gcp-service-account", 5)] * 2)

    def test_baseline(self):
        self.commit({"settings.json": '{"token": "' + GH + '"}\n'})
        self.commit({"settings.json": "{}\n"})
        baseline = Path(self.tmp) / "baseline.json"
        self.assertEqual(self.scan("--history", "--write-baseline", str(baseline))[0], 0)
        text = baseline.read_text(encoding="utf-8")
        self.assertNotIn(GH, text)
        entry = json.loads(text)["findings"][0]
        self.assertEqual((entry["rule"], entry["sha256"]), ("github-token", hashlib.sha256(GH.encode()).hexdigest()))
        self.assertEqual(self.scan("--history", "--baseline", str(baseline)), (0, []))
        self.commit({"other.txt": "npm_token = " + NPM + "\n"})
        code, findings = self.scan("--history", "--baseline", str(baseline))
        self.assertEqual(sorted(f["rule"] for f in findings), ["npm-token", "npm-token"])
        baseline.write_text("not json")
        with self.assertRaises(SystemExit):
            self.scan("--baseline", str(baseline))


class GitleaksTest(unittest.TestCase):
    COMMIT = "0123456789abcdef" * 2 + "01234567"

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = Path(self.tmp)

    def tearDown(self):
        remove_tree(self.tmp)

    def report(self, entries):
        path = self.root / "report.json"
        path.write_text(json.dumps(entries))
        return path

    def entry(self, **overrides):
        e = {"RuleID": "generic-api-key", "File": "app.cfg", "StartLine": 3, "Commit": self.COMMIT,
             "Secret": "REDACTED", "Match": "key = REDACTED", "Line": "key = REDACTED",
             "Fingerprint": self.COMMIT + ":app.cfg:generic-api-key:3"}
        e.update(overrides)
        return e

    def test_read_report(self):
        report = self.report([
            self.entry(),
            self.entry(File="fixtures/x.cfg"),
            self.entry(Line="key = REDACTED  # secret-scan: ignore"),
            "junk",
            self.entry(File=str(self.root / "local.cfg"), Commit="", Fingerprint=""),
        ])
        found = secret_scan.read_gitleaks_report(report, self.root, ["fixtures/*"])
        self.assertEqual([(f["where"], f["line"], f["rule"], f["match"]) for f in found], [
            ("app.cfg (commit 0123456789ab)", 3, "gitleaks:generic-api-key", "…"),
            ("local.cfg", 3, "gitleaks:generic-api-key", "…"),
        ])
        self.assertEqual(found[0]["sha256"], hashlib.sha256(self.entry()["Fingerprint"].encode()).hexdigest())
        self.assertEqual(found[1]["sha256"], hashlib.sha256(b"local.cfg:generic-api-key:3").hexdigest())
        tracked_only = secret_scan.read_gitleaks_report(report, self.root, tracked={"local.cfg"})
        self.assertEqual([f["where"] for f in tracked_only], ["local.cfg"])
        with self.assertRaises(ValueError):
            secret_scan.read_gitleaks_report(self.report({"not": "a list"}), self.root)

    def test_merge_skips_same_file_and_line(self):
        ours = [{"where": "app.cfg (commit 0123456789ab)", "line": 3, "rule": "assignment", "match": "…",
                 "sha256": "0"}]
        theirs = secret_scan.read_gitleaks_report(self.report([self.entry(), self.entry(StartLine=9)]), self.root)
        self.assertEqual([f["line"] for f in secret_scan.merge(ours, theirs)], [3, 9])


@unittest.skipIf(os.name == "nt", "the fake gitleaks is a shebang script")
class GitleaksOnPathTest(RepoScanTest):
    FAKE = """#!{python}
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_GITLEAKS_LOG"], "a") as f:
    f.write(json.dumps(args) + "\\n")
if os.environ.get("FAKE_GITLEAKS_FAIL"):
    sys.stderr.write("fatal: something broke\\n")
    sys.exit(2)
source = json.dumps(args[args.index("--source") + 1])[1:-1]
with open(os.environ["FAKE_GITLEAKS_REPORT"]) as f:
    report = f.read().replace("{{source}}", source)
with open(args[args.index("--report-path") + 1], "w") as f:
    f.write(report)
sys.exit(0 if report == "[]" else 1)
"""

    def setUp(self):
        super().setUp()
        self.bin = Path(tempfile.mkdtemp())
        fake = self.bin / "gitleaks"
        fake.write_text(self.FAKE.format(python=sys.executable))
        fake.chmod(0o755)
        self.log = self.bin / "calls.jsonl"
        self.report = self.bin / "report.json"
        env = {"PATH": str(self.bin) + os.pathsep + os.environ.get("PATH", ""),
               "FAKE_GITLEAKS_LOG": str(self.log), "FAKE_GITLEAKS_REPORT": str(self.report)}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(remove_tree, str(self.bin))

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(l) for l in self.log.read_text().splitlines()]

    def test_history_hand_off(self):
        self.commit({"notes.txt": "hello\n"})
        self.report.write_text(json.dumps([{"RuleID": "fake-rule", "File": "notes.txt", "StartLine": 1,
                                            "Commit": "ab" * 20, "Secret": "REDACTED", "Fingerprint": "fp"}]))
        code, findings = self.scan("--history", gitleaks=True)
        self.assertEqual((code, [f["rule"] for f in findings]), (1, ["gitleaks:fake-rule"]))
        args = self.calls()[0]
        self.assertEqual(args[0], "detect")
        self.assertIn("--redact", args)
        self.assertIn("--log-opts=--all", args)
        self.assertEqual(self.scan("--history"), (0, []))  # --no-gitleaks
        self.assertEqual(len(self.calls()), 1)

    def test_working_tree_hand_off_keeps_to_tracked_files(self):
        self.commit({"notes.txt": "hello\n"})
        (self.root / ".env.local").write_text("untracked\n")
        self.report.write_text(json.dumps([
            {"RuleID": "fake-rule", "File": "{source}/notes.txt", "StartLine": 1, "Secret": "REDACTED"},
            {"RuleID": "fake-rule", "File": "{source}/.env.local", "StartLine": 1, "Secret": "REDACTED"},
        ]))
        code, findings = self.scan(gitleaks=True)
        self.assertEqual([(f["where"], f["rule"]) for f in findings], [("notes.txt", "gitleaks:fake-rule")])
        self.assertIn("--no-git", self.calls()[0])

    def test_staged_skips_gitleaks(self):
        (self.root / "notes.txt").write_text("hello\n")
        self.git("add", "-A")
        self.report.write_text("[]")
        self.assertEqual(self.scan("--staged", gitleaks=True), (0, []))
        self.assertEqual(self.calls(), [])

    def test_failure_is_a_warning(self):
        self.commit({"notes.txt": "hello\n"})
        with mock.patch.dict(os.environ, {"FAKE_GITLEAKS_FAIL": "1"}):
            self.assertEqual(self.scan("--history", gitleaks=True), (0, []))
        self.assertIn("gitleaks exited 2", self.stderr.getvalue())
        self.report.write_text("not json")
        self.assertEqual(self.scan(gitleaks=True), (0, []))
        self.assertIn("couldn't read the gitleaks report", self.stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
