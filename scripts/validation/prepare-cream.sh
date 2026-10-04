#!/usr/bin/env bash
set -euo pipefail
sudo -n cloud-init status
uname -r
free -h
sudo -n dpkg-query -W -f='${Package} ${Status}
' kmod linux-base microcode-initrd
work=$(mktemp -d /tmp/cream-kernel.XXXXXX)
trap 'rm -rf "$work"' EXIT
cd "$work"
download() {
 url=$1
 filename=$2
 size=$3
 digest=$4
 for attempt in 1 2 3; do
  # Direct I/O avoids filling this small host's page cache with kernel archives.
  if curl --fail --silent --show-error --location --max-time 240 "$url" | dd of="$filename" oflag=direct iflag=fullblock conv=sync bs=64K status=none; then
   truncate --size="$size" "$filename"
   if printf '%s  %s\n' "$digest" "$filename" | sha256sum --check; then return 0; fi
  fi
  echo "Kernel package download attempt $attempt failed"
  rm -f "$filename"
  sleep 3
 done
 return 1
}
download 'https://archive.ubuntu.com/ubuntu/pool/main/l/linux-aws-7.0/linux-modules-7.0.0-1014-aws_7.0.0-1014.14~24.04.1_amd64.deb' kernel-0.deb 148428992 '918e98bed5dae1ab40bfb3bc91e9456c1321435533165a9d7023ac60301c1e88'
download 'https://archive.ubuntu.com/ubuntu/pool/main/l/linux-signed-aws-7.0/linux-image-7.0.0-1014-aws_7.0.0-1014.14~24.04.1_amd64.deb' kernel-1.deb 16695418 'bb4e1aae90d41945b100459233ee440c3494e019467f9a2e60ec931f988cf00b'
download 'https://archive.ubuntu.com/ubuntu/pool/main/l/linux-meta-aws-7.0/linux-image-aws_7.0.0-1014.14~24.04.1_amd64.deb' kernel-2.deb 2462 '6e2b2a0bee8ee3e4bbd9d47c771126373080336e791bb2544e31560f4cf2ab61'
sudo -n timeout 600 env DEBIAN_FRONTEND=noninteractive DPKG_DEB_THREADS_MAX=1 dpkg -i kernel-0.deb kernel-1.deb kernel-2.deb
sudo -n mkdir -p /var/lib/proxy-validation
sudo -n sh -c 'test -f /boot/vmlinuz-7.0.0-1014-aws && test ! -f /etc/default/grub.d/99-proxy-kernel.cfg && printf "%s\n" 7.0.0-1014-aws > /var/lib/proxy-validation/expected-kernel'
sudo -n dpkg-query -W linux-image-aws linux-image-7.0.0-1014-aws linux-modules-7.0.0-1014-aws
