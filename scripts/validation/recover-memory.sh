#!/usr/bin/env bash
set -euo pipefail
uname -r
sudo -n mkdir -p /var/lib/proxy-validation
uname -r | sudo -n tee /var/lib/proxy-validation/expected-kernel
sudo -n tee /etc/default/grub.d/98-cream-validation-kho.cfg >/dev/null <<'GRUB'
# Isolated new Cream test: retain current kernel, disable optional Kexec HandOver.
GRUB_CMDLINE_LINUX_DEFAULT="${GRUB_CMDLINE_LINUX_DEFAULT} kho=off"
GRUB
sudo -n chmod 644 /etc/default/grub.d/98-cream-validation-kho.cfg
sudo -n update-grub
