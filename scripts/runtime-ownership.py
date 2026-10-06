#!/usr/bin/env python3
"""Runtime ownership checks and narrowly scoped Podman supervisor actions."""
import json
import argparse
import configparser
import ipaddress
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import time


PODMAN = ['podman', '--remote=false']
PODMAN_ROOT = '/opt/xray-podman'
PODMAN_MARKER = 'less-vision-reality podman-runtime v1\n'
PODMAN_LABELS = {'io.github.jeonkwan.less-vision-reality.runtime': 'podman',
                 'io.github.jeonkwan.less-vision-reality.root': PODMAN_ROOT}
FORWARDING_FILE = 'opt/xray-podman/forwarding.json'


def validate_forwarding_record(record):
    if (not isinstance(record, dict) or set(record) != {'id', 'ip'} or
            not isinstance(record['id'], str) or not re.fullmatch('[0-9a-f]{64}', record['id']) or
            not isinstance(record['ip'], str)):
        raise RuntimeError('Refusing unmanaged Podman forwarding identity')
    address = ipaddress.IPv4Address(record['ip'])
    if not any(address in ipaddress.IPv4Network(subnet) for subnet in ['10.0.0.0/8','172.16.0.0/12','192.168.0.0/16']):
        raise RuntimeError('Refusing unexpected Podman bridge address')
    return record


def forwarding_record(root=pathlib.Path('/')):
    path = root / FORWARDING_FILE
    if path.is_symlink():
        raise RuntimeError('Refusing symlinked Podman forwarding record')
    if not path.exists():
        return None
    if path.stat().st_uid != os.geteuid() or path.stat().st_mode & 0o777 != 0o600:
        raise RuntimeError('Refusing unmanaged Podman forwarding record')
    return validate_forwarding_record(json.loads(path.read_text()))


def forwarding_rule(record):
    validate_forwarding_record(record)
    return ['-d', record['ip']+'/32', '-p', 'tcp', '--dport', '443',
            '-m', 'conntrack', '--ctstate', 'DNAT', '--ctorigdstport', '443', '-m', 'comment', '--comment',
            'less-vision-reality:xray-podman:'+record['id'], '-j', 'ACCEPT']


def clear_forwarding(root=pathlib.Path('/'), call=subprocess.run):
    record = forwarding_record(root)
    if record is None:
        return
    prefix = ['iptables', '-w', '5', '-t', 'filter']
    rule = forwarding_rule(record)
    found = call(prefix+['-C', 'FORWARD']+rule, capture_output=True, text=True)
    if found.returncode == 0:
        call(prefix+['-D', 'FORWARD']+rule, capture_output=True, text=True, check=True)
    elif found.returncode != 1:
        raise RuntimeError('Podman forwarding inspection failed')
    (root / FORWARDING_FILE).unlink()


def inspect_podman(root=pathlib.Path('/'), call=subprocess.run, podman=None, supervising=False):
    unit = root / 'etc/systemd/system/xray-podman.service'
    deployment = root / 'opt/xray-podman'
    marker = deployment / '.managed-by-less-vision-reality'
    for path in [unit, deployment, marker, deployment / 'config', deployment / 'config/config.json']:
        if path.is_symlink():
            raise RuntimeError('Refusing symlinked Podman deployment')
    if deployment.exists() and (not marker.exists() or marker.read_text() != PODMAN_MARKER):
        raise RuntimeError('Refusing unmarked Podman deployment directory')
    forwarding_record(root)
    if unit.exists():
        required = ['Description=Xray VLESS REALITY proxy (managed Podman)', 'Type=simple',
                    'ExecStart=/usr/bin/python3 /opt/xray-podman/runtime-ownership.py --podman-action start',
                    'ExecStop=/usr/bin/python3 /opt/xray-podman/runtime-ownership.py --podman-action stop',
                    'Restart=always', 'WantedBy=multi-user.target']
        if not marker.exists() or not all(line in unit.read_text().splitlines() for line in required):
            raise RuntimeError('Refusing unmanaged xray-podman.service')
        definition = configparser.ConfigParser(interpolation=None)
        definition.optionxform = str
        try:
            definition.read_string(unit.read_text())
        except configparser.Error as error:
            raise RuntimeError('Refusing ambiguous Podman service definition') from error
        allowed = {'Type', 'ExecStart', 'ExecStop', 'Restart', 'RestartSec',
                   'TimeoutStopSec', 'KillMode', 'StandardOutput', 'StandardError', 'SyslogIdentifier'}
        extended = allowed | {'ExecStartPost', 'ExecStopPost'}
        if set(definition['Service']) not in [allowed, extended]:
            raise RuntimeError('Refusing unmanaged Podman service directives')
        if set(definition['Service']) == extended:
            for directive, action in [('ExecStartPost', 'allow-forwarding'), ('ExecStopPost', 'clear-forwarding')]:
                if definition['Service'][directive] != '/usr/bin/python3 /opt/xray-podman/runtime-ownership.py --podman-action '+action:
                    raise RuntimeError('Refusing unmanaged Podman forwarding supervisor')
        if any(list((root / path).glob('*.conf')) for path in [
                'etc/systemd/system/xray-podman.service.d',
                'run/systemd/system/xray-podman.service.d',
                'usr/lib/systemd/system/xray-podman.service.d']):
            raise RuntimeError('Refusing unmanaged Podman service overrides')
    else:
        result = call(['systemctl', 'show', 'xray-podman', '-p', 'LoadState', '--value'],
                      capture_output=True, text=True, check=False)
        if result.stdout.strip() != 'not-found':
            raise RuntimeError('Refusing Podman unit outside managed path')
    state = dict(podman_unit_exists=unit.exists(), podman_exists=False, podman_running=False,
                 podman_enabled=False, podman_id='', podman_image='', podman_image_ref='', podman_spec='', podman_ports=[])
    has_podman = podman if podman is not None else bool(shutil.which('podman'))
    if has_podman:
        info = json.loads(call(PODMAN + ['info', '--format', 'json'], capture_output=True,
                               text=True, check=True).stdout)
        if info['host']['security']['rootless']:
            raise RuntimeError('Refusing rootless Podman inspection')
        result = call(PODMAN + ['container', 'ls', '-a', '--filter', 'name=^xray-podman$',
                               '--format', '{{.ID}}'], capture_output=True, text=True, check=True)
        if result.stdout.strip():
            if len(result.stdout.split()) != 1:
                raise RuntimeError('Ambiguous Podman container identity')
            data = json.loads(call(PODMAN + ['inspect', result.stdout.strip()],
                                   capture_output=True, text=True, check=True).stdout)[0]
            labels = data['Config'].get('Labels') or {}
            if not unit.exists() or not all(labels.get(k) == v for k, v in PODMAN_LABELS.items()):
                raise RuntimeError('Refusing unmanaged Podman container')
            if data['Config']['Image'] not in ['ghcr.io/xtls/xray-core:25.10.15', 'ghcr.io/xtls/xray-core:26.3.27'] or data['Config']['User'] != '65532:65532':
                raise RuntimeError('Refusing unreviewed Podman image or user')
            if not any(m.get('Source') == PODMAN_ROOT + '/config' and
                       m.get('Destination') == '/usr/local/etc/xray' and m.get('RW') is False
                       for m in data.get('Mounts', [])):
                raise RuntimeError('Refusing unrelated Podman configuration')
            if data['HostConfig'].get('Privileged') or data['HostConfig'].get('NetworkMode') != 'bridge':
                raise RuntimeError('Refusing privileged or unexpected Podman networking')
            if not data.get('AppArmorProfile','').startswith('containers-default-'):
                raise RuntimeError('Refusing missing default Podman AppArmor confinement')
            bindings = data.get('HostConfig', {}).get('PortBindings') or {}
            ports = [int(b['HostPort']) for values in bindings.values() for b in (values or [])]
            if set(bindings) != {'443/tcp'} or ports != [443]:
                raise RuntimeError('Refusing unexpected Podman port mappings')
            if data['HostConfig']['LogConfig']['Type'] != 'journald' or data['HostConfig']['RestartPolicy']['Name'] not in ['', 'no']:
                raise RuntimeError('Refusing unexpected Podman supervision or logging')
            state.update(podman_exists=True, podman_running=data['State']['Running'],
                         podman_id=data['Id'], podman_image=data['Image'], podman_image_ref=data['Config']['Image'],
                         podman_spec=labels.get('io.github.jeonkwan.less-vision-reality.spec','v1'), podman_ports=ports)
    elif unit.exists():
        raise RuntimeError('Managed Podman unit exists but Podman is unavailable')
    active = call(['systemctl', 'is-active', 'xray-podman'], capture_output=True, text=True).stdout.strip() == 'active'
    enabled = call(['systemctl', 'is-enabled', 'xray-podman'], capture_output=True, text=True).stdout.strip() == 'enabled'
    if (active or enabled) and not unit.exists():
        raise RuntimeError('Refusing unmanaged active Podman service')
    if state['podman_running'] and not active and not supervising:
        raise RuntimeError('Managed Podman container is running outside its supervisor')
    state['podman_enabled'] = enabled
    state['podman_service_active'] = active
    return state


def allow_forwarding(root=pathlib.Path('/'), call=subprocess.run, probe=inspect_podman, pause=time.sleep):
    # An explicit DNAT-only allowance makes this published port independent of
    # Docker's FORWARD default policy. Never change a global policy or flush rules.
    for attempt in range(40):
        state = probe(root, call, supervising=True)
        if state['podman_running']:
            break
        pause(0.25)
    else:
        raise RuntimeError('Owned Podman container did not start for forwarding')
    data = json.loads(call(PODMAN+['inspect', state['podman_id']], capture_output=True,
                           text=True, check=True).stdout)[0]
    addresses = [network['IPAddress'] for network in data['NetworkSettings']['Networks'].values()
                 if network.get('IPAddress')]
    if len(addresses) != 1:
        raise RuntimeError('Refusing ambiguous Podman bridge addresses')
    record = validate_forwarding_record({'id': state['podman_id'], 'ip': str(ipaddress.IPv4Address(addresses[0]))})
    old = forwarding_record(root)
    if old is not None and old != record:
        clear_forwarding(root, call)
    path = root / FORWARDING_FILE
    with tempfile.NamedTemporaryFile(mode='w', prefix='.forwarding-', dir=path.parent, delete=False) as temporary:
        json.dump(record, temporary)
    try:
        os.replace(temporary.name, path)
    finally:
        pathlib.Path(temporary.name).unlink(missing_ok=True)
    forwarding_record(root)  # Validate canonical ownership before issuing rules.
    prefix = ['iptables', '-w', '5', '-t', 'filter']
    rule = forwarding_rule(record)
    found = call(prefix+['-C', 'FORWARD']+rule, capture_output=True, text=True)
    if found.returncode == 1:
        call(prefix+['-I', 'FORWARD', '1']+rule, capture_output=True, text=True, check=True)
    elif found.returncode != 0:
        raise RuntimeError('Podman forwarding inspection failed')


def inspect(root=pathlib.Path('/'), call=subprocess.run, docker=None, podman=None):
    unit = root / 'etc/systemd/system/xray.service'
    native = unit.exists()
    if native:
        text = unit.read_text()
        required = ['Description=Xray VLESS REALITY proxy', 'User=xray', 'Group=xray',
                    'ExecStart=/usr/local/bin/xray run -config /usr/local/etc/xray/config.json']
        if not all(line in text.splitlines() for line in required):
            raise RuntimeError('Refusing unmanaged xray.service')
    else:
        result = call(['systemctl', 'show', 'xray', '-p', 'LoadState', '--value'],
                      capture_output=True, text=True, check=False)
        if result.stdout.strip() != 'not-found':
            raise RuntimeError('Refusing Xray unit outside managed path')
    exists = False
    running = False
    container_id = ''
    docker_ports = []
    native_port = None
    config = root / 'usr/local/etc/xray/config.json'
    if native and config.exists():
        native_port = json.loads(config.read_text())['inbounds'][0]['port']
    has_docker = docker if docker is not None else bool(shutil.which('docker'))
    if has_docker:
        # A daemon error must not be mistaken for absence of a container.
        call(['docker', 'info'], capture_output=True, text=True, check=True)
        result = call(['docker', 'container', 'ls', '-a', '--filter', 'name=^/xray$',
                       '--format', '{{.ID}}'], capture_output=True, text=True, check=True)
        if result.stdout.strip():
            data = json.loads(call(['docker', 'inspect', 'xray'], capture_output=True,
                                   text=True, check=True).stdout)[0]
            labels = data['Config'].get('Labels') or {}
            expected = {'com.docker.compose.project': 'xray',
                        'com.docker.compose.service': 'xray',
                        'com.docker.compose.project.working_dir': '/opt/xray'}
            if not all(labels.get(k) == v for k, v in expected.items()):
                raise RuntimeError('Refusing unmanaged container named xray')
            if labels.get('com.docker.compose.project.config_files') != '/opt/xray/docker-compose.yml':
                raise RuntimeError('Refusing container from another Compose definition')
            mounts = data.get('Mounts', [])
            if not any(m.get('Source') == '/opt/xray/config' and
                       m.get('Destination') == '/usr/local/etc/xray' for m in mounts):
                raise RuntimeError('Refusing container with unrelated configuration')
            exists, running, container_id = True, data['State']['Running'], data['Id']
            docker_ports = [int(binding['HostPort']) for bindings in
                            data.get('HostConfig', {}).get('PortBindings', {}).values()
                            for binding in (bindings or [])]
    # Existing configuration must belong to this deployment, even when stopped
    # containers have been removed. Never overwrite an arbitrary /opt/xray tree.
    compose = root / 'opt/xray/docker-compose.yml'
    marker = root / 'opt/xray/.managed-by-less-vision-reality'
    deployment = root / 'opt/xray'
    if deployment.exists() and not exists:
        if not marker.exists():
            if not compose.exists():
                raise RuntimeError('Refusing unmarked Docker deployment directory')
            definition = json.loads(call(['docker', 'compose', '-f', str(compose),
                                          'config', '--format', 'json'],
                                         capture_output=True, text=True, check=True).stdout)
            service = definition.get('services', {}).get('xray', {})
            volumes = service.get('volumes', [])
            if (set(definition.get('services', {})) != {'xray'} or
                    service.get('container_name') != 'xray' or
                    service.get('image') not in ['ghcr.io/xtls/xray-core:25.10.15', 'ghcr.io/xtls/xray-core:26.3.27'] or
                    not any(v.get('source') == '/opt/xray/config' and
                            v.get('target') == '/usr/local/etc/xray' for v in volumes)):
                raise RuntimeError('Refusing unrelated Docker configuration')
    if not native and any((root / p).exists() for p in
                          ['usr/local/bin/xray', 'usr/local/etc/xray/config.json']):
        raise RuntimeError('Refusing native artifacts without a managed unit')
    active = call(['systemctl', 'is-active', 'xray'], capture_output=True, text=True).stdout.strip() == 'active'
    enabled = call(['systemctl', 'is-enabled', 'xray'], capture_output=True, text=True).stdout.strip() == 'enabled'
    state = dict(native_exists=native, native_running=active, native_enabled=enabled,
                docker_exists=exists, docker_running=running, docker_id=container_id,
                native_port=native_port, docker_ports=docker_ports)
    state.update(inspect_podman(root, call, podman))
    if sum([active, running, state['podman_running']]) > 1:
        raise RuntimeError('Multiple managed runtimes are active; refusing ambiguous switch')
    # NAT-only published ports may have no userspace socket. Inspect engine port
    # bindings as well, so a bind probe cannot overlook an unrelated container.
    foreign_ports = []
    for engine, available, owned in [( ['docker'], has_docker, container_id),
                                      (PODMAN, podman if podman is not None else bool(shutil.which('podman')), state['podman_id'])]:
        if not available:
            continue
        ids = call(engine + ['ps', '-q'], capture_output=True, text=True, check=True).stdout.split()
        ids = [identity for identity in ids if not owned or not owned.startswith(identity)]
        if ids:
            containers = json.loads(call(engine + ['inspect'] + ids, capture_output=True,
                                         text=True, check=True).stdout)
            for container in containers:
                bindings = container.get('HostConfig', {}).get('PortBindings') or {}
                foreign_ports.extend(int(b['HostPort']) for values in bindings.values() for b in (values or []))
    state['foreign_ports'] = sorted(set(foreign_ports))
    return state


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--podman-action', choices=['start', 'stop', 'allow-forwarding', 'clear-forwarding'])
    parser.add_argument('--require-podman-running', action='store_true')
    args = parser.parse_args()
    if args.podman_action:
        state = inspect_podman(supervising=True)
        if args.podman_action == 'allow-forwarding':
            allow_forwarding()
            raise SystemExit(0)
        if args.podman_action == 'clear-forwarding':
            clear_forwarding()
            raise SystemExit(0)
        if not state['podman_exists']:
            raise RuntimeError('Verified Podman container is missing')
        if args.podman_action == 'stop':
            clear_forwarding()
        command = ['start', '--attach'] if args.podman_action == 'start' else ['stop', '--time', '10']
        os.execvp('podman', PODMAN + command + [state['podman_id']])
    else:
        state = inspect()
        if args.require_podman_running and not (state['podman_running'] and state['podman_service_active'] and state['podman_enabled']):
            raise RuntimeError('Podman container or supervisor is not active/enabled')
        print(json.dumps(state))
