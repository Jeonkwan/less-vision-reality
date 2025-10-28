#!/bin/sh
set -eu
XRAY_KEYS=$(xray x25519)
PRIVATE_KEY=$(printf "%s\n" "$XRAY_KEYS" | awk -F": " '/Private key/{print $2}')
PUBLIC_KEY=$(printf "%s\n" "$XRAY_KEYS" | awk -F": " '/Public key/{print $2}')
printf "private=%s\n" "$PRIVATE_KEY" >>"$GITHUB_OUTPUT"
printf "public=%s\n" "$PUBLIC_KEY" >>"$GITHUB_OUTPUT"
