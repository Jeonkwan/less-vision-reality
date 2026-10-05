#!/usr/bin/env bash
set -euo pipefail
cd "$RUNNER_TEMP"
curl -fsSL --max-time 90 https://github.com/SagerNet/sing-box/releases/download/v1.11.4/sing-box-1.11.4-linux-amd64.tar.gz -o sing-box.tar.gz
echo '0bb762ef286b36c2016d9107fc1f089be7a75f6d579b33f067d31e696c05927e  sing-box.tar.gz' | sha256sum -c -
tar -xzf sing-box.tar.gz
echo "$RUNNER_TEMP/sing-box-1.11.4-linux-amd64" >> "$GITHUB_PATH"
curl -fsSL --max-time 90 https://github.com/MetaCubeX/mihomo/releases/download/v1.19.32/mihomo-linux-amd64-compatible-v1.19.32.gz -o mihomo.gz
echo 'ba3ce607747a07f948fc35780e108a4a7c7f552a38b9bd4d115f313ebcb89c20  mihomo.gz' | sha256sum -c -
gzip -dc mihomo.gz > mihomo
chmod 755 mihomo
echo "$RUNNER_TEMP" >> "$GITHUB_PATH"
