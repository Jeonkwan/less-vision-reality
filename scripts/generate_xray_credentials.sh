#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "[error] docker is required to generate credentials" >&2
  exit 1
fi

SHORT_ID_COUNT=${SHORT_ID_COUNT:-3}

info() { printf '\n%s\n' "$1"; }

info "Generating UUID..."
XRAY_UUID=$(docker run --rm python:3.12-slim python -c 'import uuid; print(uuid.uuid4())')

info "Generating ${SHORT_ID_COUNT} short IDs..."
mapfile -t XRAY_SHORT_IDS < <(docker run --rm -e SHORT_ID_COUNT="${SHORT_ID_COUNT}" python:3.12-slim python - <<'PY'
import os
import secrets
count = int(os.environ.get("SHORT_ID_COUNT", "3"))
for _ in range(count):
    print(secrets.token_hex(4))
PY
)

info "Generating Reality key pair..."
XRAY_KEY_OUTPUT=$(docker run --rm ghcr.io/xtls/xray-core:25.10.15 xray x25519)
XRAY_PRIVATE_KEY=$(printf '%s\n' "$XRAY_KEY_OUTPUT" | awk '/Private key|Private/ {print $NF; exit}')
XRAY_PUBLIC_KEY=$(printf '%s\n' "$XRAY_KEY_OUTPUT" | awk '/Public key|Public|Password/ {print $NF; exit}')

cat <<CREDENTIALS
XRAY_UUID=${XRAY_UUID}
XRAY_SHORT_IDS=$(IFS=,; echo "${XRAY_SHORT_IDS[*]}")
XRAY_PRIVATE_KEY=${XRAY_PRIVATE_KEY}
XRAY_PUBLIC_KEY=${XRAY_PUBLIC_KEY}
CREDENTIALS

info "Done. Store the values securely (e.g., Ansible Vault or secrets manager)."
