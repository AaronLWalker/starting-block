set -euo pipefail
git init -q -b main
git config user.name "Eval Bot"
git config user.email "eval@example.com"

mkdir -p config
# The token is built from two pieces so this fixture doesn't itself look like a leaked secret.
TOKEN="ghp_""Zq3x9TkLm2Vb7Wc4Nd8Rf1Gh5Js6Kp0Yt2Ae"
printf '{"deploy_host": "nas.local", "github_token": "%s"}\n' "$TOKEN" > config/settings.json
cat > deploy.py <<'EOF'
import json
settings = json.load(open("config/settings.json"))
EOF
git add -A && git commit -qm "Add deploy settings"
cat > config/settings.json <<'EOF'
{"deploy_host": "nas.local"}
EOF
cat > deploy.py <<'EOF'
import json, os
settings = json.load(open("config/settings.json"))
token = os.environ["GITHUB_TOKEN"]
EOF
git add -A && git commit -qm "Read the token from the environment"
