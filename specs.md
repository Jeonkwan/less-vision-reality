# Project Specifications

## Functional Requirements
- Provide infrastructure automation via Ansible playbooks to deploy the service and manage dependencies.
- Supply containerized runtime environments using Docker for local development, testing, and production deployments.
- Automate CI/CD workflows through GitHub Actions, including linting, testing, and deployment steps.
- Support secure configuration through externally supplied identifiers and keys (UUID, shortIds, Xray keys) and optional decoy SNI handling.

## Non-Functional Requirements
- Maintain secure handling of secrets and environment variables throughout automation workflows.
- Ensure documentation remains synchronized with implementation changes to facilitate onboarding and compliance.
- Design for portability between local development, CI, and production environments by standardizing tooling.
- Optimize for maintainability through modular directory organization and reusable infrastructure code.

## Planned Architecture
- **Automation Layer:** Ansible playbooks in `ansible/` orchestrate provisioning, configuration, and runtime setup, consuming inventory variables that include UUIDs, shortIds, Xray keys, and decoy SNI values.
- **Containerization Layer:** Dockerfiles and compose definitions in `docker/` build and run application services, referencing the same variable inputs via environment files or secrets management.
- **Application Layer:** Core application code resides under `src/`, structured into domain-specific modules with shared utilities in `src/common/` and configuration in `src/config/`.
- **Observability & Security:** Monitoring and logging configuration housed in `ops/` integrates with the automation layer, ensuring secure propagation of sensitive identifiers.
- **CI/CD Pipeline:** GitHub Actions workflows in `.github/workflows/` trigger automated tests, security scans, and deployments, relying on repository secrets for UUID, shortIds, Xray keys, and decoy SNI when required.

## Intended Directory Tree
```
/
├── ansible/
│   ├── inventories/
│   ├── playbooks/
│   └── roles/
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── src/
│   ├── common/
│   ├── config/
│   └── services/
├── ops/
│   ├── logging/
│   └── monitoring/
├── docs/
│   └── architecture/
├── .github/
│   └── workflows/
├── tests/
├── README.md
└── specs.md
```

## Variable Inputs and Consumption
- **UUID:** Unique identifier for deployed instances. Defined within Ansible inventory variables (`ansible/inventories/group_vars/*.yml`), passed through Docker runtime environment variables, and stored as an encrypted secret (`UUID`) for GitHub Actions workflows.
- **shortIds:** Short-form identifiers used for service discovery or lightweight tagging. Managed alongside UUIDs in Ansible inventories, surfaced as Docker environment variables, and injected into GitHub Actions via repository secrets (`SHORT_IDS`).
- **Xray Keys:** Credentials or API keys required by observability tooling. Secured in Ansible vault files, mounted into Docker containers as secrets, and referenced by GitHub Actions using encrypted secrets (`XRAY_KEYS`).
- **Decoy SNI (optional, defaults to `www.bing.com`):** Configurable Server Name Indication used for obfuscation. Defaults are maintained in Ansible group variables, with overrides permitted via extra vars. Docker services consume this value through environment files, while GitHub Actions reference a secret (`DECOY_SNI`) when an override is needed; otherwise they rely on the default.

## Living Document Guidance
- Treat `specs.md` as a living document: every change to architecture, requirements, variable inputs, or directory layout must include corresponding updates to this file within the same change set.
- Code reviewers should verify that modifications affecting infrastructure, automation, or application structure are reflected here to maintain accuracy over time.
- Automated checks should be considered to ensure `specs.md` stays synchronized with implementation changes.
