# Project specifications

Deploy native official Xray VLESS/REALITY under systemd using runner-side Ansible.
Checksum-pin reviewed release archives, stage and validate the candidate configuration
before activation, restrict secret file access and preserve unchanged processes.
Require completed infrastructure bootstrap and active boot policy. Use a dedicated
Xray account with CAP_NET_BIND_SERVICE, restart-on-failure, persistent bounded
journald logs and no periodic reboot or automatic package/binary updates.

Credentials remain in GitHub Actions environments. No supplied personal configuration,
private keys or Terraform state may be committed. Run Ansible syntax checks, artifact
integrity tests and actual configuration validation with reviewed binaries. Deployment
acceptance requires authenticated HTTPS traffic using both supplied client transport
profiles, unchanged-redeployment, log rotation and reboot/failure recovery checks.
Refer to docs/native-xray.md for paths, version pins, platform scope and test operations.
