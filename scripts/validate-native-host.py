"""Execute on selected VM via SSH; output only non-secret evidence."""
import pathlib,subprocess,json,shutil,os,hashlib
run=lambda *a:subprocess.check_output(a,text=True).strip()
assert pathlib.Path('/var/lib/proxy-bootstrap/complete').exists()
assert 'kho=off' in pathlib.Path('/proc/cmdline').read_text().split()
assert run('uname','-r')==pathlib.Path('/var/lib/proxy-bootstrap/kernel-at-provisioning').read_text().strip()
assert not run('dpkg','--audit')
assert not any('linux' in x for x in run('apt-mark','showhold').splitlines())
assert not shutil.which('docker') and not shutil.which('ansible')
assert not pathlib.Path('/opt/venv-gcp-proxy').exists()
assert run('systemctl','is-active','xray')=='active'
assert run('systemctl','is-enabled','xray')=='enabled'
assert run('systemctl','show','xray','-p','User','--value')=='xray'
assert pathlib.Path('/usr/local/etc/xray/config.json').stat().st_mode & 0o777==0o640
for unit in ['apt-daily.timer','apt-daily-upgrade.timer','apt-daily.service','apt-daily-upgrade.service']:
 r=subprocess.run(['systemctl','is-enabled',unit],text=True,capture_output=True);assert r.stdout.strip()=='masked'
conf=run('systemd-analyze','cat-config','systemd/journald.conf');effective={}
for line in conf.splitlines():
 if line.strip() and not line.lstrip().startswith('#') and '=' in line:
  k,v=line.split('=',1);effective[k.strip()]=v.strip()
assert all(effective.get(k)==v for k,v in {'Storage':'persistent','SystemMaxUse':'100M','RuntimeMaxUse':'32M','SystemMaxFileSize':'10M','MaxRetentionSec':'7day','ForwardToSyslog':'no'}.items()),str({k:effective.get(k) for k in ['Storage','SystemMaxUse','RuntimeMaxUse','SystemMaxFileSize','MaxRetentionSec','ForwardToSyslog']})
assert 'hold: forever' in run('snap','refresh','--time') if shutil.which('snap') else True
print(run('/usr/local/bin/xray','version'))
print('Xray binary SHA-256',hashlib.sha256(pathlib.Path('/usr/local/bin/xray').read_bytes()).hexdigest())
print('Kernel',run('uname','-r'))
print(run('systemctl','show','xray','-p','MainPID','-p','NRestarts','-p','ExecMainStartTimestampMonotonic'))
print('Native host policy, permissions and bounded persistent journal PASS')
