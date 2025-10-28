#!/bin/sh
set -eu
apk add --no-cache util-linux >/dev/null 2>&1
UUID=$(uuidgen | tr -d '\r')
printf "value=%s\n" "$UUID" >>"$GITHUB_OUTPUT"
