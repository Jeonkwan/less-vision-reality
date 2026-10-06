# Setup guide

Use Linux/Bash and the pinned tools in [development setup](development.md).
Provision a basic Ubuntu VM from the Lightsail repository, then use controller-side
Ansible after bootstrap completes and `kho=off` is active. See
[selectable runtime](selectable-xray-runtime.md) for commands and mode dependencies.

Native mode needs SSH, Python3 and CA certificates on the VM; release downloads and
verification run on the controller. Docker mode additionally needs outbound package
repository/GHCR access and installs its missing curl/GPG/repository tools, Engine and
Compose plugin. Podman mode installs distribution Podman plus netavark/aardvark-dns and uses a
regular systemd supervisor without Compose. No mode installs Ansible or a Docker SDK
on the VM. See [Podman setup](podman-xray.md). Allow the
configured `xray_host_port` (443 by default) in the Lightsail firewall.

Define target hosts under `xray_servers`. Supply credentials securely through Vault,
environment variables or the selected GitHub Actions environment. Default SNI is
`web.wechat.com`; `XRAY_SNI` or the existing Actions fallback variable overrides it.
Keep SSH keys, personal client files, state and secrets outside tracked files.
Local static checks need no AWS credentials or SSH keys. Live deployment requires
an explicitly selected target and authorized scope; serving peers must stay healthy.
