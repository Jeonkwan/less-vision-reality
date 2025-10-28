#!/bin/sh
set -eu
if ! command -v xray >/dev/null 2>&1; then
  echo "xray binary not found in PATH" >&2
  exit 1
fi
XRAY_KEYS=$(xray x25519)
PRIVATE_KEY=$(printf "%s\n" "$XRAY_KEYS" | awk -F": " '/Private key/{print $2}')
PUBLIC_KEY=$(printf "%s\n" "$XRAY_KEYS" | awk -F": " '/Public key/{print $2}')
printf "private=%s\n" "$PRIVATE_KEY" >>"$GITHUB_OUTPUT"
printf "public=%s\n" "$PUBLIC_KEY" >>"$GITHUB_OUTPUT"
