#!/usr/bin/env bash
set -euo pipefail
uname -r
free -h
df -h /
sudo -n systemctl is-active docker systemd-journald
sudo -n python3 - <<'CHECK'
import pathlib,re,subprocess,json
expected=pathlib.Path('/var/lib/proxy-validation/expected-kernel').read_text().strip()
assert subprocess.check_output(['uname','-r'],text=True).strip()==expected
assert not pathlib.Path('/etc/default/grub.d/99-proxy-kernel.cfg').exists()
for root in ('/etc/cron.d','/var/spool/cron/crontabs'):
 p=pathlib.Path(root)
 if p.exists():
  for f in p.iterdir():
   if f.is_file():
    for line in f.read_text(errors='replace').splitlines():
     if line.strip() and not line.lstrip().startswith('#'):
      assert not re.search(r'\b(?:reboot|shutdown)\b',line), (f.name,line)
print('No scheduled reboot/shutdown cron commands')
text=subprocess.check_output(['systemd-analyze','cat-config','systemd/journald.conf'],text=True)
effective={}
for line in text.splitlines():
 if line.strip() and not line.lstrip().startswith('#') and '=' in line:
  k,v=line.split('=',1);effective[k.strip()]=v.strip()
assert effective.get('SystemMaxUse')=='100M',effective
assert effective.get('RuntimeMaxUse')=='32M',effective
print('Effective journal caps:',{k:effective[k] for k in ('SystemMaxUse','RuntimeMaxUse')})
config=json.loads(subprocess.check_output(['docker','inspect','--format={{json .HostConfig.LogConfig}}','xray'],text=True))
assert config['Type']=='json-file' and config['Config']=={'max-size':'10m','max-file':'3'},config
print('Effective Xray log policy:',config)
state=json.loads(subprocess.check_output(['docker','inspect','--format={{json .State}}','xray'],text=True))
assert state['Running'] and not state['OOMKilled'],state
print('Xray running; no OOM kill')
result=subprocess.run(['journalctl','-k','-b','--no-pager','--grep=Out of memory|oom-kill'],text=True,capture_output=True)
assert result.returncode in (0,1),result.stderr
assert 'kernel:' not in result.stdout, 'Boot-time kernel OOM detected'
print('No kernel OOM entries this boot')
logpath=pathlib.Path(subprocess.check_output(['docker','inspect','--format={{.LogPath}}','xray'],text=True).strip())
logfiles=[logpath]+list(logpath.parent.glob(logpath.name+'.*'))
sizes=[f.stat().st_size for f in logfiles]
assert len(sizes)<=3 and sum(sizes)<=30*1024*1024+3*65536,sizes
print('Actual Xray retained log bytes:',sum(sizes))
assert __import__('shutil').disk_usage('/').used/__import__('shutil').disk_usage('/').total<0.90,'Root filesystem above 90 percent usage'
CHECK
sudo -n journalctl --disk-usage
sudo -n systemctl list-timers --all --no-pager
