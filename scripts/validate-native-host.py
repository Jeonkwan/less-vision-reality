"""Execute on selected VM via SSH; output only non-secret evidence."""
import pathlib,subprocess,json,shutil,os,hashlib,grp,pwd
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
 assert run('systemctl','show','xray','-p','Group','--value')=='xray'
 for option,value in {'CapabilityBoundingSet':'cap_net_bind_service','AmbientCapabilities':'cap_net_bind_service','NoNewPrivileges':'yes','ProtectSystem':'strict','ProtectHome':'yes','PrivateTmp':'yes'}.items():
  assert run('systemctl','show','xray','-p',option,'--value')==value,option
 config_stat=pathlib.Path('/usr/local/etc/xray/config.json').stat()
 assert config_stat.st_uid==0 and config_stat.st_gid==grp.getgrnam('xray').gr_gid
 pid=run('systemctl','show','xray','-p','MainPID','--value')
 assert int(pid)>1 and int(run('ps','-o','uid=','-p',pid))==pwd.getpwnam('xray').pw_uid
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
 docker_config=pathlib.Path('/opt/xray/config/config.json').stat()
 assert docker_config.st_mode & 0o777==0o640 and docker_config.st_uid==0 and docker_config.st_gid==65532
 assert data['Config']['User']=='65532'
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
 digest=hashlib.sha256(pathlib.Path('/usr/local/bin/xray').read_bytes()).hexdigest()
 assert digest in ['1d6b0fb6f2348683d59304c9f0bbf3611daa068527159b749374f12da252e78c','8255dd939c34cf966cc91517b6324dd3c8d0bcf49ffac8beca049a38c46845ed']
 print('Reviewed Xray binary SHA-256',digest)
 print(run('systemctl','show','xray','-p','MainPID','-p','NRestarts','-p','ExecMainStartTimestampMonotonic'))
else:
 print(run('docker','exec','xray','/usr/local/bin/xray','version'))
print('Kernel',run('uname','-r'))
print(mode,'host policy, permissions and bounded logs PASS')
