# Development environment

For selectable native/Docker deployment, switching and the spare-validation plan, see [selectable runtime](selectable-xray-runtime.md).

Use a Linux workstation or CI runner with Bash, Git, curl, OpenSSH client and
Python 3.12 (including venv/pip). Install tools on the control host, not on the
512 MB proxy VM. macOS can be used with equivalent tools; the documented checks
have been validated on Linux.

## Tools and setup

| Tool | Version / purpose |
| --- | --- |
| Python | 3.12; local development and Ansible control host |
| GitHub CLI (`gh`) | Authenticated CLI for repository access and Actions; tested 2.46.0 |
| Terraform | 1.6.6; infrastructure repo CI version |
| Ansible core | 2.16.19; tested with Python 3.12 |
| Docker Engine / Compose | Optional on workstation; credential generation requires Docker; not required on native deployed hosts |
| AWS CLI v2 | Optional for direct AWS inspection; unnecessary for local static checks |
| sing-box | Optional 1.11.4 for supplied legacy client configurations and authenticated proxy validation |

Install Git, curl, OpenSSH, Python 3.12 and its venv support through your platform's
package manager. Install `gh` using the official GitHub CLI instructions and
Terraform 1.6.6 from HashiCorp's official release (verify its checksum). Add the
executables to PATH. These tools are prerequisites; cloning does not install them.

Create a dedicated virtual environment outside tracked files:

```bash
python3.12 -m venv "$HOME/.venvs/proxy-development"
source "$HOME/.venvs/proxy-development/bin/activate"
python -m pip install 'ansible-core==2.16.19'
python --version
ansible --version
terraform version
gh --version
```

The selectable playbook uses `ansible.builtin` modules for native systemd or Docker Compose deployment. Native remains the default. No extra Ansible Galaxy collection or Python Docker SDK is
required for this deployment. Python's standard library suffices for the
bootstrap tests and diagnostic script. Do not install unrelated packages by default.

For the previously prepared workspace, `source /workspace/proxy/activate.sh`
selects its installed tools and writable Ansible/cache paths. That helper is
workspace-specific and is not part of a fresh repository clone.

## Repository relationship

Clone `Jeonkwan/lightsail-proxy` (Terraform and OS bootstrap) and
`Jeonkwan/less-vision-reality` (Ansible and Xray) as sibling directories. Changes
currently use `feature/selectable-xray-runtime` in both repositories. Check remote branch
availability before checkout; do not assume it remains the development branch
forever. `Jeonkwan/gcp-proxy` is a separate optional infrastructure project;
GCP credentials and tooling are not prerequisites for this Lightsail work.

```bash
mkdir -p proxy-workspace
cd proxy-workspace
gh repo clone Jeonkwan/lightsail-proxy
gh repo clone Jeonkwan/less-vision-reality
git -C lightsail-proxy switch feature/selectable-xray-runtime
git -C less-vision-reality switch feature/selectable-xray-runtime
```

## Authentication and configuration

Local syntax/bootstrap checks below require no AWS account credentials, SSH key,
proxy secrets or access to live VMs. Package/provider downloads need HTTPS access
to GitHub, PyPI and HashiCorp; runtime image pulls additionally need GHCR and
Docker's registries. Preserve any environment-provided proxy and CA settings.

Use `gh auth status` to check GitHub access. If authentication is absent, use your
approved GitHub connection or `gh auth login` on an interactive workstation.
Repository access and workflow dispatch require corresponding repository/Actions
permissions. GitHub authentication does not provide local AWS or SSH credentials.

Prefer GitHub Actions for deployment: credentials already stored in GitHub
repository/environments stay there. Check workflow definitions for the exact
secret names and selected environment before dispatch. Do not extract or print
secret values, commit private keys, client configuration, tfvars secrets or state,
or upload unfiltered deployment logs/credential summaries.

Direct Terraform operations additionally require the configured AWS profile,
S3 backend access, matching workspace/tfvars and SSH public key. Direct Ansible
execution requires the target inventory, SSH private key/user/port and sudo
access. Neither is required to begin development.

## Proxy checks (from repository root)

Run `python3 scripts/tests/test_native.py`, `python3 scripts/tests/test_runtime.py`,
`python3 scripts/tests/test_journal_storage.py`,
`python3 scripts/tests/test_client_requests.py` and
`python3 scripts/tests/test_runtime_config.py` (the latter downloads reviewed
archives to temporary controller directories). Repeat the syntax check below with
`-e xray_deployment_mode=docker` as well as the default native selection.

```bash
XRAY_UUID=00000000-0000-0000-0000-000000000000 \
XRAY_SHORT_IDS=deadbeefcafebabe \
XRAY_PRIVATE_KEY=FAKE_PRIVATE_KEY \
XRAY_PUBLIC_KEY=FAKE_PUBLIC_KEY \
ansible-playbook -i ansible/inventory.yml ansible/site.yml --syntax-check
git diff --check
```

Dummy values are only for syntax checking. This command does not connect to hosts
or apply configuration. The deployment workflow currently uses Python 3.11 and
`ansible-core==2.16.19`; the PR syntax workflow also uses Python 3.11 and Ansible 2.16.19. The local Python 3.12 / Ansible 2.16.19 combination above is tested, but
both workflows pin the same Ansible core version.

The selected deployment environment supplies `HOST_SSH_PRIVATE_KEY`, `XRAY_UUID`,
`XRAY_SHORT_IDS`, `XRAY_PRIVATE_KEY`, `XRAY_PUBLIC_KEY`, and optionally SSH public
key/SNI settings. Supply host address/user/port using the workflow's inputs and
variables; review `.github/workflows/deploy.yml` and [secrets guide](secrets-management.md).
The managed host must be Ubuntu with Python 3 and active `kho=off`; the playbook
verifies the host maintenance policy and deploys the selected pinned runtime.
No Ansible installation on the managed VM is needed for runner-controlled deployment.

Validation of a live proxy requires matching client UUID, Reality public key,
short ID and SNI, plus an actual VLESS/Reality HTTPS request through sing-box;
a listening TCP port alone is insufficient. The native validation workflow requires an explicitly selected target and expected
IP. It tests both supplied client transport profiles using runner-side clients.
Runner success does not establish connectivity from a China Unicom client.
Read [disposable VM strategy](disposable-proxy-vms.md) before live tests.

See [runtime validation and current nodes](selectable-runtime-validation.md) for
Cream replacement acceptance, historical spare evidence and cleanup scope.

CI also runs `python3 scripts/tests/test_docker_config.py` with controller Docker.
It tests the pinned image user and rejection/acceptance of restricted config permissions
using generated in-memory keys and ephemeral containers without published ports.

## Podman development

See [Podman runtime](podman-xray.md). Use feature/podman-runtime for this change.
Run `python3 scripts/tests/test_podman.py` in the proxy repository and repeat the
Ansible syntax check with `-e xray_deployment_mode=podman`. The proxy CI matrix
covers all three modes. The affected image test `scripts/tests/test_podman_config.py`
requires controller-side sudo/rootful Podman and checks both reviewed versions.
On Ubuntu 24.04 install Podman, netavark and aardvark-dns; no Compose provider or
Docker compatibility package is needed. The live harness `scripts/podman-validation.py`
refuses targets other than flatwhite. Credentials remain in Actions.
