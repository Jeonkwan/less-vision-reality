# Ansible Automation for less-vision-reality

This playbook deploys the Xray Vision/Reality service with Docker Compose while following the lightweight container style used in `Jeonkwan/less-vision`.

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
3. To stop, reload, or recreate the deployment run the playbook with the appropriate tag:
   - `ansible-playbook -i inventory.yml site.yml -t xray_down`
   - `ansible-playbook -i inventory.yml site.yml -t xray_reload`
   - `ansible-playbook -i inventory.yml site.yml -t xray_recreate`

The playbook regenerates configuration and re-applies `docker compose up -d --remove-orphans` whenever templates change, ensuring idempotent runs.

## Continuous Integration

A GitHub Action (`.github/workflows/pr-check.yml`) runs `ansible-playbook --syntax-check` with representative environment values on every pull request so changes to the playbook or templates are validated automatically. Two companion workflows (`.github/workflows/generate-credentials-manual.yml` and `.github/workflows/generate-credentials-pr.yml`) reuse the same credential generation routine: the manual entry prompts operators for a descriptive run label, while the PR check automatically labels the run with the pull request number. The shared action orchestrates dedicated Alpine utility containers for UUIDs, OpenSSL short IDs, and the official `ghcr.io/xtls/xray-core:25.10.15` image for the key pair—normalizing both the legacy `Public key` and newer `Password` fields into the published Reality public key—to keep responsibilities isolated.
