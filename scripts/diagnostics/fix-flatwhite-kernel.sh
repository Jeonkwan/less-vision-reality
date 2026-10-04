#!/usr/bin/env bash
set -euo pipefail
uname -r
cat /proc/cmdline
free -h
sudo -n timeout 420 env DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=120 install --no-install-recommends -y linux-image-6.17.0-1019-aws linux-modules-6.17.0-1019-aws
[ -s /boot/vmlinuz-6.17.0-1019-aws ]
[ -s /boot/initrd.img-6.17.0-1019-aws ]
sudo -n python3 - <<'PIN'
from pathlib import Path
text=Path('/boot/grub/grub.cfg').read_text()
assert "submenu 'Advanced options for Ubuntu'" in text
assert "menuentry 'Ubuntu, with Linux 6.17.0-1019-aws'" in text
p=Path('/etc/default/grub.d/99-proxy-kernel.cfg')
assert not p.exists(), 'Refusing to overwrite unexpected kernel override'
p.write_text('# Use the official Ubuntu AWS kernel version verified on Decaf.\nGRUB_DEFAULT="Advanced options for Ubuntu>Ubuntu, with Linux 6.17.0-1019-aws"\n')
p.chmod(0o644)
PIN
sudo -n update-grub
sudo -n grep '^GRUB_DEFAULT' /etc/default/grub.d/99-proxy-kernel.cfg
sudo -n grep '6.17.0-1019-aws' /boot/grub/grub.cfg | head -5
