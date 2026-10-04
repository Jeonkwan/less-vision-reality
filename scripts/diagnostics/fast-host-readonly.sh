#!/usr/bin/env bash
set -u
for command in 'date -u' 'uptime' 'uname -r' 'cat /proc/sys/kernel/random/boot_id' 'free -h' 'swapon --show' "ps -eo pid,comm,stat,pcpu,pmem,wchan:30 --sort=-pcpu | head -25" 'systemctl --failed --no-pager' 'systemctl list-jobs --no-pager' 'systemctl status docker --no-pager' "sudo -n journalctl -k -b --no-pager -n 60" "sudo -n journalctl -u docker -b --no-pager -n 35" 'sudo -n docker ps -a --format "{{.Names}} {{.Status}}"' 'ls /boot/vmlinuz*'; do
 echo "=== $command"
 timeout 5 bash -c "$command" || true
done

for command in 'sudo -n journalctl --list-boots --no-pager' 'last -x -n 22' "sudo -n journalctl -k -b -1 --no-pager --grep='Out of memory|oom|Killed process|blocked for|soft lockup|BUG:|panic|hung|Memory:' -n 60" "sudo -n journalctl -b -1 -p warning --no-pager -n 60" "sudo -n journalctl -u docker -b -1 --no-pager -n 30" 'systemd-analyze time' 'systemd-analyze blame | head -12'; do
 echo "=== $command"
 timeout 8 bash -c "$command" || true
done

for command in 'cat /proc/cmdline' "cat /proc/meminfo | head -12; cat /proc/meminfo | tail -15" "sudo -n journalctl -k -b -1 --no-pager | head -80" "sudo -n journalctl -k -b -1 --no-pager --grep='cma|CMA|reserved|Memory:' -n 25" 'apt-cache policy linux-image-6.17.0-1019-aws linux-image-6.17.0-1018-aws linux-image-6.8.0-1046-aws' 'cat /etc/default/grub; ls /etc/default/grub.d'; do
 echo "=== $command"
 timeout 8 bash -c "$command" || true
done
