#!/usr/bin/env python3
"""Read-only ownership checks; refuse ambiguous Xray resources, never discover by port."""
import json
import argparse
import os
import pathlib
import shutil
import subprocess


PODMAN = ['podman', '--remote=false']
PODMAN_ROOT = '/opt/xray-podman'
PODMAN_MARKER = 'less-vision-reality podman-runtime v1\n'
PODMAN_LABELS = {'io.github.jeonkwan.less-vision-reality.runtime': 'podman',
                 'io.github.jeonkwan.less-vision-reality.root': PODMAN_ROOT}


def inspect_podman(root=pathlib.Path('/'), call=subprocess.run, podman=None, supervising=False):
    unit = root / 'etc/systemd/system/xray-podman.service'
    deployment = root / 'opt/xray-podman'
    marker = deployment / '.managed-by-less-vision-reality'
    for path in [unit, deployment, marker, deployment / 'config', deployment / 'config/config.json']:
        if path.is_symlink():
            raise RuntimeError('Refusing symlinked Podman deployment')
    if deployment.exists() and (not marker.exists() or marker.read_text() != PODMAN_MARKER):
        raise RuntimeError('Refusing unmarked Podman deployment directory')
    if unit.exists():
        required = ['Description=Xray VLESS REALITY proxy (managed Podman)', 'Type=simple',
                    'ExecStart=/usr/bin/python3 /opt/xray-podman/runtime-ownership.py --podman-action start',
                    'ExecStop=/usr/bin/python3 /opt/xray-podman/runtime-ownership.py --podman-action stop',
                    'Restart=always', 'WantedBy=multi-user.target']
        if not marker.exists() or not all(line in unit.read_text().splitlines() for line in required):
            raise RuntimeError('Refusing unmanaged xray-podman.service')
        if any(unit.with_name('xray-podman.service.d').glob('*.conf')):
            raise RuntimeError('Refusing unmanaged Podman service overrides')
    else:
        result = call(['systemctl', 'show', 'xray-podman', '-p', 'LoadState', '--value'],
                      capture_output=True, text=True, check=False)
        if result.stdout.strip() != 'not-found':
            raise RuntimeError('Refusing Podman unit outside managed path')
    state = dict(podman_unit_exists=unit.exists(), podman_exists=False, podman_running=False,
                 podman_enabled=False, podman_id='', podman_image='', podman_image_ref='', podman_ports=[])
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
            bindings = data.get('HostConfig', {}).get('PortBindings') or {}
            ports = [int(b['HostPort']) for values in bindings.values() for b in (values or [])]
            if set(bindings) != {'443/tcp'} or ports != [443]:
                raise RuntimeError('Refusing unexpected Podman port mappings')
            if data['HostConfig']['LogConfig']['Type'] != 'journald' or data['HostConfig']['RestartPolicy']['Name'] not in ['', 'no']:
                raise RuntimeError('Refusing unexpected Podman supervision or logging')
            state.update(podman_exists=True, podman_running=data['State']['Running'],
                         podman_id=data['Id'], podman_image=data['Image'], podman_image_ref=data['Config']['Image'], podman_ports=ports)
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
    parser.add_argument('--podman-action', choices=['start', 'stop'])
    parser.add_argument('--require-podman-running', action='store_true')
    args = parser.parse_args()
    if args.podman_action:
        state = inspect_podman(supervising=True)
        if not state['podman_exists']:
            raise RuntimeError('Verified Podman container is missing')
        command = ['start', '--attach'] if args.podman_action == 'start' else ['stop', '--time', '10']
        os.execvp('podman', PODMAN + command + [state['podman_id']])
    else:
        state = inspect()
        if args.require_podman_running and not (state['podman_running'] and state['podman_service_active'] and state['podman_enabled']):
            raise RuntimeError('Podman container or supervisor is not active/enabled')
        print(json.dumps(state))
