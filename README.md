# Less Vision Reality Automation

This repository contains Ansible playbooks and supporting GitHub Actions workflows for deploying and operating an Xray Vision/Reality stack with Docker Compose.

## Features
- Automated Ansible playbook (`ansible/site.yml`) that renders Xray configuration and applies Docker Compose updates.
- Continuous integration workflow that validates Ansible syntax for pull requests.
- Credentials workflow that can be triggered manually or automatically during pull requests to produce fresh UUID, short IDs, and Xray Reality key pairs for operators.

## Generating Reality Credentials
Use the **Generate Xray Credentials (manual)** workflow whenever you need disposable identifiers for a new deployment:

1. Navigate to **Actions → Generate Xray Credentials (manual)** in GitHub.
2. Press **Run workflow**, provide a short description in the **Run label** input (this text appears in the workflow run title and job name), and confirm.
3. Open the workflow run and expand the single job.
4. Copy the values from the step summary or grouped log output.
5. Store the UUID, short IDs, and key pair securely (for example in your inventory variables or secrets manager).

Behind the scenes the workflow pulls lightweight Alpine utility containers for each credential component: an Alpine image installs `util-linux` for `uuidgen`, another Alpine run installs `openssl` to emit three short IDs, and the official `ghcr.io/xtls/xray-core:25.10.15` image supplies the `xray x25519` CLI. Because that container is distroless, the shared action invokes it through `docker run` from the runner host, then normalizes the CLI output—treating either `Public key` or the newer `Password` label as the Reality public key—before surfacing `XRAY_PUBLIC_KEY` in the summary. The same core steps execute automatically for pull requests via the **Generate Xray Credentials (PR check)** workflow so credential generation errors are caught during review. No artifacts are saved; outputs only appear in the job log and step summary for easy copy/paste.

## Ansible Usage
1. Review or edit default variables in `ansible/group_vars/all.yml`.
2. Update `ansible/inventory.yml` with your target hosts and overrides.
3. Run `ansible-playbook -i ansible/inventory.yml ansible/site.yml` to apply the configuration.

Ensure the UUID, short IDs, and Reality keys you obtained from the credentials workflow are provided through inventory variables, vaulted secrets, or environment overrides before running the playbook. If you omit the optional Reality SNI value, the playbook now selects a random decoy from the predefined candidate list.

## Repository Structure
- `ansible/` – Playbooks, inventory, variable definitions, and templates for the Xray deployment.
- `.github/workflows/` – CI/CD automation including syntax checks and credential generation.
- `specs.md` – Project specifications and documentation expectations.
