"""Validate the shared template with both checksum-verified reviewed release binaries.

Downloads run on the controller. Temporary generated credentials never leave it.
This validates Xray configuration parsing, not a Docker deployment or transport.
"""
import importlib.util
import json
import pathlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from jinja2 import Environment

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('prepare', ROOT / 'scripts/prepare-native.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class ConfigCompatibility(unittest.TestCase):
    def test_reviewed_binaries_accept_both_mode_templates(self):
        template = Environment().from_string((ROOT / 'ansible/templates/config.json.j2').read_text())
        with tempfile.TemporaryDirectory(prefix='xray-config-validation-') as tmp:
            for version in prepare.RELEASES:
                directory = pathlib.Path(tmp) / version
                with patch('sys.argv', ['prepare-native.py', '--version', version,
                                       '--directory', str(directory)]):
                    prepare.main()
                binary = directory / 'xray'
                keys = subprocess.check_output([str(binary), 'x25519'], text=True)
                private = next(line.split(':', 1)[1].strip() for line in keys.splitlines()
                               if line.startswith('Private key:') or line.startswith('PrivateKey:'))
                for mode in ['native', 'docker']:
                    with self.subTest(version=version, mode=mode):
                        config = template.render(xray_deployment_mode=mode, xray_host_port=8443,
                                                 xray_container_port=443, xray_sni='',
                                                 xray_uuid='00000000-0000-4000-8000-000000000000',
                                                 xray_short_ids=['deadbeefcafebabe'],
                                                 xray_reality_private_key=private)
                        self.assertEqual(json.loads(config)['inbounds'][0]['port'],
                                         8443 if mode=='native' else 443)
                        candidate = directory / 'config.json'; candidate.write_text(config); candidate.chmod(0o600)
                        result = subprocess.run([str(binary), 'run', '-test', '-config', str(candidate)],
                                                capture_output=True, text=True)
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                        candidate.write_text('{invalid')
                        result = subprocess.run([str(binary), 'run', '-test', '-config', str(candidate)],
                                                capture_output=True, text=True)
                        self.assertNotEqual(result.returncode, 0)


if __name__ == '__main__': unittest.main()
