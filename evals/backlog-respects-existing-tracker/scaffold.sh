set -euo pipefail
git init -q -b main
git config user.name "Eval Bot"
git config user.email "eval@example.com"
mkdir -p src
cat > src/export.py <<'PY'
def to_csv(rows):
    lines = ["name,email"]
    for r in rows:
        lines.append(",".join([r["name"], r["email"]]))
    return "\n".join(lines) + "\n"
PY
cat > CONTRIBUTING.md <<'MD'
# Contributing

We track bugs and features in GitHub Issues: https://github.com/acme/contacts/issues
Use the "Bug" template and add a priority label (P1, P2 or P3).
MD
git add -A && git commit -qm "Initial commit"
