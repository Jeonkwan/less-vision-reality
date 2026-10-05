#!/usr/bin/env python3
"""Selected-host diagnostics and authenticated checks; no credentials in output."""
import json,os,pathlib,socket,subprocess,tempfile,time

def main():
 target=os.environ['TARGET'];stage=os.environ['STAGE'];address=os.environ['ADDRESS'];assert target in ['cream','flatwhite','decaf'];socket.inet_aton(address)
 with tempfile.TemporaryDirectory(prefix='native-ssh-') as tmp:
  p=pathlib.Path(tmp);key=p/'key';key.write_text(os.environ['SSH_PRIVATE_KEY'].strip()+'\n');key.chmod(0o600)
  ssh=['ssh','-i',str(key),'-o','BatchMode=yes','-o','IdentitiesOnly=yes','-o','ConnectTimeout=10','-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(p/'known_hosts'),'ubuntu@'+address]
  def remote(cmd,check=True,timeout=100):
   r=subprocess.run(ssh+[cmd],capture_output=True,text=True,timeout=timeout)
   if check and r.returncode:raise RuntimeError('Remote check failed: '+r.stderr[:250])
   return r.stdout.strip()
  def clients():
   subprocess.run(['python3','scripts/check-native-clients.py','--nodes',target,'--address',address],check=True)
   resolved={x[4][0] for x in socket.getaddrinfo(target+'.mokamaker.site',443,type=socket.SOCK_STREAM)}
   assert resolved=={address},'Hostname not yet resolving to expected instance'
   subprocess.run(['python3','scripts/check-native-clients.py','--nodes',target],check=True)
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
   code=pathlib.Path('scripts/validate-native-host.py').read_text()
   print(remote("sudo -n python3 - <<'PY'\n"+code+"\nPY"));clients();return
  def baseline():
   return json.loads(remote("sudo -n python3 - <<'PY'\nimport json,pathlib,subprocess\nx={line.split('=',1)[0]:line.split('=',1)[1] for line in subprocess.check_output(['systemctl','show','xray','-p','MainPID','-p','ExecMainStartTimestampMonotonic','-p','NRestarts'],text=True).splitlines()};x['boot']=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip();print(json.dumps(x))\nPY"))
  if stage in ['baseline','compare']:
   current=baseline()
   if stage=='baseline':print(remote("sudo -n install -d -m 0700 /var/lib/xray-validation; printf '%s' '"+json.dumps(current)+"' | sudo -n tee /var/lib/xray-validation/baseline.json >/dev/null; echo Baseline_saved"))
   else:assert current==json.loads(remote('sudo -n cat /var/lib/xray-validation/baseline.json')),'Unchanged deployment restarted service/host'
   print('Baseline',current);clients();return
  if stage in ['reboot','recovery']:
   before=baseline()
   if stage=='reboot':remote("sudo -n shutdown -r now",False,30)
   else:remote('sudo -n systemctl kill --signal=SIGKILL xray')
   for attempt in range(60):
    time.sleep(3)
    try:
     now=baseline();active=remote('systemctl is-active xray',False)
     if active=='active' and now['MainPID']!='0' and (now['boot']!=before['boot'] if stage=='reboot' else now['MainPID']!=before['MainPID']):break
    except (RuntimeError,subprocess.TimeoutExpired):pass
   else:raise RuntimeError('Service did not recover')
   print('Recovery PASS',stage,before,now);clients();return
  if stage=='logs':
   print(remote("sudo -n systemd-run --wait --unit=xray-journal-probe --property=StandardOutput=journal --property=LogRateLimitIntervalSec=0 /usr/bin/python3 -c 'for i in range(45000): print(\"native-journal-probe \"+\"x\"*1000)'",timeout=150))
   code="""import pathlib,subprocess
files=list(pathlib.Path('/var/log/journal').rglob('*.journal'))
assert len(files)>=2,'Journal did not rotate'
size=sum(x.stat().st_size for x in files)
assert size<=115*1024**2,'Persistent journal exceeded budget and file slack'
print('Journal rotation PASS; files',len(files),'bytes',size)
print(subprocess.check_output(['journalctl','--disk-usage'],text=True))
"""
   print(remote("sudo -n python3 - <<'PY'\n"+code+"\nPY"));clients();return
  raise RuntimeError('Unknown stage')
if __name__=='__main__':main()
