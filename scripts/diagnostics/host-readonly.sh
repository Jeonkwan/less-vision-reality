#!/usr/bin/env bash
set -u
mode="${XRAY_DEPLOYMENT_MODE:-native}"
case "$mode" in native|docker|podman) ;; *) echo 'Invalid Xray runtime' >&2; exit 1 ;; esac
date -u
uptime
free -h
df -h /
swapon --show
sudo -n cloud-init status || true
if [ "$mode" = native ]; then
  sudo -n systemctl show xray -p ActiveState -p MainPID -p NRestarts -p ExecMainStartTimestampMonotonic || true
elif [ "$mode" = podman ]; then
  sudo -n systemctl show xray-podman -p ActiveState -p MainPID -p NRestarts -p ExecMainStartTimestampMonotonic || true
  sudo -n podman --remote=false inspect --format '{{json .State}}' xray-podman || true
else
  sudo -n docker inspect --format '{{json .State}}' xray || true
fi
sudo -n ss -lntp '( sport = :443 )' || true
sudo -n python3 - "$mode" <<'PYLOG'
import re,subprocess,sys
cmd=['journalctl','-u','xray','--since','48 hours ago','--no-pager','-n','80'] if sys.argv[1]=='native' else ['docker','logs','--tail','80','xray']
if sys.argv[1]=='podman':cmd=['journalctl','CONTAINER_NAME=xray-podman','--since','48 hours ago','--no-pager','-n','80']
r=subprocess.run(cmd,capture_output=True,text=True,timeout=15)
s=re.sub(r'(?i)\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b','[UUID redacted]',r.stdout+r.stderr)
s=re.sub(r'(?i)("(?:privateKey|publicKey|shortIds)"\s*:\s*)("[^"]*"|\[[^\]]*\])',r'\1"[redacted]"',s)
print(s)
PYLOG
sudo -n journalctl -k --since '48 hours ago' --no-pager --grep='Out of memory|oom-kill|Killed process' -n 30 || true
sudo -n journalctl --disk-usage || true
