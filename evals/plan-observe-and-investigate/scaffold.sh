set -euo pipefail
git init -q -b main
git config user.name "Eval Bot"
git config user.email "eval@example.com"

mkdir -p src tests issues logs
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
printf '__pycache__/\n' > .gitignore
git add -A && git commit -qm "Initial export module"

cat > src/export.py <<'EOF'
"""Export contacts to CSV."""
import csv
import io


def to_csv(rows):
    """rows: list of dicts with name, email, phone."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["name", "email", "phone"])
    for r in rows:
        writer.writerow([r["name"], r["email"], r["phone"]])
    return out.getvalue()
EOF
git add -A && git commit -qm "Quote fields with the csv module"

cat > logs/export.log <<'EOF'
2026-09-27 02:00:03 nightly export: 412 rows; mail failed: SMTP timeout after 30s
2026-09-28 02:00:02 nightly export: 415 rows; mail failed: SMTP timeout after 30s
2026-09-29 02:00:04 nightly export: 415 rows; mail failed: SMTP timeout after 30s
2026-09-30 11:12:40 deploy: mail timeout raised to 120s, retries 3
2026-10-01 02:00:03 nightly export: 418 rows; mail sent
2026-10-02 02:00:02 nightly export: 418 rows; mail sent
2026-10-03 02:00:05 nightly export: 420 rows; mail sent
2026-10-04 02:00:03 nightly export: 421 rows; mail sent
2026-10-05 02:00:04 nightly export: 421 rows; mail sent
2026-10-06 02:00:02 nightly export: 424 rows; mail sent
2026-10-07 02:00:03 nightly export: 424 rows; mail sent
EOF
cat > issues/001-nightly-export-mail-times-out.md <<'EOF'
---
status: open
priority: P1
area: export
opened: 2026-09-27
---

# Nightly export mail times out

## Problem
The nightly export's mail failed with `SMTP timeout after 30s` on 2026-09-27, 28 and 29.

## Progress (2026-09-30)
Deployed a 120s timeout with 3 retries.

## Observe
No `SMTP timeout` lines in `logs/export.log` after 2026-10-01.

## Done when
- A week of nightly runs in `logs/export.log` without `SMTP timeout`.
EOF
cat > issues/002-export-is-slow-for-large-accounts.md <<'EOF'
---
status: open
priority: P2
area: export
opened: 2026-10-02
---

# Export is slow for large accounts

## Problem
An account with 40,000 contacts took 95 seconds to export on 2026-10-01; small accounts take under a second.

## Investigate
- Is the time in `to_csv`, in loading the contacts, or in sending the file?
- Does it grow linearly with the row count?

## Done when
- Exporting 40,000 contacts takes under 5 seconds.
EOF
cat > issues/003-export-crashes-on-missing-phone.md <<'EOF'
---
status: open
priority: P2
area: export
opened: 2026-10-03
---

# Export crashes when a contact has no phone

## Problem
`to_csv` reads `r["phone"]`, so a contact without a `phone` key raises `KeyError`.

## Proposed fix
Use `r.get("phone", "")` for each field.

## Done when
- A test exporting `{"name": "Bo", "email": "b@x.org"}` produces `Bo,b@x.org,` and doesn't raise.
- `python3 -m unittest discover -s tests` passes.
EOF
cat > issues/004-csv-export-breaks-on-commas.md <<'EOF'
---
status: open
priority: P3
area: export
opened: 2026-09-10
---

# CSV export breaks when a field contains a comma

## Problem
`to_csv` joins fields with `","` without quoting, so `Smith, Ann` produces four columns.

## Proposed fix
Write rows with the `csv` module.

## Done when
- A name with a comma reads back with `csv.reader` as one field.
EOF
cat > issues/README.md <<'EOF'
# Issues

| # | Priority | Issue |
|---|---|---|
| [001](001-nightly-export-mail-times-out.md) | P1 | Nightly export mail times out |
| [002](002-export-is-slow-for-large-accounts.md) | P2 | Export is slow for large accounts |
| [003](003-export-crashes-on-missing-phone.md) | P2 | Export crashes when a contact has no phone |
| [004](004-csv-export-breaks-on-commas.md) | P3 | CSV export breaks when a field contains a comma |
EOF
git add -A && git commit -qm "Backlog and export log"
