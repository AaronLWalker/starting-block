import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "skills/drift-guard/templates/check_manifest.py"


class DriftTemplateTest(unittest.TestCase):
    """The drift-guard template works as shipped against its own example layout."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "scripts").mkdir()
        (self.tmp / "docs").mkdir()
        (self.tmp / "src").mkdir()
        shutil.copy(str(TEMPLATE), str(self.tmp / "scripts/check_manifest.py"))
        (self.tmp / "src/routes.py").write_text('@route("/users")\ndef users(): ...\n@route("/health")\ndef health(): ...\n')
        self.manifest([("/users", "List users"), ("/health", "Liveness probe")])
        (self.tmp / "README.md").write_text(
            "# API\n\n<!-- generated:start (edit docs/manifest.json, then run build) -->\n<!-- generated:end -->\n\nEnd.\n")
        sys.path.insert(0, str(self.tmp / "scripts"))
        sys.modules.pop("check_manifest", None)
        import check_manifest
        self.mod = check_manifest

    def tearDown(self):
        sys.path.remove(str(self.tmp / "scripts"))
        sys.modules.pop("check_manifest", None)
        shutil.rmtree(str(self.tmp))

    def manifest(self, items):
        data = {"items": [{"name": n, "description": d} for n, d in items]}
        (self.tmp / "docs/manifest.json").write_text(json.dumps(data))

    def run_cmd(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = self.mod.main(list(argv))
        return code, out.getvalue()

    def test_build_then_check_passes(self):
        self.assertEqual(self.run_cmd("build")[0], 0)
        readme = (self.tmp / "README.md").read_text()
        self.assertIn("| `/health` | Liveness probe |", readme)
        self.assertTrue(readme.endswith("End.\n"))
        self.assertEqual(self.run_cmd("check", "--offline"), (0, "In step: 2 entries\n"))

    def test_each_kind_of_drift_fails_with_a_fix(self):
        self.run_cmd("build")
        self.manifest([("/users", "List users"), ("/gone", "Removed route")])
        code, out = self.run_cmd("check", "--offline")
        self.assertEqual(code, 1)
        self.assertIn("routes.py defines '/health' but manifest.json has no entry", out)
        self.assertIn("manifest.json lists '/gone' but routes.py doesn't define it", out)
        self.assertIn("generated table is out of date", out)
        self.assertIn("run: python scripts/check_manifest.py build", out)


if __name__ == "__main__":
    unittest.main()
