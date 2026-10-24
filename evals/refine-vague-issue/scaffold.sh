set -euo pipefail
git init -q -b main
git config user.name "Eval Bot"
git config user.email "eval@example.com"

mkdir -p src tests
cat > src/export.py <<'EOF'
"""Export contacts to CSV."""


def to_csv(rows):
    """rows: list of dicts with name, email, phone."""
    lines = ["name,email,phone"]
    for r in rows:
        lines.append(",".join([r["name"], r["email"], r["phone"]]))
    return "\n".join(lines) + "\n"
EOF
cat > tests/test_export.py <<'EOF'
import sys, unittest
sys.path.insert(0, "src")
from export import to_csv


class ExportTest(unittest.TestCase):
    def test_header(self):
        self.assertTrue(to_csv([]).startswith("name,email,phone"))

    def test_simple_row(self):
        out = to_csv([{"name": "Ann", "email": "a@x.org", "phone": "1"}])
        self.assertIn("Ann,a@x.org,1", out)


if __name__ == "__main__":
    unittest.main()
EOF

mkdir -p issues
cat > issues/001-export-is-broken.md <<'EOF'
---
status: open
priority: P3
area: export
opened: 2026-09-10
---

# Export is broken

## Problem
Some customers say the export is wrong. Probably the email validation at `src/export.py` line 40.
EOF

cat > issues/README.md <<'EOF'
# Issues

One Markdown file per issue. Priority: **P1** fix soon, **P2** worth doing, **P3** tidy-up.

| # | Priority | Issue |
|---|---|---|
| [001](001-export-is-broken.md) | P3 | Export is broken |
EOF

cat > NOTES.md <<'EOF'
Support ticket 2026-09-09: "my export has an extra column for every customer whose name is like 'Smith, Ann'".
EOF
git add -A && git commit -qm "Initial export module and backlog"
