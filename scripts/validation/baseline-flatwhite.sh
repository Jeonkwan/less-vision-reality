#!/usr/bin/env bash
set -euo pipefail
mode=${1:?baseline or compare}
sudo -n python3 - "$mode" <<'PY'
import pathlib,subprocess,json,sys
x=json.loads(subprocess.check_output(['docker','inspect','xray'],text=True))[0]
state={'boot':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'kernel':subprocess.check_output(['uname','-r'],text=True).strip(),'container':x['Id'],'started':x['State']['StartedAt'],'restarts':x['RestartCount']}
p=pathlib.Path('/var/lib/proxy-validation/deploy-baseline.json')
if sys.argv[1]=='baseline':
 p.parent.mkdir(exist_ok=True);p.write_text(json.dumps(state));p.chmod(0o600);print('Captured baseline:',state)
else:
 assert state==json.loads(p.read_text()),'Deployment restarted or replaced host/container';print('Idempotent deployment retained baseline:',state)
PY
