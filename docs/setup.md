# Setup Guide

This guide expands on the high-level expectations in [`specs.md`](../specs.md) to describe the infrastructure prerequisites and local environment preparation necessary before executing the Ansible automation.

## Infrastructure Prerequisites

- **Control host requirements:** An operator workstation or CI runner with Docker Engine 24+, Docker Compose v2, Ansible 2.16+, and access to the target infrastructure over SSH.
- **Managed hosts:** Linux hosts capable of running Docker containers, with outbound connectivity to pull `ghcr.io/xtls/xray-core:25.10.15` and any auxiliary images. Ensure firewall rules allow the service ports defined in your inventory (`xray_service_ports`).
- **Credential storage:** Provide a secure secret manager (such as Ansible Vault or your organization's secret platform) to persist the UUID, short IDs, and Reality key pairs referenced in [`ansible/group_vars/all.yml`](../ansible/group_vars/all.yml).

## Repository Relationships

The automation draws inspiration from, but deliberately diverges from, two public projects:

- [`Jeonkwan/less-vision`](https://github.com/Jeonkwan/less-vision) – Source of the overall service topology and baseline configuration ideas. The current repository replaces shell scripts with structured Ansible playbooks, introduces templated Docker Compose manifests, and documents CI-driven credential generation.
- [`myelectronix/xtls-reality-docker`](https://github.com/myelectronix/xtls-reality-docker) – Demonstrates containerized Reality deployments. This project adapts those patterns while emphasizing idempotent Ansible roles, inventory-driven overrides, and GitHub Actions automation.

## Local Environment Preparation

1. Clone this repository and install the Python requirements for Ansible (e.g., `pip install ansible`).
2. Authenticate with any private registries or GitHub Container Registry if credentials are required to pull images.
3. Populate a working inventory (see [Inventory Management](operations.md#inventory-management)) with host definitions and required variables.
4. Export or configure secrets using environment variables or Ansible Vault (see [Secrets Management](secrets-management.md)).
5. Run `ansible-galaxy collection install -r requirements.yml` if additional collections are declared.

## Validation Checklist

Before running the playbook:

- [ ] Managed hosts resolve DNS names for upstream registries.
- [ ] SSH connectivity is verified (`ansible all -m ping`).
- [ ] Required ports are free on the target hosts.
- [ ] Secrets have been securely provisioned.
- [ ] GitHub Actions workflows are configured with necessary repository secrets.
