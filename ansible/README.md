# Selectable Xray Ansible deployment

See [runtime selection, switching and rollback](../docs/selectable-xray-runtime.md)
and [development setup](../docs/development.md). Native systemd is the default;
`-e xray_deployment_mode=docker` selects pinned Docker Compose. Ansible runs on the
controller. Use `xray_down`, `xray_reload` and `xray_recreate` with the same selector.
All modes validate candidates before activation and preserve an unchanged runtime.

`-e xray_deployment_mode=podman` selects rootful Podman supervised by systemd,
without Compose. See [Podman runtime](../docs/podman-xray.md).
