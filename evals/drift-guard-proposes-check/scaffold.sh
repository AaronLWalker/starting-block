set -euo pipefail
git init -q -b main
git config user.name "Eval Bot"
git config user.email "eval@example.com"

cat > docker-compose.yml <<'EOF'
services:
  web:
    image: nginx:1.27
    ports: ["8080:80"]
  api:
    image: ghcr.io/acme/api:2.3
    ports: ["9000:9000"]
  worker:
    image: ghcr.io/acme/worker:2.3
EOF
cat > README.md <<'EOF'
# acme stack

| Service | Port | What it does |
|---|---|---|
| web | 8080 | Public site |
| api | 8000 | REST API |
| scheduler | - | Cron jobs |
EOF
git add -A && git commit -qm "Initial stack"
