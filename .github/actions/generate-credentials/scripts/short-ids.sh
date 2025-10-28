#!/bin/sh
set -eu
apk add --no-cache openssl >/dev/null 2>&1
IDS=""
for _ in 1 2 3; do
  ID=$(openssl rand -hex 8 | tr -d '\r\n')
  if [ -z "$IDS" ]; then
    IDS="$ID"
  else
    IDS="$IDS $ID"
  fi
done
printf "value=%s\n" "$IDS" >>"$GITHUB_OUTPUT"
