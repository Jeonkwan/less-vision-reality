#!/bin/sh
set -eu

IMAGE="${XRAY_IMAGE:-ghcr.io/xtls/xray-core:25.10.15}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker binary not found in PATH" >&2
  exit 1
fi

if ! XRAY_KEYS=$(docker run --rm "$IMAGE" x25519 2>&1); then
  status=$?
  echo "failed to execute xray container (exit $status)" >&2
  exit "$status"
fi

PRIVATE_KEY=""
PUBLIC_KEY=""

# Parse the CLI output. Newer Xray releases label the public key as "Password"
# while older versions print "Public key". Handle both along with the original
# spaced variants.
while IFS= read -r line; do
  # Ignore empty lines
  [ -z "$line" ] && continue

  key_part=${line%%:*}
  value_part=${line#*:}
  # If there is no separator, skip the line
  [ "$key_part" = "$line" ] && continue

  # Normalise the key label (remove spaces, lower-case)
  normalised_key=$(printf "%s" "$key_part" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')
  # Trim whitespace and carriage returns from the value
  value=$(printf "%s" "$value_part" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')
  value=$(printf "%s" "$value" | tr -d '\r')

  case "$normalised_key" in
    privatekey|private)
      if [ -z "$PRIVATE_KEY" ]; then
        PRIVATE_KEY="$value"
      fi
      ;;
    publickey|public|password)
      if [ -z "$PUBLIC_KEY" ]; then
        PUBLIC_KEY="$value"
      fi
      ;;
  esac
done <<OUT
$XRAY_KEYS
OUT

if [ -z "$PRIVATE_KEY" ] || [ -z "$PUBLIC_KEY" ]; then
  echo "failed to parse xray key pair from output:" >&2
  printf '%s\n' "$XRAY_KEYS" >&2
  exit 1
fi

printf "private=%s\n" "$PRIVATE_KEY" >>"$GITHUB_OUTPUT"
printf "public=%s\n" "$PUBLIC_KEY" >>"$GITHUB_OUTPUT"
