# Native Xray Ansible deployment

See [native deployment](../docs/native-xray.md) and [development setup](../docs/development.md).
Run `scripts/prepare-native.py` on the control host, export its binary path/checksum,
and supply XRAY_UUID, XRAY_SHORT_IDS, XRAY_PRIVATE_KEY, XRAY_PUBLIC_KEY and optional
XRAY_SNI through the environment. Run `ansible-playbook -i inventory.yml site.yml`.
Never install Ansible on the proxy VM. `--tags xray_down` stops the service and
`--tags xray_reload` restarts it explicitly. Normal unchanged runs do not restart.
