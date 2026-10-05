#!/usr/bin/env python3
"""Selected-host diagnostics and authenticated checks; no credentials in output."""
import json,os,pathlib,shlex,socket,subprocess,tempfile,time

def write_private_key(path,value):
 path.write_text(value.strip()+'\n')
 path.chmod(0o600)

def main():
 mode=os.environ.get('XRAY_DEPLOYMENT_MODE','native');assert mode in ['native','docker']
 target=os.environ['TARGET'];stage=os.environ['STAGE'];address=os.environ['ADDRESS'];assert target in ['cream','flatwhite','decaf','americano','latte'];socket.inet_aton(address)
 hostname=os.environ.get('VALIDATION_HOSTNAME') or target+'.mokamaker.site'
 assert hostname in [target+'.mokamaker.site',target+'.'+address+'.sslip.io'],'Unapproved test hostname'
 if stage in ['suite','baseline','logs','recovery','reboot']:
  resolved={x[4][0] for x in socket.getaddrinfo(hostname,443,type=socket.SOCK_STREAM)}
  assert resolved=={address},'Refusing host mutations: selected hostname does not resolve to the expected IP'
 if stage=='suite':
  for part in ['inspect','logs','recovery','reboot','inspect','baseline']:
   subprocess.run(['python3',__file__],env={**os.environ,'STAGE':part},check=True)
  return
 with tempfile.TemporaryDirectory(prefix='native-ssh-') as tmp:
  p=pathlib.Path(tmp);key=p/'key';write_private_key(key,os.environ['SSH_PRIVATE_KEY'])
  ssh=['ssh','-i',str(key),'-o','BatchMode=yes','-o','IdentitiesOnly=yes','-o','ConnectTimeout=10','-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(p/'known_hosts'),'ubuntu@'+address]
  def remote(cmd,check=True,timeout=100):
   r=subprocess.run(ssh+[cmd],capture_output=True,text=True,timeout=timeout)
   if check and r.returncode:raise RuntimeError('Remote check failed: '+r.stderr[:1000])
   return r.stdout.strip()
  def clients():
   subprocess.run(['python3','scripts/check-native-clients.py','--nodes',target,'--address',address],check=True)
   resolved={x[4][0] for x in socket.getaddrinfo(hostname,443,type=socket.SOCK_STREAM)}
   assert resolved=={address},'Hostname not yet resolving to expected instance'
   subprocess.run(['python3','scripts/check-native-clients.py','--nodes',target,'--address',hostname],check=True)
  if stage=='bootstrap':
   print(remote("uname -r; cat /proc/cmdline; sudo -n cloud-init status; sudo -n systemctl status proxy-bootstrap.service --no-pager || true; sudo -n journalctl -u proxy-bootstrap.service -n 35 --no-pager; sudo -n tail -40 /var/log/cloud-init-output.log"));return
  if stage=='ready':
   for attempt in range(90):
    # Commands with no stdout need a positive marker.
    r=remote("test -f /var/lib/proxy-bootstrap/complete && grep -qw kho=off /proc/cmdline && ! sudo -n systemctl is-failed --quiet proxy-bootstrap.service && echo READY",False,30)
    if r=='READY':break
    print('Waiting for bootstrap',attempt+1,flush=True);time.sleep(10)
   else:raise RuntimeError('Bootstrap did not complete')
   print(remote("uname -r; sudo -n cloud-init status; sudo -n systemctl show proxy-bootstrap.service -p Result; sudo -n journalctl -u proxy-bootstrap.service -n 8 --no-pager"));return
  if stage=='clients':clients();return
  if stage=='inspect':
   code='import os\nos.environ[\"XRAY_DEPLOYMENT_MODE\"]='+repr(mode)+'\nos.environ[\"XRAY_REQUIRE_MINIMAL_HOST\"]='+repr(os.environ.get('XRAY_REQUIRE_MINIMAL_HOST','false'))+'\n'+pathlib.Path('scripts/validate-native-host.py').read_text()
   print(remote("sudo -n python3 - <<'PY'\n"+code+"\nPY"));clients();return
  def baseline():
   if mode=='docker':
    code="import json,pathlib,subprocess;d=json.loads(subprocess.check_output(['docker','inspect','xray'],text=True))[0];print(json.dumps(dict(mode='docker',Id=d['Id'],MainPID=str(d['State']['Pid']),StartedAt=d['State']['StartedAt'],RestartCount=d['RestartCount'],boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip())))"
    return json.loads(remote("sudo -n python3 -c "+shlex.quote(code)))
   return json.loads(remote("sudo -n python3 - <<'PY'\nimport json,pathlib,subprocess\nx={line.split('=',1)[0]:line.split('=',1)[1] for line in subprocess.check_output(['systemctl','show','xray','-p','MainPID','-p','ExecMainStartTimestampMonotonic','-p','NRestarts'],text=True).splitlines()};x['boot']=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip();print(json.dumps(x))\nPY"))
  if stage in ['baseline','compare']:
   current=baseline()
   if stage=='baseline':print(remote("sudo -n install -d -m 0700 /var/lib/xray-validation; printf '%s' '"+json.dumps(current)+"' | sudo -n tee /var/lib/xray-validation/baseline.json >/dev/null; echo Baseline_saved"))
   else:assert current==json.loads(remote('sudo -n cat /var/lib/xray-validation/baseline.json')),'Unchanged deployment restarted service/host'
   print('Baseline',current);clients();return
  if stage in ['reboot','recovery']:
   before=baseline()
   if stage=='reboot':remote("sudo -n shutdown -r now",False,30)
   else:remote('sudo -n systemctl kill --signal=SIGKILL xray' if mode=='native' else 'sudo -n kill -KILL '+before['MainPID'])
   for attempt in range(60):
    time.sleep(3)
    try:
     now=baseline();active=remote('systemctl is-active xray' if mode=='native' else "sudo -n docker inspect --format '{{if .State.Running}}active{{end}}' xray",False)
     if active=='active' and now['MainPID']!='0' and (now['boot']!=before['boot'] if stage=='reboot' else now['MainPID']!=before['MainPID']):break
    except (RuntimeError,subprocess.TimeoutExpired):pass
   else:raise RuntimeError('Service did not recover')
   print('Recovery PASS',stage,before,now);clients();return
  if stage=='logs' and mode=='docker':
   # Inject stdout through the verified container process; do not require a shell
   # or auxiliary utilities in the official runtime image.
   code="""import json,pathlib,subprocess,os
before=json.loads(subprocess.check_output(['docker','inspect','xray'],text=True))[0]
assert before['Config']['Labels']['com.docker.compose.project']=='xray'
assert before['Config']['Labels']['com.docker.compose.service']=='xray'
assert before['Config']['Labels']['com.docker.compose.project.working_dir']=='/opt/xray'
assert before['Config']['Labels']['com.docker.compose.project.config_files']=='/opt/xray/docker-compose.yml'
assert before['HostConfig']['LogConfig']=={'Type':'json-file','Config':{'max-size':'10m','max-file':'3'}}
with open('/proc/'+str(before['State']['Pid'])+'/fd/1','wb',buffering=0) as output:
 for i in range(40000):output.write(os.urandom(768).hex().encode()+b'\\n')
import time;time.sleep(3)
after=json.loads(subprocess.check_output(['docker','inspect','xray'],text=True))[0]
assert (before['Id'],before['State']['Pid'])==(after['Id'],after['State']['Pid'])
log=pathlib.Path(after['LogPath']);files=list(log.parent.glob(log.name+'*'))
assert len(files)>1 and len(files)<=3,'Docker logs did not rotate within max-file'
assert sum(p.stat().st_size for p in files)<=31*1024**2,'Docker logs exceeded budget and slack'
print('Docker log rotation PASS; files',len(files),'bytes',sum(p.stat().st_size for p in files))
"""
   print(remote("sudo -n python3 - <<'PY'\n"+code+"\nPY",timeout=150));clients();return
  if stage=='logs':
   before=int(remote("sudo -n find /var/log/journal -name '*@*.journal' | wc -l"))
   print(remote("sudo -n systemd-run --wait --unit=xray-journal-probe --property=StandardOutput=journal --property=LogRateLimitIntervalSec=0 /usr/bin/python3 -c 'import os,base64; [print(base64.b64encode(os.urandom(768)).decode()) for i in range(45000)]'",timeout=150))
   code="""import pathlib,subprocess
subprocess.run(['journalctl','--sync'],check=True)
files=list(pathlib.Path('/var/log/journal').rglob('*.journal'))
assert len([p for p in files if '@' in p.name])>BEFORE,'Journal did not rotate'
size=sum(x.stat().st_size for x in files)
print('Journal measurement; files',len(files),'bytes',size,flush=True)
print(subprocess.check_output(['journalctl','--disk-usage'],text=True),flush=True)
assert size<=115*1024**2,'Persistent journal exceeded budget and file slack'
print('Journal rotation PASS; files',len(files),'bytes',size)
print(subprocess.check_output(['journalctl','--disk-usage'],text=True))
"""
   code=code.replace('BEFORE',str(before))
   print(remote("sudo -n python3 - <<'PY'\n"+code+"\nPY"));clients();return
  raise RuntimeError('Unknown stage')
if __name__=='__main__':main()
