"""Exercise secret permissions with the pinned nonroot official container image.

Docker on the controller is required. Only ephemeral IDs created here are removed.
Generated keys stay in memory; no credentials or published ports are involved.
"""
import io,json,pathlib,subprocess,tarfile
from jinja2 import Environment
image='ghcr.io/xtls/xray-core:25.10.15'
docker=['docker']
subprocess.run(docker+['pull',image],check=True,capture_output=True)
data=json.loads(subprocess.check_output(docker+['image','inspect',image],text=True))[0]
assert data['Config']['User']=='65532'
private=subprocess.check_output(docker+['run','--rm','--network','none',image,'x25519'],text=True)
private=next(line.split(':',1)[1].strip() for line in private.splitlines() if line.startswith(('Private key:','PrivateKey:')))
template=Environment().from_string((pathlib.Path(__file__).resolve().parents[2]/'ansible/templates/config.json.j2').read_text())
config=template.render(xray_deployment_mode='docker',xray_container_port=443,xray_sni='',xray_uuid='00000000-0000-4000-8000-000000000000',xray_short_ids=['deadbeefcafebabe'],xray_reality_private_key=private).encode()
for mode,expected in [(0o600,False),(0o640,True)]:
 container=subprocess.check_output(docker+['create','--network','none',image,'run','-test','-config','/candidate.json'],text=True).strip()
 try:
  tar=io.BytesIO()
  with tarfile.open(fileobj=tar,mode='w') as archive:
   info=tarfile.TarInfo('candidate.json');info.size=len(config);info.uid=0;info.gid=65532;info.mode=mode;archive.addfile(info,io.BytesIO(config))
  subprocess.run(docker+['cp','-',container+':/'],input=tar.getvalue(),check=True,capture_output=True)
  result=subprocess.run(docker+['start','--attach',container],capture_output=True,text=True)
  state=json.loads(subprocess.check_output(docker+['inspect',container],text=True))[0]['State']
  assert (state['ExitCode']==0)==expected,(result.stdout+result.stderr)
  print('Pinned image config mode',oct(mode),'expected acceptance',expected,'PASS')
 finally:subprocess.run(docker+['rm',container],check=True,capture_output=True)
