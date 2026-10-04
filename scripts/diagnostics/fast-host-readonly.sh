#!/usr/bin/env bash
set -u
for command in 'date -u' 'uptime' 'uname -r' 'cat /proc/sys/kernel/random/boot_id' 'free -h' 'swapon --show' "ps -eo pid,comm,stat,pcpu,pmem,wchan:30 --sort=-pcpu | head -25" 'systemctl --failed --no-pager' 'systemctl list-jobs --no-pager' 'systemctl status docker --no-pager' "sudo -n journalctl -k -b --no-pager -n 60" "sudo -n journalctl -u docker -b --no-pager -n 35" 'sudo -n docker ps -a --format "{{.Names}} {{.Status}}"' 'ls /boot/vmlinuz*'; do
 echo "=== $command"
 timeout 5 bash -c "$command" || true
done
