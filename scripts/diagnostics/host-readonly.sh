#!/usr/bin/env bash
set -u
date -u
uptime
free -h
df -h /
swapon --show
sudo -n cloud-init status || true
sudo -n systemctl show xray -p ActiveState -p MainPID -p NRestarts -p ExecMainStartTimestampMonotonic || true
sudo -n ss -lntp '( sport = :443 )' || true
sudo -n python3 - <<'PYLOG'
import re,subprocess
r=subprocess.run(['journalctl','-u','xray','--since','48 hours ago','--no-pager','-n','80'],capture_output=True,text=True,timeout=15)
s=re.sub(r'(?i)\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b','[UUID redacted]',r.stdout)
s=re.sub(r'(?i)("(?:privateKey|publicKey|shortIds)"\s*:\s*)("[^"]*"|\[[^\]]*\])',r'\1"[redacted]"',s)
print(s)
PYLOG
sudo -n journalctl -k --since '48 hours ago' --no-pager --grep='Out of memory|oom-kill|Killed process' -n 30 || true
sudo -n journalctl --disk-usage || true
