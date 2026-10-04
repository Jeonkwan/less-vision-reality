#!/usr/bin/env python3
"""Read-only TCP and authenticated sing-box checks on an Internet-connected host.

Use --config with a supplied sing-box config, or supply XRAY_UUID,
XRAY_PUBLIC_KEY, and XRAY_SHORT_IDS through the environment. No secrets are printed.
"""
import argparse
import copy
import hashlib
import json
import os
import pathlib
import shutil
import socket
import subprocess
import tempfile
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=pathlib.Path)
    parser.add_argument('--sing-box', default='sing-box')
    parser.add_argument('--nodes', nargs='+', choices=('cream', 'flatwhite', 'decaf'), default=['cream', 'decaf'])
    parser.add_argument('--expected-flatwhite-ip')
    args = parser.parse_args()
    if args.expected_flatwhite_ip:
        resolved = {x[4][0] for x in socket.getaddrinfo('flatwhite.mokamaker.site', 443, type=socket.SOCK_STREAM)}
        print('Flat White DNS matches new instance:', resolved == {args.expected_flatwhite_ip}, flush=True)
        if resolved != {args.expected_flatwhite_ip}:
            raise SystemExit('Flat White DNS has not resolved to the verified new instance')
    if args.config:
        original = json.loads(args.config.read_text())
        outbounds = {o['tag']: o for o in original['outbounds'] if o.get('tag') in args.nodes}
    else:
        uuid = os.environ['XRAY_UUID']
        public = os.environ['XRAY_PUBLIC_KEY']
        sid = os.environ['XRAY_SHORT_IDS'].split(',')[0].strip()
        outbounds = {
            name: {'type': 'vless', 'tag': name, 'server': name + '.mokamaker.site',
                   'server_port': 443, 'uuid': uuid, 'flow': 'xtls-rprx-vision',
                   'tls': {'enabled': True, 'server_name': 'web.wechat.com',
                           'utls': {'enabled': True, 'fingerprint': 'chrome'},
                           'reality': {'enabled': True, 'public_key': public, 'short_id': sid}}}
            for name in args.nodes
        }
        # Compare without logging credentials.
        print('Deployment public key matches supplied clients:', public == 'c8UlOfsM1xr3sXJB51xsZkVfsmQf4iGYwb9TRvZZ038')
        print('Deployment first short ID matches supplied clients:', sid == 'f2a5aebaa3acb89d')
        print('Deployment UUID matches supplied clients:', hashlib.sha256(uuid.encode()).hexdigest()[:12] == '6318c1ff6c69')
    binary = shutil.which(args.sing_box)
    if not binary:
        raise SystemExit('sing-box executable not found')
    if not args.config and not (public == 'c8UlOfsM1xr3sXJB51xsZkVfsmQf4iGYwb9TRvZZ038' and sid == 'f2a5aebaa3acb89d' and hashlib.sha256(uuid.encode()).hexdigest()[:12] == '6318c1ff6c69'):
        raise SystemExit('Deployment credentials do not match the supplied clients')
    failed = False
    for name in args.nodes:
        outbound = copy.deepcopy(outbounds[name])
        host = outbound['server']
        port = outbound['server_port']
        print('\nEndpoint:', name, host, port, flush=True)
        try:
            print('DNS:', sorted({x[4][0] for x in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}), flush=True)
            with socket.create_connection((host, port), timeout=8):
                print('TCP 443: PASS', flush=True)
        except OSError as exc:
            print('TCP 443: FAIL', str(exc), flush=True)
            failed = True
            continue
        for attempt in range(1, 3):
            with tempfile.TemporaryDirectory(prefix='proxy-check-') as temp:
                with socket.socket() as listener:
                    listener.bind(('127.0.0.1', 0))
                    local_port = listener.getsockname()[1]
                config = {'log': {'level': 'error'},
                          'inbounds': [{'type': 'socks', 'tag': 'test-in', 'listen': '127.0.0.1', 'listen_port': local_port}],
                          'outbounds': [outbound], 'route': {'final': name}}
                path = pathlib.Path(temp) / 'config.json'
                path.write_text(json.dumps(config))
                path.chmod(0o600)
                checked = subprocess.run([binary, 'check', '-c', str(path)], capture_output=True)
                if checked.returncode:
                    print('Minimal client config: FAIL; check local sing-box version', flush=True)
                    failed = True
                    break
                process = subprocess.Popen([binary, 'run', '-c', str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                try:
                    ready = False
                    for _ in range(50):
                        if process.poll() is not None:
                            break
                        try:
                            with socket.create_connection(('127.0.0.1', local_port), timeout=0.1):
                                ready = True
                                break
                        except OSError:
                            time.sleep(0.1)
                    if not ready:
                        print('Local client startup: FAIL', flush=True)
                        failed = True
                        break
                    # socks5-hostname sends target DNS through the authenticated proxy.
                    for url in ('https://www.cloudflare.com/cdn-cgi/trace', 'https://www.gstatic.com/generate_204'):
                        result = subprocess.run(['curl', '--silent', '--show-error', '--fail', '--max-time', '15',
                                                 '--noproxy', '', '--proxy', f'socks5h://127.0.0.1:{local_port}',
                                                 '--output', os.devnull, '--write-out', '%{http_code}', url], capture_output=True, text=True)
                        print('REALITY attempt', attempt, url, 'PASS' if result.returncode == 0 else 'FAIL',
                              'HTTP', result.stdout, result.stderr.strip()[:250], flush=True)
                        failed |= result.returncode != 0
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
