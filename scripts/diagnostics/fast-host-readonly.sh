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
sudo -n python3 - <<'DISABLE'
from pathlib import Path
p=Path('/etc/cron.d/daily-reboot');text=p.read_text();jobs=[l.strip() for l in text.splitlines() if l.strip() and not l.lstrip().startswith('#')]
assert jobs==['0 21 * * * root /sbin/shutdown -r now'],jobs
backup=Path('/etc/proxy-maintenance');backup.mkdir(mode=0o700,exist_ok=True)
(backup/'daily-reboot.before-disable').write_text(text)
p.write_text('# Daily OS reboot disabled after failed Flat White recovery test on 2026-10-04.\n# Original schedule: 0 21 * * * root /sbin/shutdown -r now\n')
p.chmod(0o644)
for f in Path('/etc/cron.d').iterdir():
 if f.is_file():
  for line in f.read_text(errors='replace').splitlines():
   if line.strip() and not line.lstrip().startswith('#') and ('shutdown' in line or 'reboot' in line):
    raise SystemExit('Unexpected active reboot job: '+f.name+' '+line)
print('No active reboot entries in /etc/cron.d; original schedule backed up outside cron directory.')
DISABLE
