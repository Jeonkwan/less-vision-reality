"""Validate reviewed images and restricted configuration with actual rootful Podman.

Controller CI uses sudo; this removes only ephemeral IDs created by this test.
Generated keys remain in memory. No network or service ports are published.
"""
import io
import json
import os
import pathlib
import subprocess
import tarfile

from jinja2 import Environment

image='ghcr.io/xtls/xray-core:'+os.environ.get('XRAY_CONTAINER_IMAGE_VERSION','26.3.27')
podman=['sudo','-n','podman','--remote=false']
subprocess.run(podman+['pull',image],check=True,capture_output=True)
data=json.loads(subprocess.check_output(podman+['image','inspect',image],text=True))[0]
assert data['Config']['User']=='65532'
assert data['Config']['Entrypoint']==['/usr/local/bin/xray']
flags=['--network=none','--user=65532:65532','--security-opt=no-new-privileges','--cap-drop=all']
reported=subprocess.check_output(podman+['run','--rm']+flags+[image,'version'],text=True)
assert reported.splitlines()[0].startswith('Xray '+image.rsplit(':',1)[1]+' ')
private=subprocess.check_output(podman+['run','--rm']+flags+[image,'x25519'],text=True)
private=next(line.split(':',1)[1].strip() for line in private.splitlines() if line.startswith(('Private key:','PrivateKey:')))
template=Environment().from_string((pathlib.Path(__file__).resolve().parents[2]/'ansible/templates/config.json.j2').read_text())
config=template.render(xray_deployment_mode='podman',xray_container_port=443,xray_sni='',xray_uuid='00000000-0000-4000-8000-000000000000',xray_short_ids=['deadbeefcafebabe'],xray_reality_private_key=private).encode()
for mode,expected in [(0o600,False),(0o640,True)]:
    container=subprocess.check_output(podman+['create']+flags+[image,'run','-test','-config','/candidate.json'],text=True).strip()
    try:
        buffer=io.BytesIO()
        with tarfile.open(fileobj=buffer,mode='w') as archive:
            info=tarfile.TarInfo('candidate.json');info.size=len(config);info.uid=0;info.gid=65532;info.mode=mode
            archive.addfile(info,io.BytesIO(config))
        subprocess.run(podman+['cp','-',container+':/'],input=buffer.getvalue(),check=True,capture_output=True)
        subprocess.run(podman+['start','--attach',container],capture_output=True,text=True)
        state=json.loads(subprocess.check_output(podman+['inspect',container],text=True))[0]['State']
        assert (state['ExitCode']==0)==expected,'Pinned Podman image configuration permissions differ'
        print('Podman',image,'configuration',oct(mode),'expected acceptance',expected,'PASS')
    finally:
        subprocess.run(podman+['rm',container],check=True,capture_output=True)
