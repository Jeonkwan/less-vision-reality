#!/usr/bin/env bash
set -euo pipefail
sudo -n timeout 600 cloud-init status --wait
uname -r
sudo -n timeout 240 apt-get -o DPkg::Lock::Timeout=120 update
sudo -n timeout 600 env DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=120 install --no-install-recommends -y linux-image-aws
sudo -n mkdir -p /var/lib/proxy-validation
sudo -n python3 - <<'KERNEL'
import pathlib,re,subprocess
text=subprocess.check_output(['apt-cache','policy','linux-image-aws'],text=True)
print(text)
installed=re.search(r'Installed: (\S+)',text).group(1)
candidate=re.search(r'Candidate: (\S+)',text).group(1)
assert installed==candidate,(installed,candidate)
deps=subprocess.check_output(['dpkg-query','-W','-f=${Depends}','linux-image-aws'],text=True)
kernel=re.search(r'linux-image-(\d[^ ,(]+)',deps).group(1)
assert pathlib.Path('/boot/vmlinuz-'+kernel).exists(),kernel
assert not pathlib.Path('/etc/default/grub.d/99-proxy-kernel.cfg').exists(), 'Old kernel workaround must not be present'
pathlib.Path('/var/lib/proxy-validation/expected-kernel').write_text(kernel+'\n')
print('Current repository kernel selected for test:',kernel)
KERNEL
