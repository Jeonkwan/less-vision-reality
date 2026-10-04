#!/usr/bin/env bash
# Run remotely over SSH. Bounded diagnostics only; no restarts or configuration writes.
set -u
date -u
uptime
free -h
df -h /
swapon --show
last -x -n 8 || true
sudo -n systemctl is-active docker || true
sudo -n cloud-init status || true
sudo -n ss -lntp '( sport = :443 )' || true
sudo -n docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' || true
sudo -n docker inspect xray --format '{{json .State}}' || true
sudo -n docker inspect xray --format 'RestartCount={{.RestartCount}} Image={{.Config.Image}} RestartPolicy={{.HostConfig.RestartPolicy.Name}}' || true
sudo -n journalctl -k --since '48 hours ago' --no-pager --grep='Out of memory|oom-kill|Killed process' -n 30 || true
sudo -n journalctl -u docker --since '48 hours ago' --no-pager -n 30 || true
sudo -n ufw status || true
sudo -n python3 - <<'PY'
import hashlib,json,pathlib
p=pathlib.Path('/opt/xray/config/config.json')
if not p.exists():
 print('Xray config missing at expected path')
else:
 d=json.loads(p.read_text())
 for inbound in d.get('inbounds',[]):
  r=inbound.get('streamSettings',{}).get('realitySettings',{})
  print('Listener:',inbound.get('listen'),inbound.get('port'))
  print('REALITY destination:',r.get('target',r.get('dest')))
  print('REALITY SNI names:',r.get('serverNames'))
  print('Expected supplied short ID accepted:','f2a5aebaa3acb89d' in r.get('shortIds',[]))
  print('Expected supplied UUID accepted:',any(hashlib.sha256(c.get('id','').encode()).hexdigest()[:12]=='6318c1ff6c69' for c in inbound.get('settings',{}).get('clients',[])))
  print('Expected supplied public key configured:',r.get('publicKey')=='c8UlOfsM1xr3sXJB51xsZkVfsmQf4iGYwb9TRvZZ038')
PY
timeout 12 openssl s_client -connect web.wechat.com:443 -servername web.wechat.com -tls1_3 -brief </dev/null || true
