#!/usr/bin/env bash
# Consolidate the two deployment-managed reboot jobs to 05:00 China time.
set -euo pipefail
date -u
uptime
sudo -n systemctl --failed --no-pager || true
sudo -n systemctl is-active docker cron || true
sudo -n cloud-init status || true
ps -eo pid,comm,stat,%cpu,%mem --sort=-%cpu | head -n 12
sudo -n docker inspect xray --format 'Status={{.State.Status}} OOMKilled={{.State.OOMKilled}} RestartCount={{.RestartCount}}' || true
sudo -n python3 - <<'PY'
import datetime,os,pathlib,re,subprocess,tempfile
offset=datetime.datetime.now().astimezone().utcoffset()
if offset!=datetime.timedelta(0):
    raise SystemExit('Host timezone is not UTC; schedule needs timezone-aware review.')
print('Host timezone has UTC offset; 21:00 host time = 05:00 Asia/Shanghai.')
daily=pathlib.Path('/etc/cron.d/daily-reboot')
xray=pathlib.Path('/etc/cron.d/xray')
expected=re.compile(r'^0\s+20\s+\*\s+\*\s+\*\s+root\s+/usr/sbin/shutdown\s+-r\s+now\s*$')
old=xray.read_text() if xray.exists() else ''
lines=old.splitlines()
unknown=[line for line in lines if line.strip() and not line.lstrip().startswith('#') and not expected.fullmatch(line)]
if any('shutdown' in line or 'reboot' in line for line in unknown):
    raise SystemExit('Unexpected Xray reboot entry; refusing to replace it.')
if daily.exists():
    print('Existing deployment daily-reboot job:',daily.read_text().strip())
print('Existing Xray maintenance cron:',old.strip() or '[absent]')
new='# Daily reboot at 05:00 China time (UTC+8); host timezone UTC.\n0 21 * * * root /sbin/shutdown -r now\n'
fd,temp=tempfile.mkstemp(prefix='.daily-reboot-',dir='/etc/cron.d')
try:
    with os.fdopen(fd,'w') as f: f.write(new)
    os.chmod(temp,0o644)
    os.chown(temp,0,0)
    os.replace(temp,daily)
finally:
    if os.path.exists(temp):os.unlink(temp)
if xray.exists() and any(expected.fullmatch(line) for line in lines):
    kept=[line for line in lines if not expected.fullmatch(line) and line!='#Ansible: Daily reboot to refresh Xray environment']
    if any(line.strip() and not line.lstrip().startswith('#') for line in kept):
        xray.write_text('\n'.join(kept)+'\n')
    else:
        xray.unlink()
subprocess.run(['systemctl','enable','--now','cron'],check=True)
print('Final daily-reboot schedule:',daily.read_text().strip())
print('Cron service:',subprocess.check_output(['systemctl','is-active','cron'],text=True).strip())
print('Reboot entries across /etc/cron.d:')
for p in pathlib.Path('/etc/cron.d').iterdir():
    if p.is_file():
        for line in p.read_text(errors='replace').splitlines():
            if line.strip() and not line.lstrip().startswith('#') and ('shutdown' in line or 'reboot' in line):
                print(p.name,line)
PY
