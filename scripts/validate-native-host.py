"""Execute on selected VM via SSH; output only non-secret evidence."""
import pathlib,subprocess,json,shutil,os,hashlib
run=lambda *a:subprocess.check_output(a,text=True).strip()
assert pathlib.Path('/var/lib/proxy-bootstrap/complete').exists()
assert 'kho=off' in pathlib.Path('/proc/cmdline').read_text().split()
assert run('uname','-r')==pathlib.Path('/var/lib/proxy-bootstrap/kernel-at-provisioning').read_text().strip()
assert not run('dpkg','--audit')
assert not any('linux' in x for x in run('apt-mark','showhold').splitlines())
mode=os.environ.get('XRAY_DEPLOYMENT_MODE','native')
assert mode in ['native','docker']
assert not shutil.which('ansible')
if os.environ.get('XRAY_REQUIRE_MINIMAL_HOST')=='true':
 assert mode=='native' and not shutil.which('docker')
assert not pathlib.Path('/opt/venv-gcp-proxy').exists()
if mode=='native':
 assert run('systemctl','is-active','xray')=='active'
 assert run('systemctl','is-enabled','xray')=='enabled'
 assert run('systemctl','show','xray','-p','User','--value')=='xray'
 assert pathlib.Path('/usr/local/etc/xray/config.json').stat().st_mode & 0o777==0o640
 if shutil.which('docker'):
  assert not run('docker','ps','--filter','label=com.docker.compose.project=xray','--filter','label=com.docker.compose.service=xray','-q')
else:
 assert shutil.which('docker')
 assert subprocess.run(['systemctl','is-active','--quiet','xray']).returncode!=0
 assert subprocess.run(['systemctl','is-enabled','--quiet','xray']).returncode!=0
 data=json.loads(run('docker','inspect','xray'))[0]
 assert data['State']['Running'] and not data['State']['Restarting']
 assert data['Config']['Image']=='ghcr.io/xtls/xray-core:25.10.15'
 labels=data['Config']['Labels']
 assert labels['com.docker.compose.project']=='xray'
 assert labels['com.docker.compose.service']=='xray'
 assert labels['com.docker.compose.project.working_dir']=='/opt/xray'
 assert labels['com.docker.compose.project.config_files']=='/opt/xray/docker-compose.yml'
 assert any(m['Source']=='/opt/xray/config' and m['Destination']=='/usr/local/etc/xray' for m in data['Mounts'])
 assert data['HostConfig']['LogConfig']=={'Type':'json-file','Config':{'max-size':'10m','max-file':'3'}}
 assert data['HostConfig']['RestartPolicy']['Name']=='unless-stopped'
 assert pathlib.Path('/opt/xray/config/config.json').stat().st_mode & 0o777==0o600
 print('Container',data['Id'],'image digest',data['Image'])
for unit in ['apt-daily.timer','apt-daily-upgrade.timer','apt-daily.service','apt-daily-upgrade.service']:
 r=subprocess.run(['systemctl','is-enabled',unit],text=True,capture_output=True);assert r.stdout.strip()=='masked'
conf=run('systemd-analyze','cat-config','systemd/journald.conf');effective={}
for line in conf.splitlines():
 if line.strip() and not line.lstrip().startswith('#') and '=' in line:
  k,v=line.split('=',1);effective[k.strip()]=v.strip()
assert all(effective.get(k)==v for k,v in {'Storage':'persistent','SystemMaxUse':'100M','RuntimeMaxUse':'32M','SystemMaxFileSize':'10M','MaxRetentionSec':'7day','ForwardToSyslog':'no'}.items()),str({k:effective.get(k) for k in ['Storage','SystemMaxUse','RuntimeMaxUse','SystemMaxFileSize','MaxRetentionSec','ForwardToSyslog']})
assert 'hold: forever' in run('snap','refresh','--time') if shutil.which('snap') else True
if mode=='native':
 print(run('/usr/local/bin/xray','version'))
 print('Xray binary SHA-256',hashlib.sha256(pathlib.Path('/usr/local/bin/xray').read_bytes()).hexdigest())
 print(run('systemctl','show','xray','-p','MainPID','-p','NRestarts','-p','ExecMainStartTimestampMonotonic'))
else:
 print(run('docker','exec','xray','/usr/local/bin/xray','version'))
print('Kernel',run('uname','-r'))
print(mode,'host policy, permissions and bounded logs PASS')
