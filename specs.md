# Project Specifications

## Functional Requirements
- Provide infrastructure automation via Ansible for deploying the Xray Vision/Reality service with Docker Compose.
- Support templating of Xray server configuration and Docker Compose manifests from operator-supplied variables.
- Expose lifecycle controls (stop, reload, recreate) through tagged Ansible tasks.
- Document configuration inputs so operators can supply secrets through inventories, extra vars, or environment overrides.

## Non-Functional Requirements
- Maintain secure handling of secrets and environment variables throughout automation workflows.
- Ensure playbooks are idempotent by regenerating configuration and reapplying Docker Compose only when templates change.
- Keep documentation synchronized with implemented automation to facilitate onboarding and review.
- Provide automated pull request checks that run Ansible syntax validation to guard against breaking playbook changes.

## Current Architecture
- **Automation Layer:** `ansible/site.yml` orchestrates validation, configuration rendering, Docker Compose generation, and service application. Templates live in `ansible/templates/`. Shared variables are demonstrated in `ansible/group_vars/all.yml`.
- **Containerization Layer:** Runtime defined dynamically through `ansible/templates/docker-compose.yml.j2`, leveraging the public `ghcr.io/xtls/xray-core:latest` image and mounting generated configuration.
- **Configuration Inputs:** UUID, short IDs, Reality keys, and optional SNI values are surfaced as Ansible variables with environment overrides documented in `ansible/group_vars/all.yml`.
- **Continuous Integration:** `.github/workflows/pr-check.yml` executes `ansible-playbook --syntax-check` during pull request validation using representative environment variables. Dedicated credential workflows (`.github/workflows/generate-credentials-manual.yml` and `.github/workflows/generate-credentials-pr.yml`) provide disposable UUIDs, short IDs, and Reality key pairs whether triggered manually or during pull requests.

## Directory Overview
```
/
├── ansible/
│   ├── group_vars/
│   │   └── all.yml
│   ├── inventory.yml
│   ├── site.yml
│   └── templates/
│       ├── config.json.j2
│       └── docker-compose.yml.j2
├── README.md
└── specs.md
```

## Variable Inputs and Consumption
- **xray_uuid:** Primary UUID for the Vision/Reality client. Operators override via inventory, vault, `--extra-vars`, or the `XRAY_UUID` environment variable when invoking Ansible.
- **xray_short_ids:** Short identifiers for Reality. Accepts a YAML list and can be overridden through the `XRAY_SHORT_IDS` environment variable (comma separated) or explicit vars.
- **xray_reality_private_key / xray_reality_public_key:** Reality key pair expected from secure storage. Example fallbacks are placeholders; operators must supply real values via vault or environment variables (`XRAY_PRIVATE_KEY`, `XRAY_PUBLIC_KEY`).
- **xray_sni:** Optional decoy SNI, defaulting to `www.bing.com` when empty.
- **xray_container_image / ports / restart policy:** Infrastructure defaults that can be tuned per inventory to match deployment needs.

## Operational Flow
1. Validate required secrets/IDs are provided and ensure `docker compose` CLI is installed.
2. Compute the effective SNI and create directories for configuration and compose artifacts under `xray_service_root`.
3. Render `config.json` and `docker-compose.yml` from templates using supplied variables.
4. Apply Docker Compose (`docker compose up -d --remove-orphans`) via handler when templates change. Optional tagged tasks allow manual `down`, `up`, or `force recreate` operations.

## Documentation Expectations
- Changes to automation or variable definitions must update this specification and any operator-facing documentation in `ansible/`.

## Credential Generation Workflow
- Triggered manually via the **Generate Xray Credentials (manual)** workflow or automatically for pull requests via **Generate Xray Credentials (PR check)**.
- Uses dedicated utility containers to isolate each step: Alpine-based runs install `util-linux` for `uuidgen`, separate Alpine runs install `openssl` to generate short IDs, and the shell-capable `docker.io/teddysun/xray:latest` image produces the Reality key pairs.
- Emits values only to the job log and step summary so operators can copy/paste secrets without persisting artifacts.
- Operators must securely store the emitted UUID, short IDs, and keys before running Ansible.
