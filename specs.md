# Project specifications

Deploy official Xray VLESS/REALITY using controller-side Ansible with a selectable
native systemd (default), pinned Docker Compose, or rootful Podman runtime. See
[selectable runtime](docs/selectable-xray-runtime.md) for the shared contract.
Checksum-pin reviewed release archives, stage and validate the candidate configuration
before activation, restrict secret file access and preserve unchanged processes.
Require completed infrastructure bootstrap and active boot policy. Native uses a dedicated
Xray account with CAP_NET_BIND_SERVICE and restart-on-failure. Podman runs image
UID/GID 65532 under systemd with the shared bounded journald policy. All modes have
bounded logs and no periodic reboot or automatic package/binary updates.

Credentials remain in GitHub Actions environments. No supplied personal configuration,
private keys or Terraform state may be committed. Run Ansible syntax checks, artifact
integrity tests and actual configuration validation with reviewed binaries. Deployment
acceptance requires authenticated HTTPS traffic using both supplied client transport
profiles, unchanged-redeployment, log rotation and reboot/failure recovery checks.
Refer to docs/native-xray.md for paths, version pins, platform scope and test operations.

See [Podman contract](docs/podman-xray.md) for the additional mode and focused
owner-approved flatwhite acceptance scope.
