# Less Vision Reality Automation

Deploy official Xray VLESS/REALITY with controller-side Ansible, choosing native
systemd (default) or pinned Docker Compose. See [runtime selection, switching and
rollback](docs/selectable-xray-runtime.md) for exact commands and validation status.

Contributors start with [AGENTS.md](AGENTS.md), [development setup](docs/development.md)
and [disposable VM strategy](docs/disposable-proxy-vms.md). Provision basic-vm in the
Lightsail repository separately. Runtime deployment never reboots the host or
installs server-side Ansible. Native uses verified reviewed binaries and a dedicated
unprivileged account; Docker installs prerequisites only when selected. Both retain
shared client credentials, boot/maintenance policy and bounded host journals.

The **Deploy Xray Stack** workflow accepts a credential environment, target SSH
address/user, `deployment_mode`, native `xray_version`, Docker
`container_image_version`, and explicit `allow_runtime_switch`. Version defaults
remain native 26.3.27 and Docker 26.3.27. Credentials are supplied by the selected
environment or existing overrides; optional SNI falls back to `web.wechat.com`.

Use [setup](docs/setup.md), [operations](docs/operations.md) and
[secrets management](docs/secrets-management.md) for details. `diagnose.yml` validates
the selected mode with explicit target/IP and operator-selected credential environment.
CI executes selector/ownership checks, validates the shared template with both
reviewed official binaries and syntax-checks both runtime modes. Live acceptance
requires the spare-instance sequence in the runtime guide; this refactor has not
been deployed to serving nodes.

## Credential generation

The existing manual/PR credential workflows and `scripts/generate_xray_credentials.sh`
use throwaway Docker containers on the controller to generate UUIDs, short IDs and
Reality key pairs using pinned Xray 26.3.27. Docker is optional for local credential
generation and unnecessary on native VMs. Store generated values securely; never
commit credential output or personal client files. Supply `XRAY_UUID`, `XRAY_SHORT_IDS`,
`XRAY_PRIVATE_KEY`, `XRAY_PUBLIC_KEY` and optional `XRAY_SNI` to deployment securely.

Prior native-only deployment evidence remains in
[native validation](docs/native-xray-validation.md) and
[Decaf validation](docs/decaf-native-validation.md). Existing draft branches and
immutable release tags remain unchanged. New work uses
`feature/selectable-xray-runtime`, targeting `feature/native-xray`.

See [Americano/Latte validation and cleanup](docs/selectable-runtime-validation.md) for the task scope and evidence.
