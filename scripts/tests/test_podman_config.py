"""Validate reviewed images and restricted configuration with actual rootful Podman.

Controller CI uses sudo; this removes only ephemeral IDs created by this test.
Generated test keys are held only in a private temporary file. No network or service ports are published.
"""
import json
import os
import pathlib
import subprocess
import tempfile

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
with tempfile.TemporaryDirectory(prefix='podman-permissions-') as directory:
    candidate=pathlib.Path(directory)/'candidate.json'
    candidate.write_bytes(config);candidate.chmod(0o600)
    subprocess.run(['sudo','-n','chown','0:65532',str(candidate)],check=True)
    for mode,expected in [(0o600,False),(0o640,True)]:
        subprocess.run(['sudo','-n','chmod',oct(mode)[2:],str(candidate)],check=True)
        result=subprocess.run(podman+['run','--rm']+flags+['--mount',
            'type=bind,src='+str(candidate)+',dst=/candidate.json,readonly',
            image,'run','-test','-config','/candidate.json'],capture_output=True,text=True)
        assert (result.returncode==0)==expected,'Pinned Podman image configuration permissions differ at '+oct(mode)
        print('Podman',image,'configuration',oct(mode),'expected acceptance',expected,'PASS')
