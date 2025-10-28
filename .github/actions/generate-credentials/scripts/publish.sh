#!/bin/sh
set -eu

: "${UUID:?UUID environment variable is required}"
: "${SHORT_IDS:?SHORT_IDS environment variable is required}"
: "${PRIVATE_KEY:?PRIVATE_KEY environment variable is required}"
: "${PUBLIC_KEY:?PUBLIC_KEY environment variable is required}"

OUTPUT_DIR="${RUNNER_TEMP:-/tmp}"
mkdir -p "$OUTPUT_DIR"
OUTPUT_FILE="$OUTPUT_DIR/xray-credentials.txt"

# Write credentials to an artifact file
set -- $SHORT_IDS
{
  echo "XRAY_UUID: $UUID"
  echo "XRAY_SHORT_IDS:"
  for short_id in "$@"; do
    echo "  - $short_id"
  done
  echo "XRAY_PRIVATE_KEY: $PRIVATE_KEY"
  echo "XRAY_PUBLIC_KEY: $PUBLIC_KEY"
} >"$OUTPUT_FILE"

echo "::group::Xray Reality Credentials"
cat "$OUTPUT_FILE"
echo "::endgroup::"

# Append credentials to the GitHub step summary
set -- $SHORT_IDS
{
  echo "### Generated Xray Credentials"
  echo
  echo "- **UUID:** \`$UUID\`"
  echo "- **Short IDs:**"
  for short_id in "$@"; do
    echo "  - \`$short_id\`"
  done
  echo "- **Reality Private Key:** \`$PRIVATE_KEY\`"
  echo "- **Reality Public Key:** \`$PUBLIC_KEY\`"
  echo
  echo "> Copy the values above into your inventory or secret manager."
} >>"$GITHUB_STEP_SUMMARY"
