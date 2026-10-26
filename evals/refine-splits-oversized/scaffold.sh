set -euo pipefail
git init -q -b main
git config user.name "Eval Bot"
git config user.email "eval@example.com"

mkdir -p src tests issues
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


if __name__ == "__main__":
    unittest.main()
EOF
cat > issues/001-export-improvements.md <<'EOF'
---
status: open
priority: P2
area: export
opened: 2026-10-20
---

# Export improvements

## Problem
Support asked for several export fixes on 2026-10-19:
- a name like `Smith, Ann` comes out as four columns;
- a contact saved without a phone number makes the export crash;
- the finance team wants the same contacts as JSON for their import tool.

## Proposed fix
Rework `src/export.py`.

## Done when
- Export works.
EOF
cat > issues/README.md <<'EOF'
# Issues

| # | Priority | Issue |
|---|---|---|
| [001](001-export-improvements.md) | P2 | Export improvements |
EOF
printf '__pycache__/\n' > .gitignore
git add -A && git commit -qm "Initial export module and backlog"
