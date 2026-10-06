"""Validate reviewed images and restricted configuration with actual rootful Podman.

Controller CI uses sudo; this removes only ephemeral IDs created by this test.
Generated test keys are held only in a private temporary file. No network or service ports are published.
"""
import json
import os
import pathlib
import subprocess
import tempfile
import time

from jinja2 import Environment

image='ghcr.io/xtls/xray-core:'+os.environ.get('XRAY_CONTAINER_IMAGE_VERSION','26.3.27')
podman=['sudo','-n','podman','--remote=false']
subprocess.run(podman+['pull',image],check=True,capture_output=True)
data=json.loads(subprocess.check_output(podman+['image','inspect',image],text=True))[0]
assert data['Config']['User']=='65532'
assert data['Config']['Entrypoint']==['/usr/local/bin/xray']
flags=['--network=none','--user=65532:65532','--cap-drop=all']
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
    # Configuration parsing does not prove that the unprivileged process can
    # create its real TCP listener under the selected confinement policy.
    mount='type=bind,src='+str(candidate)+',dst=/candidate.json,readonly'
    container=subprocess.check_output(podman+['create']+flags+[
        '--sysctl=net.ipv4.ip_unprivileged_port_start=0','--mount',mount,
        image,'run','-config','/candidate.json'],text=True).strip()
    try:
        subprocess.run(podman+['start',container],check=True,capture_output=True)
        for sample in range(2):
            time.sleep(2)
            state=json.loads(subprocess.check_output(podman+['inspect',container],text=True))[0]['State']
            if not state['Running']:
                logs=subprocess.check_output(podman+['logs',container],text=True,stderr=subprocess.STDOUT)
                safe=logs.replace(private,'[generated key redacted]')
                raise AssertionError('Podman real listener failed: '+safe[-2000:])
        print('Podman',image,'unprivileged real TCP listener PASS')
    finally:
        subprocess.run(podman+['stop',container],capture_output=True)
        subprocess.run(podman+['rm',container],check=True,capture_output=True)
