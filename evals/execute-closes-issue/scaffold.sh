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
cat > issues/001-csv-export-breaks-on-commas.md <<'EOF'
---
status: open
priority: P2
area: export
opened: 2026-09-10
---

# CSV export breaks when a field contains a comma

## Problem
`to_csv` in `src/export.py` joins fields with `","` and doesn't quote them, so a name like
`Smith, Ann` produces four columns instead of three.

## Proposed fix
Write rows with Python's `csv` module, which quotes fields that need it.

## Done when
- A test in `tests/test_export.py` exports `{"name": "Smith, Ann", ...}` and reads it back with
  `csv.reader` as exactly three fields.
- `python3 -m unittest discover -s tests` passes.
EOF

cat > issues/README.md <<'EOF'
# Issues

One Markdown file per issue. Priority: **P1** fix soon, **P2** worth doing, **P3** tidy-up.

| # | Priority | Issue |
|---|---|---|
| [001](001-csv-export-breaks-on-commas.md) | P2 | CSV export breaks when a field contains a comma |
EOF

git add -A && git commit -qm "Initial export module and backlog"
