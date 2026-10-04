#!/usr/bin/env bash
set -euo pipefail
sudo -n timeout 240 apt-get -o DPkg::Lock::Timeout=120 update
sudo -n timeout 600 env DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=120 -y --no-install-recommends --fix-broken install
sudo -n apt-get check
sudo -n dpkg-query -W linux-aws linux-image-aws linux-headers-aws
sudo -n dpkg --audit
uname -r
free -h
sudo -n journalctl -k -b --no-pager --grep='Out of memory|oom-kill' || test "$?" = 1
