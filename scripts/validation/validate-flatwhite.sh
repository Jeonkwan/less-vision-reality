#!/usr/bin/env bash
set -euo pipefail
sudo -n python3 - <<'CHECK'
import pathlib,subprocess,json,re,shutil
run=lambda *args:subprocess.check_output(args,text=True).strip()
p=pathlib.Path('/var/lib/proxy-bootstrap')
assert (p/'complete').exists(),'Bootstrap incomplete'
kernel=run('uname','-r');assert kernel==(p/'kernel-at-provisioning').read_text().strip(),'Kernel changed since provisioning'
assert 'kho=off' in pathlib.Path('/proc/cmdline').read_text().split()
assert not pathlib.Path('/etc/default/grub.d/99-proxy-kernel.cfg').exists()
assert not any('linux' in h for h in run('apt-mark','showhold').splitlines())
assert not run('dpkg','--audit')
status=subprocess.run(['systemctl','is-failed','proxy-bootstrap.service'],text=True,capture_output=True)
assert status.stdout.strip()!='failed'
conf=run('apt-config','dump')
for k,v in {'APT::Periodic::Enable':'0','APT::Periodic::Update-Package-Lists':'0','APT::Periodic::Download-Upgradeable-Packages':'0','APT::Periodic::Unattended-Upgrade':'0','Unattended-Upgrade::Automatic-Reboot':'false'}.items():
 assert re.search(r'^'+re.escape(k)+r' "'+v+r'";',conf,re.M),k
for unit in ['apt-daily.timer','apt-daily-upgrade.timer','apt-daily.service','apt-daily-upgrade.service']:
 r=subprocess.run(['systemctl','is-enabled',unit],capture_output=True,text=True)
 assert r.stdout.strip()=='masked',(unit,r.stdout)
 if unit.endswith('.timer'):
  r=subprocess.run(['systemctl','is-active',unit],capture_output=True,text=True);assert r.stdout.strip()=='inactive',(unit,r.stdout)
u=subprocess.run(['systemctl','is-enabled','unattended-upgrades.service'],capture_output=True,text=True);assert u.stdout.strip()=='disabled',u.stdout
if pathlib.Path('/usr/bin/snap').exists():
 assert 'hold: forever' in run('snap','refresh','--time'),'Snap automatic refresh not held'
for unit in ['fwupd-refresh.timer','update-notifier-download.timer','update-notifier-motd.timer']:
 r=subprocess.run(['systemctl','show',unit,'--property=LoadState','--value'],capture_output=True,text=True)
 if r.stdout.strip()!='not-found':
  r=subprocess.run(['systemctl','is-enabled',unit],capture_output=True,text=True);assert r.stdout.strip()=='masked',(unit,r.stdout)
# Existing provisioning transactions must be finished by the readiness marker.
for unit in ['apt-daily.service','apt-daily-upgrade.service']:
 r=subprocess.run(['systemctl','is-active',unit],capture_output=True,text=True);assert r.stdout.strip()=='inactive',(unit,r.stdout)
assert not pathlib.Path('/opt/venv-gcp-proxy').exists(),'Basic VM unnecessarily installed local Ansible'
for root in ['/etc/cron.d','/var/spool/cron/crontabs']:
 p=pathlib.Path(root)
 if p.exists():
  for f in p.iterdir():
   if f.is_file():
    for l in f.read_text(errors='replace').splitlines():
     if l.strip() and not l.lstrip().startswith('#'):assert not re.search(r'\b(reboot|shutdown)\b',l),(f.name,l)
j=run('systemd-analyze','cat-config','systemd/journald.conf');effective={}
for l in j.splitlines():
 if l.strip() and not l.lstrip().startswith('#') and '=' in l:
  k,v=l.split('=',1);effective[k.strip()]=v.strip()
assert effective.get('SystemMaxUse')=='100M' and effective.get('RuntimeMaxUse')=='32M'
r=subprocess.run(['journalctl','-k','-b','--no-pager','-o','cat','--grep=Out of memory|oom-kill'],text=True,capture_output=True)
assert r.returncode in (0,1) and not any(w in r.stdout for w in ['Out of memory','oom-kill']),r.stdout
assert shutil.disk_usage('/').used/shutil.disk_usage('/').total<.9
mem=pathlib.Path('/proc/meminfo').read_text();print('Kernel retained from current blueprint:',kernel);print('Effective boot parameters:',pathlib.Path('/proc/cmdline').read_text().strip())
print('CMA:',[l for l in mem.splitlines() if l.startswith('Cma')]);print('Automatic updates disabled; package state clean; no kernel holds or routine reboots; journal capped; minimal bootstrap confirmed')
CHECK
uname -r
free -h
df -h /
if [ "${POLICY_ONLY:-0}" != 1 ]; then
 sudo -n python3 - <<'CHECK'
import json,subprocess,pathlib
x=json.loads(subprocess.check_output(['docker','inspect','xray'],text=True))[0]
assert x['State']['Running'] and not x['State']['OOMKilled']
assert x['HostConfig']['RestartPolicy']['Name']=='unless-stopped'
assert x['HostConfig']['LogConfig']=={'Type':'json-file','Config':{'max-size':'10m','max-file':'3'}}
p=pathlib.Path(x['LogPath']);files=[p]+list(p.parent.glob(p.name+'.*'));sizes=[f.stat().st_size for f in files]
assert len(files)<=3 and sum(sizes)<=30*1024**2+3*65536
print('Xray container:',x['Id'],x['State']['StartedAt'],'RestartCount',x['RestartCount'])
print('Xray image and digest:',x['Config']['Image'],x['Image']);print('Retained Xray log bytes:',sum(sizes))
print(subprocess.check_output(['docker','version','--format','{{.Server.Version}}'],text=True).strip())
CHECK
fi
