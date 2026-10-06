#!/usr/bin/env python3
"""Focused Podman acceptance. Mutations are restricted to owner-selected flatwhite."""
import importlib.util
import ipaddress
import json
import os
import pathlib
import shlex
import socket
import subprocess
import tempfile

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('validation',ROOT/'scripts/native-validation.py')
validation=importlib.util.module_from_spec(spec);spec.loader.exec_module(validation)


def sanitized(text):
    for name in ['SSH_PRIVATE_KEY','XRAY_UUID','XRAY_PRIVATE_KEY','XRAY_PUBLIC_KEY','XRAY_SHORT_IDS']:
        value=os.environ.get(name,'')
        if value:
            text=text.replace(value,'[redacted]')
            if name=='XRAY_SHORT_IDS':
                for sid in value.split(','):
                    if sid.strip():text=text.replace(sid.strip(),'[redacted]')
    return text


def main():
    assert os.environ['TARGET']=='flatwhite','Podman acceptance refuses other targets'
    address=os.environ['ADDRESS'];assert str(ipaddress.IPv4Address(address))==address
    hostname='flatwhite.mokamaker.site'
    assert {item[4][0] for item in socket.getaddrinfo(hostname,443,type=socket.SOCK_STREAM)}=={address}
    assert os.environ.get('XRAY_DEPLOYMENT_MODE')=='podman'
    assert os.environ.get('XRAY_CONTAINER_IMAGE_VERSION','26.3.27')=='26.3.27'
    assert address not in {'18.136.58.134','52.74.81.140'},'Refusing recorded serving peer IP'
    resume=os.environ.get('SPARE_RESUME','false')=='true'

    def stage(name,mode='podman',minimal=False):
        print('VALIDATION flatwhite',mode,name,flush=True)
        subprocess.run(['python3','scripts/native-validation.py'],cwd=ROOT,check=True,
                       env={**os.environ,'STAGE':name,'XRAY_DEPLOYMENT_MODE':mode,
                            'XRAY_REQUIRE_MINIMAL_HOST':str(minimal).lower()})

    with tempfile.TemporaryDirectory(prefix='podman-flatwhite-') as tmp:
        directory=pathlib.Path(tmp);key=directory/'key'
        validation.write_private_key(key,os.environ['SSH_PRIVATE_KEY'])
        inventory=directory/'inventory.json'
        inventory.write_text(json.dumps({'all':{'children':{'xray_servers':{'hosts':{
            'flatwhite':{'ansible_host':address,'ansible_user':'ubuntu',
                         'ansible_python_interpreter':'/usr/bin/python3'}}}}}}))
        artifact=json.loads(subprocess.check_output(['python3','scripts/prepare-native.py','--version','26.3.27','--directory',str(directory/'binary'),'--json'],cwd=ROOT,text=True))
        env={**os.environ,'ANSIBLE_PRIVATE_KEY_FILE':str(key),'ANSIBLE_HOST_KEY_CHECKING':'False',
             'XRAY_BINARY_PATH':artifact['path'],'XRAY_BINARY_SHA256':artifact['sha256']}
        ssh=['ssh','-i',str(key),'-o','BatchMode=yes','-o','IdentitiesOnly=yes',
             '-o','ConnectTimeout=10','-o','StrictHostKeyChecking=accept-new',
             '-o','UserKnownHostsFile='+str(directory/'known_hosts'),'ubuntu@'+address]

        def remote(code):
            result=subprocess.run(ssh+['sudo -n python3 -c '+shlex.quote(code)],capture_output=True,text=True,timeout=120)
            if result.returncode:raise RuntimeError('Flatwhite check failed: '+sanitized(result.stderr)[-2000:])
            return result.stdout.strip()

        def probe():
            code=(ROOT/'scripts/runtime-ownership.py').read_text().split("if __name__ == '__main__':")[0]
            return json.loads(remote(code+'\nprint(json.dumps(inspect()))'))

        def deploy(mode,switch=False,overrides=None,rejected=None,tags=None):
            variables={'xray_deployment_mode':mode,'xray_allow_runtime_switch':switch,**(overrides or {})}
            cmd=['ansible-playbook','-i',str(inventory),'ansible/site.yml','--limit','flatwhite','-e',json.dumps(variables)]
            if tags:cmd+=['--tags',tags]
            print('DEPLOY flatwhite',mode,tags or 'reconcile','expected rejection' if rejected else '',flush=True)
            result=subprocess.run(cmd,cwd=ROOT,env=env,capture_output=True,text=True,timeout=1200)
            if rejected:
                assert result.returncode!=0,'Expected rejection did not occur'
                boundary=result.stdout.split('fatal:',1)[0].rsplit('TASK [',1)[-1].split(']',1)[0]
                assert rejected in boundary,'Failure occurred outside intended boundary: '+sanitized(boundary)
                print('Expected rejection PASS:',boundary,flush=True)
            elif result.returncode:
                print(sanitized(result.stdout+result.stderr)[-14000:],flush=True)
                raise RuntimeError('Flatwhite deployment failed')
            else:print('Deployment PASS',flush=True)

        fixtures={}

        def fixture(engine):
            prefix=['podman','--remote=false'] if engine=='podman' else ['docker']
            code='''import subprocess,json
prefix=PREFIX
name='flatwhite-podman-unrelated-'+ENGINE
assert not subprocess.check_output(prefix+['ps','-a','--filter','name=^'+name+'$','-q'],text=True).strip()
identity=subprocess.check_output(prefix+['create','--name',name,'--label','less-vision-reality.fixture=flatwhite-podman','--network','none','ghcr.io/xtls/xray-core:26.3.27','version'],text=True).strip()
print(identity)
'''.replace('PREFIX',repr(prefix)).replace('ENGINE',repr(engine))
            fixtures[engine]=remote(code)

        def verify_fixtures(remove=False):
            for engine,identity in fixtures.items():
                prefix=['podman','--remote=false'] if engine=='podman' else ['docker']
                code='''import subprocess,json
prefix=PREFIX;identity=IDENTITY
d=json.loads(subprocess.check_output(prefix+['inspect',identity],text=True))[0]
assert d['Id']==identity and d['Config']['Labels']['less-vision-reality.fixture']=='flatwhite-podman'
'''.replace('PREFIX',repr(prefix)).replace('IDENTITY',repr(identity))
                if remove:code+='subprocess.run(prefix+["rm",identity],check=True)\n'
                remote(code)
            print('Unrelated owned fixtures', 'cleaned' if remove else 'preserved','PASS',flush=True)

        def negatives(mode='podman'):
            stage('baseline',mode)
            deploy(mode)
            stage('compare',mode)
            deploy('invalid',rejected='Reject unsupported runtime')
            stage('compare',mode)
            deploy(mode,overrides={'xray_reality_private_key':'INVALID_CANDIDATE_KEY'},rejected='Validate Podman candidate')
            stage('compare',mode)

        try:
            stage('ready')
            deploy('podman',switch=resume)
            stage('inspect',minimal=not resume)
            fixture('podman')
            negatives()
            original=probe()['podman_id']
            short_ids=[value.strip() for value in os.environ['XRAY_SHORT_IDS'].split(',') if value.strip()]
            extra='cafebabedeadbeef';assert extra not in short_ids
            deploy('podman',overrides={'xray_short_ids':short_ids+[extra]})
            assert probe()['podman_id']!=original,'Changed configuration did not recreate Podman container'
            stage('clients')
            deploy('podman');stage('inspect')
            original=probe()['podman_id']
            deploy('podman',tags='xray_down')
            stopped=probe();assert not stopped['podman_running'] and not stopped['podman_service_active']
            deploy('podman');assert probe()['podman_id']==original
            deploy('podman',tags='xray_reload');assert probe()['podman_id']==original
            deploy('podman',tags='xray_recreate');assert probe()['podman_id']!=original
            stage('recovery')
            stage('logs')
            # Cover only transitions involving the new runtime. Existing native /
            # Docker lifecycle suites are deliberately not repeated.
            for opposite in ['native','docker']:
                stage('baseline')
                deploy(opposite,rejected='Require explicit opt-in')
                stage('compare')
                deploy(opposite,switch=True)
                if opposite=='docker':fixture('docker')
                stage('inspect',opposite);verify_fixtures()
                stage('baseline',opposite)
                deploy('podman',rejected='Require explicit opt-in')
                stage('compare',opposite)
                deploy('podman',switch=True)
                stage('inspect');verify_fixtures()
            stage('reboot')
            stage('inspect');verify_fixtures()
            print('PODMAN FLATWHITE ACCEPTANCE PASS',flush=True)
        finally:
            verify_fixtures(remove=True)


if __name__=='__main__':main()
