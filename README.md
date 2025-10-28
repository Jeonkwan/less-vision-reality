# Less Vision Reality Automation

This repository contains Ansible playbooks and supporting GitHub Actions workflows for deploying and operating an Xray Vision/Reality stack with Docker Compose.

## Features
- Automated Ansible playbook (`ansible/site.yml`) that renders Xray configuration and applies Docker Compose updates.
- Continuous integration workflow that validates Ansible syntax for pull requests.
- Manually triggered credentials workflow that produces fresh UUID, short IDs, and Xray Reality key pairs for operators.

## Generating Reality Credentials
Use the **Generate Xray Credentials** workflow whenever you need disposable identifiers for a new deployment:

1. Navigate to **Actions → Generate Xray Credentials** in GitHub.
2. Press **Run workflow**, leave the inputs empty, and confirm.
3. Open the workflow run and expand the single job.
4. Copy the values from the step summary or grouped log output.
5. Store the UUID, short IDs, and key pair securely (for example in your inventory variables or secrets manager).

The workflow uses the official `ghcr.io/xtls/xray-core` container image to execute `xray` CLI helpers. No artifacts are saved; outputs only appear in the job log and step summary for easy copy/paste.

## Ansible Usage
1. Review or edit default variables in `ansible/group_vars/all.yml`.
2. Update `ansible/inventory.yml` with your target hosts and overrides.
3. Run `ansible-playbook -i ansible/inventory.yml ansible/site.yml` to apply the configuration.

Ensure the UUID, short IDs, and Reality keys you obtained from the credentials workflow are provided through inventory variables, vaulted secrets, or environment overrides before running the playbook. If you omit the optional Reality SNI value, the playbook now selects a random decoy from the predefined candidate list.

## Repository Structure
- `ansible/` – Playbooks, inventory, variable definitions, and templates for the Xray deployment.
- `.github/workflows/` – CI/CD automation including syntax checks and credential generation.
- `specs.md` – Project specifications and documentation expectations.
