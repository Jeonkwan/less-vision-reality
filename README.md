# Less Vision Reality Automation

For agents and contributors: start with [development environment and dependencies](docs/development.md) and [AGENTS.md](AGENTS.md).

This repository contains Ansible playbooks and GitHub Actions workflows for deploying an official Xray VLESS/REALITY binary under systemd. Ansible and release downloads run on the controller; the server runs only Xray and the basic Ubuntu host services. See [`specs.md`](specs.md) for project requirements.

## Documentation Suite

- [Setup Guide](docs/setup.md) – Infrastructure prerequisites, local environment preparation, and repository relationships.
- [Operations Guide](docs/operations.md) – Inventory management patterns, Ansible execution flows, GitHub Action usage, and maintenance runbooks.
- [Secrets Management Guide](docs/secrets-management.md) – Secure handling, rotation, and auditing guidance for all required credentials.

Refer back to [`specs.md`](specs.md) for the authoritative project goals and keep the documentation synchronized with ongoing automation changes.

## Features
- Automated Ansible playbook (`ansible/site.yml`) that validates and installs native Xray with bounded journald logs.
- Continuous integration workflow that validates Ansible syntax for pull requests.
- Credentials workflow that can be triggered manually or automatically during pull requests to produce fresh UUID, short IDs, and Xray Reality key pairs for operators.
- Deployment workflow that installs Ansible on a runner, hydrates sensitive variables from repository or environment secrets, and executes the playbook against the configured inventory.

## Generating Reality Credentials
Use the **Generate Xray Credentials (manual)** workflow whenever you need disposable identifiers for a new deployment. When GitHub Actions access is unavailable, run `./scripts/generate_xray_credentials.sh` locally. That optional credential generator uses throwaway Docker containers on the controller; Docker is not required on the proxy server:

```bash
SHORT_ID_COUNT=5 ./scripts/generate_xray_credentials.sh > credentials.env
```

The script prints the UUID, comma-separated short IDs, and Reality key pair. Store these securely, then delete the temporary file.

Trigger the GitHub workflow with:

1. Navigate to **Actions → Generate Xray Credentials (manual)** in GitHub.
2. Press **Run workflow**, provide a short description in the **Run label** input (this text appears in the workflow run title and job name), and confirm.
3. Open the workflow run and expand the single job.
4. Copy the values from the step summary or grouped log output.
5. Store the UUID, short IDs, and key pair securely (for example in your inventory variables or secrets manager).

Behind the scenes the workflow pulls lightweight Alpine utility containers for each credential component: an Alpine image installs `util-linux` for `uuidgen`, another Alpine run installs `openssl` to emit three short IDs, and the official `ghcr.io/xtls/xray-core:25.10.15` image supplies the `xray x25519` CLI. Because that container is distroless, the shared action invokes it through `docker run` from the runner host, then normalizes the CLI output—treating either `Public key` or the newer `Password` label as the Reality public key—before surfacing `XRAY_PUBLIC_KEY` in the summary. The same core steps execute automatically for pull requests via the **Generate Xray Credentials (PR check)** workflow so credential generation errors are caught during review. No artifacts are saved; outputs only appear in the job log and step summary for easy copy/paste.

## Ansible Usage
1. Review or edit default variables in `ansible/group_vars/all.yml`.
2. Update `ansible/inventory.yml` with your target hosts and overrides.
3. Prepare a reviewed release on the controller, then supply the verified artifact to Ansible:

```bash
python3 scripts/prepare-native.py --version 26.3.27 --directory /tmp/xray-release
export XRAY_BINARY_PATH=/tmp/xray-release/xray
export XRAY_BINARY_SHA256=$(sha256sum "$XRAY_BINARY_PATH" | cut -d' ' -f1)
ansible-playbook -i ansible/inventory.yml ansible/site.yml
```

The default is reviewed stable Xray 26.3.27, with 25.10.15 retained for rollback.
The playbook validates the candidate binary/configuration before activation,
preserves an unchanged running service, and waits up to 30 seconds for the listener
without a fixed sleep. You can validate the installed configuration on the server:

```bash
sudo /usr/local/bin/xray run -format json -test \
  -config /usr/local/etc/xray/config.json
```

Ensure the UUID, short IDs, and Reality keys you obtained from the credentials workflow are provided through inventory variables, vaulted secrets, or environment overrides before running the playbook. If you omit the optional Reality SNI value, the playbook now selects a random decoy from the predefined candidate list.

## Deploying from GitHub Actions

The **Deploy Xray Stack** workflow (`.github/workflows/deploy.yml`) applies the same playbook directly from GitHub. It runs only when triggered manually so operators can explicitly choose the target environment before any secrets are loaded. To deploy:

1. Populate the following secrets on the target GitHub environment (for example, `production`). Each secret maps 1:1 with the playbook variables documented in `ansible/group_vars/all.yml`.

   | Secret name | Purpose | Playbook variable |
   | ----------- | ------- | ----------------- |
   | `XRAY_UUID` | Core Xray client identifier | `xray_uuid`
   | `XRAY_SHORT_IDS` | Comma-separated list of short IDs (e.g., `a1b2c3d4,e5f6g7h8`) | `xray_short_ids`
   | `XRAY_PRIVATE_KEY` | Reality private key | `xray_reality_private_key`
   | `XRAY_PUBLIC_KEY` | Reality public key | `xray_reality_public_key`
   | `HOST_SSH_PRIVATE_KEY` *(optional)* | SSH key used by Ansible to reach the remote hosts | SSH configuration written to the runner at runtime |
   | `HOST_SSH_PUBLIC_KEY` *(optional)* | Public half of the SSH key (useful when debugging host access) | Saved to `~/.ssh/id_ed25519.pub` when provided |

   Secrets are masked automatically during the run, and the workflow adds explicit `::add-mask::` directives to ensure short IDs and keys never leak into logs.

2. Provide the remote host connection details when you start the workflow:

   | Input / variable | Purpose | Default |
   | ---------------- | ------- | ------- |
   | `remote_server_ip_address` (workflow input) | Primary connection address for the target host | *(required)* |
   | `remote_server_user` (workflow input or `REMOTE_SERVER_USER` environment variable) | SSH user used to run the playbook | *(optional)* |
   | `REMOTE_SERVER_PORT` (environment variable) | SSH port for the host | `22` |

   The IP address must be supplied as a workflow input. When the SSH user input is left blank the workflow falls back to the GitHub environment variable of the same name; if both are missing it reuses `ansible/inventory.yml` instead of generating an inline inventory file.

3. (Optional) Override the Reality credentials per run by populating the `xray_uuid`, `xray_short_ids`, `xray_private_key`, and `xray_public_key` workflow inputs. Blank inputs automatically fall back to the environment secrets configured in step 1.

4. (Optional) Define a repository or environment variable named `XRAY_DECOY_SNI` when you want to force a specific fallback SNI. If the variable is blank or missing, the playbook falls back to its internal decoy list.

5. Navigate to **Actions → Deploy Xray Stack** and choose **Run workflow**. Select the GitHub environment from the required input dropdown and, if necessary, provide an Ansible `limit` pattern to scope the run to a subset of hosts.

6. The workflow validates that the requested environment exists before proceeding, installs Ansible, masks all secrets, configures SSH if a key is present, and then calls `ansible-playbook` with the runtime inventory path (either the generated file or the repository default). Any failures surface directly in the job log.

7. The workflow downloads and verifies the selected `xray_version` on the runner. The playbook validates the candidate configuration, installs Xray under systemd, and preserves an unchanged running process. Logs are available through `journalctl -u xray` with host-wide retention limits.

8. On successful runs the workflow prints ready-to-use client connection details—including VLESS URIs, QR codes, and a Clash configuration snippet—so operators can distribute credentials without shelling into the remote host. Provide `XRAY_SNI` (or an inventory `xray_domain` override) to ensure the summary reflects the production domain instead of the placeholder.

## Repository Structure
- `ansible/` – Playbooks, inventory, variable definitions, and templates for the Xray deployment.
- `.github/workflows/` – CI/CD automation including syntax checks and credential generation.
- `specs.md` – Project specifications and documentation expectations.

See [disposable proxy VM strategy](docs/disposable-proxy-vms.md) for replacement-based updates, boot readiness and validation.

## Native Xray feature

`feature/native-xray` builds on `feature/bounded-logs`. Native runtime installation
uses runner-verified official release binaries and systemd, with persistent bounded
journald logs. See [native deployment](docs/native-xray.md). Existing container roles
are legacy code and are not invoked by the native playbook.
