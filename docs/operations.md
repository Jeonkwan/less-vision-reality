# Xray operations

Start with [selectable runtime](selectable-xray-runtime.md) for exact deployment,
switch and rollback commands, [development setup](development.md) and
[secrets management](secrets-management.md). Ansible runs on the controller;
`xray_deployment_mode=native|docker|podman` defaults to native. Provision basic-vm first.

Read native service state with `systemctl status xray` and bounded logs with
`journalctl -u xray -n 80 --no-pager`. Read Docker state with
`sudo docker inspect --format '{{json .State}}' xray` and bounded logs with
`sudo docker logs --tail 80 xray`. Do not dump configuration or unredacted secrets.
Use `diagnose.yml` with the selected mode, credential environment, target and
expected IP for both client checks, inspection, baseline comparison, bounded-log
rotation and explicitly authorized reboot/failure recovery.

Normal unchanged deployment preserves the process/container and host boot.
Lifecycle tags `xray_down`, `xray_reload` and `xray_recreate` honor the runtime
selector. A deliberate switch validates candidates before stopping the verified
opposite runtime; unrelated containers, networks and configuration are preserved.
Native logs need no separate text-log/logrotate job. Initial platform support is
Ubuntu x86-64/systemd. No automatic package or runtime updates are introduced.

Read Podman state with `sudo systemctl status xray-podman` and
`sudo podman --remote=false inspect xray-podman`. Bounded container logs use
`sudo journalctl CONTAINER_NAME=xray-podman -n 80 --no-pager`. See
[Podman ownership and switching](podman-xray.md) before live operations.
