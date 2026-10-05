#!/usr/bin/env python3
"""Read-only ownership checks; refuse ambiguous Xray resources, never discover by port."""
import json
import pathlib
import shutil
import subprocess


def inspect(root=pathlib.Path('/'), call=subprocess.run, docker=None):
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
                    service.get('image') != 'ghcr.io/xtls/xray-core:25.10.15' or
                    not any(v.get('source') == '/opt/xray/config' and
                            v.get('target') == '/usr/local/etc/xray' for v in volumes)):
                raise RuntimeError('Refusing unrelated Docker configuration')
    if not native and any((root / p).exists() for p in
                          ['usr/local/bin/xray', 'usr/local/etc/xray/config.json']):
        raise RuntimeError('Refusing native artifacts without a managed unit')
    active = call(['systemctl', 'is-active', 'xray'], capture_output=True, text=True).stdout.strip() == 'active'
    enabled = call(['systemctl', 'is-enabled', 'xray'], capture_output=True, text=True).stdout.strip() == 'enabled'
    return dict(native_exists=native, native_running=active, native_enabled=enabled,
                docker_exists=exists, docker_running=running, docker_id=container_id,
                native_port=native_port, docker_ports=docker_ports)


if __name__ == '__main__':
    print(json.dumps(inspect()))
