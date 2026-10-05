#!/usr/bin/env python3
"""Validate only owner-selected disposable Americano/Latte hosts using Actions secrets."""
import ipaddress
import json
import os
import pathlib
import shlex
import socket
import subprocess
import tempfile

from importlib.util import spec_from_file_location, module_from_spec

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = spec_from_file_location('validation', ROOT / 'scripts/native-validation.py')
validation = module_from_spec(spec)
spec.loader.exec_module(validation)
SPARES = {'americano', 'latte'}


def sanitized(text):
    for name in ['SSH_PRIVATE_KEY', 'XRAY_UUID', 'XRAY_PRIVATE_KEY', 'XRAY_PUBLIC_KEY', 'XRAY_SHORT_IDS']:
        value = os.environ.get(name, '')
        if value:
            text = text.replace(value, '[redacted]')
            if name == 'XRAY_SHORT_IDS':
                for sid in value.split(','):
                    if sid.strip(): text = text.replace(sid.strip(), '[redacted]')
    return text


def main():
    target = os.environ['TARGET']
    address = os.environ['ADDRESS']
    initial = os.environ.get('XRAY_DEPLOYMENT_MODE', 'native')
    hostname = os.environ.get('VALIDATION_HOSTNAME') or target+'.mokamaker.site'
    assert target in SPARES, 'Spare harness refuses serving/unknown targets'
    assert initial in ['native', 'docker']
    assert str(ipaddress.IPv4Address(address)) == address
    assert hostname in [target+'.mokamaker.site', target+'.'+address+'.sslip.io']
    assert {item[4][0] for item in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)} == {address}
    resume = os.environ.get('SPARE_RESUME', 'false') == 'true'
    opposite = 'docker' if initial == 'native' else 'native'

    def stage(name, mode, minimal=False):
        print('VALIDATION', target, mode, name, flush=True)
        subprocess.run(['python3', 'scripts/native-validation.py'], cwd=ROOT,
                       env={**os.environ, 'STAGE': name, 'XRAY_DEPLOYMENT_MODE': mode,
                            'XRAY_REQUIRE_MINIMAL_HOST': str(minimal).lower()}, check=True)

    def peers():
        print('Read-only serving peer transport checks', flush=True)
        subprocess.run(['python3', 'scripts/check-native-clients.py', '--nodes', 'flatwhite', 'decaf'],
                       cwd=ROOT, check=True)

    with tempfile.TemporaryDirectory(prefix='selectable-spare-') as tmp:
        directory = pathlib.Path(tmp)
        key = directory / 'key'
        validation.write_private_key(key, os.environ['SSH_PRIVATE_KEY'])
        inventory = directory / 'inventory.yml'
        inventory.write_text(json.dumps({'all': {'children': {'xray_servers': {'hosts': {
            'spare': {'ansible_host': address, 'ansible_user': 'ubuntu',
                      'ansible_python_interpreter': '/usr/bin/python3'}}}}}}))
        artifact = json.loads(subprocess.check_output([
            'python3', str(ROOT/'scripts/prepare-native.py'), '--version', '26.3.27',
            '--directory', str(directory/'binary'), '--json'], text=True))
        deployment_env = {**os.environ, 'ANSIBLE_PRIVATE_KEY_FILE': str(key),
                          'ANSIBLE_HOST_KEY_CHECKING': 'False',
                          'XRAY_BINARY_PATH': artifact['path'], 'XRAY_BINARY_SHA256': artifact['sha256']}
        ssh = ['ssh', '-i', str(key), '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes',
               '-o', 'ConnectTimeout=10', '-o', 'StrictHostKeyChecking=accept-new',
               '-o', 'UserKnownHostsFile='+str(directory/'known_hosts'), 'ubuntu@'+address]

        def remote(code):
            result = subprocess.run(ssh+['sudo -n python3 -c '+shlex.quote(code)],
                                    capture_output=True, text=True, timeout=120)
            if result.returncode:
                raise RuntimeError('Spare fixture operation failed: '+sanitized(result.stderr))
            return result.stdout.strip()

        def deploy(mode, switch=False, overrides=None, rejected=False):
            variables = {'xray_deployment_mode': mode, 'xray_allow_runtime_switch': switch,
                         **(overrides or {})}
            print('DEPLOY', target, mode, 'expected rejection' if rejected else 'reconcile', flush=True)
            result = subprocess.run(['ansible-playbook', '-i', str(inventory), 'ansible/site.yml',
                                     '-e', json.dumps(variables)], cwd=ROOT, env=deployment_env,
                                    capture_output=True, text=True, timeout=1200)
            if (result.returncode != 0) != rejected:
                print(sanitized(result.stdout+result.stderr)[-12000:], flush=True)
                raise RuntimeError('Unexpected deployment result')
            if rejected:
                task = result.stdout.split('fatal:',1)[0].rsplit('TASK [',1)[-1].split(']',1)[0]
                if mode == 'invalid': expected = 'Reject unsupported runtime before any host operation'
                elif overrides: expected = 'Stage and validate configuration' if mode=='native' else 'Validate Docker candidate'
                else: expected = 'Require explicit opt-in before switching'
                assert expected in task, 'Deployment failed outside the intended rejection boundary'
                print('Expected rejection boundary PASS:', task, flush=True)
            print('Deployment result PASS', flush=True)

        fixture = None

        def create_fixture():
            nonlocal fixture
            if fixture: return
            code = """import subprocess,json,pathlib
run=lambda *args:subprocess.check_output(args,text=True).strip()
name='xray-unrelated-validation'
assert not run('docker','ps','-a','--filter','name=^/'+name+'$','-q')
assert not run('docker','network','ls','--filter','name=^'+name+'$','-q')
p=pathlib.Path('/opt/xray-unrelated-validation');assert not p.exists()
p.mkdir(mode=0o700);(p/'config.json').write_text('{}')
network=run('docker','network','create','--label','less-vision-reality.fixture=true',name)
container=run('docker','create','--name',name,'--label','less-vision-reality.fixture=true','--network',network,'ghcr.io/xtls/xray-core:26.3.27','version')
print(json.dumps(dict(container=container,network=network)))
"""
            fixture = json.loads(remote(code))

        def verify_fixture():
            if not fixture: return
            code = "import json,pathlib,subprocess\nx="+repr(fixture)+"\nfor kind in ['container','network']:\n d=json.loads(subprocess.check_output(['docker',kind,'inspect',x[kind]],text=True))[0]\n assert d['Id']==x[kind]\nassert pathlib.Path('/opt/xray-unrelated-validation/config.json').read_text()=='{}'\nprint('Unrelated container/network/config preserved PASS')"
            print(remote(code), flush=True)

        def negative_and_repeat(mode):
            stage('baseline', mode)
            deploy(mode)
            stage('compare', mode)
            deploy('invalid', rejected=True)
            stage('compare', mode)
            deploy(mode, overrides={'xray_reality_private_key': 'INVALID_CANDIDATE_KEY'}, rejected=True)
            stage('compare', mode)

        try:
            peers()
            stage('ready', initial)
            deploy(initial, switch=resume)
            stage('inspect', initial, minimal=initial=='native' and not resume)
            negative_and_repeat(initial)
            stage('suite', initial)
            if initial == 'docker': create_fixture()
            deploy(opposite, rejected=True)
            stage('compare', initial)
            deploy(opposite, switch=True)
            if opposite == 'docker': create_fixture()
            verify_fixture()
            peers()
            stage('inspect', opposite)
            negative_and_repeat(opposite)
            stage('suite', opposite)
            verify_fixture()
            deploy(initial, switch=True)
            stage('inspect', initial)
            verify_fixture()
            stage('baseline', initial)
            deploy(initial)
            stage('compare', initial)
            stage('reboot', initial)
            stage('inspect', initial)
            verify_fixture()
            peers()
            print('SPARE ACCEPTANCE PASS', target, initial, '->', opposite, '->', initial, flush=True)
        finally:
            if fixture:
                code="import json,pathlib,subprocess\nx="+repr(fixture)+"\nfor kind in ['container','network']:\n d=json.loads(subprocess.check_output(['docker',kind,'inspect',x[kind]],text=True))[0]\n labels=d['Config']['Labels'] if kind=='container' else d['Labels']\n assert labels.get('less-vision-reality.fixture')=='true'\n subprocess.run(['docker',kind,'rm',x[kind]],check=True)\np=pathlib.Path('/opt/xray-unrelated-validation');assert (p/'config.json').read_text()=='{}';(p/'config.json').unlink();p.rmdir()\nprint('Owned test fixtures cleaned')"
                print(remote(code), flush=True)


if __name__ == '__main__': main()
