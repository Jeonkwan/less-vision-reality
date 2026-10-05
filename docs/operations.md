# Native Xray operations

See [native deployment](native-xray.md), [development setup](development.md) and
[secrets management](secrets-management.md). The native feature uses runner-side
Ansible and a checksum-verified release binary, without Docker on the VM.

Deploy via the feature branch's Deploy Xray Stack workflow with the selected
GitHub environment, host address/user and reviewed xray_version. Provision the
basic VM first and require the bootstrap marker and active kho=off. Credentials
come from environment secrets. Use the Native Xray validation workflow with an
explicit target and expected IP for authenticated sing-box and Clash/mihomo
checks, inspection, reboot/failure recovery and journal rotation.

Read service state with `systemctl status xray` and bounded logs with
`journalctl -u xray -n 80 --no-pager`. Do not dump config files or unredacted
credentials. Standard logs are managed by journald, not a logrotate cron job.
Unchanged deployment does not restart the service. Explicit stop/restart uses
Ansible tags xray_down/xray_reload. Initial host support is Ubuntu x86-64/systemd.
