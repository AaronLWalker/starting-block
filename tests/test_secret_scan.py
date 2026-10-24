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

    def scan(self, *flags):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = secret_scan.main([str(self.root), "--json", *flags])
        return code, json.loads(out.getvalue())

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


if __name__ == "__main__":
    unittest.main()
