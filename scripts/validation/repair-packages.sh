#!/usr/bin/env bash
set -euo pipefail
# Keep the kernel package set consistent with the latest official Ubuntu archive.
sudo -n python3 - <<'MIRROR'
import pathlib
paths=[pathlib.Path('/etc/apt/sources.list')]
root=pathlib.Path('/etc/apt/sources.list.d')
paths+=list(root.glob('*.sources'))+list(root.glob('*.list'))
for f in paths:
 if f.exists():
  old=f.read_text();new=old.replace('ap-southeast-1.ec2.archive.ubuntu.com','archive.ubuntu.com')
  if new!=old:
   backup=f.with_name(f.name+'.pre-proxy-validation')
   if not backup.exists():backup.write_text(old)
   f.write_text(new)
   print('Use official Ubuntu archive:',f)
MIRROR
sudo -n apt-cache policy linux-aws linux-image-aws linux-headers-aws
sudo -n timeout 240 apt-get -o DPkg::Lock::Timeout=120 update
sudo -n apt-cache -o APT::Get::Always-Include-Phased-Updates=true policy linux-aws linux-image-aws linux-headers-aws
sudo -n timeout 600 env DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=120 -o APT::Get::Always-Include-Phased-Updates=true -y --no-install-recommends install linux-aws
sudo -n apt-get check
sudo -n dpkg-query -W linux-aws linux-image-aws linux-headers-aws
sudo -n dpkg --audit
uname -r
free -h
sudo -n journalctl -k -b --no-pager --grep='Out of memory|oom-kill' || test "$?" = 1
