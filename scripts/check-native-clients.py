#!/usr/bin/env python3
"""Test supplied Clash/sing-box transport profiles; credentials remain in env."""
import argparse,copy,hashlib,json,os,pathlib,socket,subprocess,tempfile,time

def port():
 with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--nodes',nargs='+',choices=['cream','flatwhite','decaf','americano','latte'],required=True);p.add_argument('--address');a=p.parse_args()
 profiles=json.loads(pathlib.Path(__file__).with_name('client-profiles.json').read_text())
 values={'uuid':os.environ['XRAY_UUID'],'public_key':os.environ['XRAY_PUBLIC_KEY'],'short_id':os.environ['XRAY_SHORT_IDS'].split(',')[0].strip()}
 for name in a.nodes:
  profile=profiles[name]
  assert all(hashlib.sha256(values[k].encode()).hexdigest()==v for k,v in profile['credential_fingerprints'].items()),'Environment credentials do not match supplied clients'
  for core in ['singbox','clash']:
   outbound=copy.deepcopy(profile[core]);host=a.address or outbound.get('server');outbound['server']=host;outbound['uuid']=values['uuid']
   if core=='singbox':
    outbound['tls']['reality'].update(public_key=values['public_key'],short_id=values['short_id'])
   else:outbound['reality-opts'].update({'public-key':values['public_key'],'short-id':values['short_id']})
   with tempfile.TemporaryDirectory(prefix='native-client-') as tmp:
    root=pathlib.Path(tmp);local=port()
    if core=='singbox':
     config={'log':{'level':'error'},'inbounds':[{'type':'socks','listen':'127.0.0.1','listen_port':local}],'outbounds':[outbound],'route':{'final':name}};binary='sing-box';cmd=[binary,'run','-c',str(root/'config.json')];test=[binary,'check','-c',str(root/'config.json')]
    else:
     config={'socks-port':local,'allow-lan':False,'mode':'global','log-level':'error','proxies':[outbound],'proxy-groups':[{'name':'GLOBAL','type':'select','proxies':[name]}],'rules':['MATCH,GLOBAL']};binary='mihomo';cmd=[binary,'-d',str(root),'-f',str(root/'config.json')];test=[binary,'-t','-d',str(root),'-f',str(root/'config.json')]
    path=root/'config.json';path.write_text(json.dumps(config));path.chmod(0o600)
    r=subprocess.run(test,capture_output=True,timeout=20);assert r.returncode==0,f'{core} profile validation failed'
    process=subprocess.Popen(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
     ready=False
     for _ in range(100):
      if process.poll() is not None:break
      try:
       with socket.create_connection(('127.0.0.1',local),timeout=.1):ready=True;break
      except OSError:time.sleep(.1)
     assert ready,f'{core} client failed to start'
     for attempt in range(2):
      for url in ['https://www.cloudflare.com/cdn-cgi/trace','https://www.gstatic.com/generate_204']:
       r=subprocess.run(['curl','--silent','--show-error','--fail','--max-time','20','--noproxy','','--proxy',f'socks5h://127.0.0.1:{local}','--output','/dev/null','--write-out','%{http_code}',url],capture_output=True,text=True,timeout=25)
       print(name,core,host,url,'PASS' if r.returncode==0 else 'FAIL','HTTP',r.stdout,flush=True)
       if r.returncode:
        detail=r.stderr.strip()
        for secret in values.values():detail=detail.replace(secret,'[redacted]')
        print('Client request failure: curl exit',r.returncode,detail[:500],flush=True)
       assert r.returncode==0,'Authenticated HTTPS traffic failed'
    finally:
     process.terminate()
     try:process.wait(timeout=5)
     except subprocess.TimeoutExpired:process.kill();process.wait()
if __name__=='__main__':main()
