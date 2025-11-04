# Ansible Automation for less-vision-reality

This playbook deploys the Xray Vision/Reality service with Docker Compose while following the lightweight container style used in `Jeonkwan/less-vision`.

The runtime defaults to the official `ghcr.io/xtls/xray-core:25.10.15` image.
Configuration rendered under `/opt/xray/config` is mounted into
`/usr/local/etc/xray` inside the container to align with the image entrypoint.
When upgrading to a newer release, bump the tag in `group_vars/all.yml` and
verify the updated container still accepts the configuration layout described
here.

## Files
- `inventory.yml` – sample inventory with placeholder host information.
- `group_vars/all.yml` – documented defaults and examples for required variables (UUID, short IDs, keys, SNI).
- `templates/config.json.j2` – Xray configuration rendered per host.
- `templates/docker-compose.yml.j2` – Docker Compose definition generated on the fly.
- `site.yml` – single playbook that validates input, renders configuration, and applies Docker Compose.

## Usage
1. Copy `inventory.yml` and replace `REPLACE_ME_WITH_TARGET` with the remote host or IP. Update SSH connection variables as needed.
2. Provide required secrets through Ansible Vault, inventory overrides, or environment variables:
   ```bash
   export XRAY_UUID="$(uuidgen)"
   export XRAY_SHORT_IDS="a1b2c3d4,e5f6g7h8"
   export XRAY_PRIVATE_KEY="<private-key>"
   export XRAY_PUBLIC_KEY="<public-key>"
   ansible-playbook -i inventory.yml site.yml
   ```
   Before rendering new configuration the playbook force-removes any existing
   Xray container that matches `xray_service_name`, pauses for 30 seconds,
   verifies the replacement is running, and prints the last 100 log lines
   before failing when Docker reports a restart loop. You can re-run syntax
   validation from the
   host with:

   ```bash
   docker compose -f /opt/xray/docker-compose.yml exec xray \
     xray -test -confdir /usr/local/etc/xray
   ```
3. To stop, reload, or recreate the deployment run the playbook with the appropriate tag:
   - `ansible-playbook -i inventory.yml site.yml -t xray_down`
   - `ansible-playbook -i inventory.yml site.yml -t xray_reload`
   - `ansible-playbook -i inventory.yml site.yml -t xray_recreate`

The playbook regenerates configuration and re-applies `docker compose up -d --remove-orphans` whenever templates change, ensuring idempotent runs.

## Continuous Integration

A GitHub Action (`.github/workflows/pr-check.yml`) runs `ansible-playbook --syntax-check` with representative environment values on every pull request so changes to the playbook or templates are validated automatically. Two companion workflows (`.github/workflows/generate-credentials-manual.yml` and `.github/workflows/generate-credentials-pr.yml`) reuse the same credential generation routine: the manual entry prompts operators for a descriptive run label, while the PR check automatically labels the run with the pull request number. The shared action orchestrates dedicated Alpine utility containers for UUIDs, OpenSSL short IDs, and the official `ghcr.io/xtls/xray-core:25.10.15` image for the key pair—normalizing both the legacy `Public key` and newer `Password` fields into the published Reality public key—to keep responsibilities isolated.

## GitHub Deployment Workflow

The deployment workflow (`.github/workflows/deploy.yml`) provides a turnkey path for applying `site.yml` from GitHub-hosted runners. Configure the GitHub environment that represents your stage (for example, `production`) with the same secrets you would export locally:

| Secret | Injected environment variable | Playbook variable |
| ------ | ----------------------------- | ----------------- |
| `XRAY_UUID` | `XRAY_UUID` | `xray_uuid` |
| `XRAY_SHORT_IDS` | `XRAY_SHORT_IDS` | `xray_short_ids` (comma-separated list) |
| `XRAY_PRIVATE_KEY` | `XRAY_PRIVATE_KEY` | `xray_reality_private_key` |
| `XRAY_PUBLIC_KEY` | `XRAY_PUBLIC_KEY` | `xray_reality_public_key` |
| `HOST_SSH_PRIVATE_KEY` *(optional)* | `HOST_SSH_PRIVATE_KEY` | SSH key written to `~/.ssh/id_ed25519` on the runner |
| `HOST_SSH_PUBLIC_KEY` *(optional)* | `HOST_SSH_PUBLIC_KEY` | Saved to `~/.ssh/id_ed25519.pub` when provided |

You can also define a non-secret repository or environment variable named `XRAY_DECOY_SNI` to force a specific fallback SNI. When both `XRAY_SNI` and `XRAY_DECOY_SNI` are absent or empty, the deployment defaults the TLS Server Name Indication to `web.wechat.com`.

The workflow collects host connection details from a mix of workflow inputs and environment variables so you can manage server metadata without editing the committed inventory:

| Input / variable | Purpose | Default |
| ---------------- | ------- | ------- |
| `remote_server_ip_address` (workflow input) | Primary connection address for the target host | *(required)* |
| `remote_server_user` (workflow input or `REMOTE_SERVER_USER` environment variable) | SSH user used by Ansible | *(optional)* |
| `REMOTE_SERVER_PORT` (environment variable) | SSH port for the host | `22` |

Reality credentials can also be overridden per run via the `xray_uuid`, `xray_short_ids`, `xray_private_key`, and `xray_public_key` workflow inputs; blanks fall back to the GitHub environment secrets. Manual runs require the operator to pick the GitHub environment from the workflow input before any secrets are loaded, and a validation job confirms the environment exists via the GitHub API. You can optionally provide an Ansible limit pattern to target a subset of hosts during the same run.

Successful workflow runs now surface client connection guidance directly in the logs. The final step prints VLESS URIs for Shadowrocket and Clash Meta, a Clash Verge YAML snippet, and ANSI QR codes so you can onboard devices without logging into the target host. Provide the intended domain via `XRAY_SNI` (or define `xray_domain` on the host in `inventory.yml`) to override the default TLS decoy of `web.wechat.com`; when it is omitted, the workflow still uses your configured remote server IP (when available) as the connection endpoint.
