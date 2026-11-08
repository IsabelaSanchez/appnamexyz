#!/bin/bash
set -euo pipefail
release_dir="$(cd "$(dirname "$0")/.." && pwd)"
export APP_ENV_FILE="${APP_ENV_FILE:-/opt/accessibility/config/application.env}"
set -a
source "$APP_ENV_FILE"
set +a
export RELEASE_TAG="${RELEASE_TAG:-$(git -C "$release_dir" rev-parse --short HEAD 2>/dev/null || date +%s)}"
compose=(docker compose --env-file "$APP_ENV_FILE" -f "$release_dir/infra/docker-compose.yml")
exec 9>/opt/accessibility/deployment.lock
flock -n 9
previous="$(readlink -f /opt/accessibility/current || true)"
"${compose[@]}" config --quiet
"${compose[@]}" build
if "${compose[@]}" up -d --wait --wait-timeout 180 && curl --fail --max-time 20 --retry 8 --retry-delay 5 "https://$APP_HOST/api/v1/health"; then
    install -m 600 "$release_dir/infra/sync_deployment.py" /opt/accessibility/config/sync_deployment.py
    ln -sfn "$release_dir" /opt/accessibility/current
    printf '%s\n' "$RELEASE_TAG" > /opt/accessibility/config/current-release
else
    if [ -n "$previous" ] && [ -f "$previous/infra/docker-compose.yml" ]; then
        export RELEASE_TAG="$(cat /opt/accessibility/config/current-release)"
        docker compose --env-file "$APP_ENV_FILE" -f "$previous/infra/docker-compose.yml" up -d --no-build --wait
    fi
    exit 1
fi
