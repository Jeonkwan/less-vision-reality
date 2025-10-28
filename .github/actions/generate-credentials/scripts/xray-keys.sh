#!/bin/sh
set -eu

if ! command -v xray >/dev/null 2>&1; then
  echo "xray binary not found in PATH" >&2
  exit 1
fi

XRAY_KEYS=$(xray x25519 2>&1)

PRIVATE_KEY=$(printf "%s\n" "$XRAY_KEYS" | sed -n 's/^[Pp]rivate[[:space:]]*key[[:space:]]*:[[:space:]]*//p' | head -n 1 | tr -d '\r')
PUBLIC_KEY=$(printf "%s\n" "$XRAY_KEYS" | sed -n 's/^[Pp]ublic[[:space:]]*key[[:space:]]*:[[:space:]]*//p' | head -n 1 | tr -d '\r')

if [ -z "$PRIVATE_KEY" ] || [ -z "$PUBLIC_KEY" ]; then
  echo "failed to parse xray key pair from output:" >&2
  printf '%s\n' "$XRAY_KEYS" >&2
  exit 1
fi

printf "private=%s\n" "$PRIVATE_KEY" >>"$GITHUB_OUTPUT"
printf "public=%s\n" "$PUBLIC_KEY" >>"$GITHUB_OUTPUT"
