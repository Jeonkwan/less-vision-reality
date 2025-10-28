# Operations Guide

This document supplements [`specs.md`](../specs.md) by detailing how to manage inventories, execute the Ansible playbook, integrate with GitHub Actions, and perform ongoing maintenance for the Vision/Reality deployment.

## Inventory Management

- Start from `ansible/inventory.yml` as a template. Define hosts under the appropriate groups (e.g., `vision_reality`) and assign variables either inline or via `group_vars` files.
- Store sensitive values (UUID, Reality keys, short IDs) in Ansible Vault encrypted files or reference environment variables as described in [Secrets Management](secrets-management.md).
- Use host variables for per-node overrides such as `xray_service_ports`, `xray_container_image`, or filesystem paths. Leverage group-level defaults for shared settings to preserve idempotency.

### Example Inventory Snippet

```yaml
all:
  children:
    vision_reality:
      hosts:
        edge-01:
          ansible_host: 203.0.113.10
          xray_service_ports:
            - "443:443"
```

## Executing the Ansible Automation

### Manual credential generation (no GitHub Actions)

Operators who cannot trigger the repository workflows can still generate the required UUID, short IDs, and Reality key pair locally as long as Docker is available:

1. Ensure Docker is installed and the daemon is running on the workstation.
2. From the repository root, run the wrapper script which orchestrates the necessary containers: `./scripts/generate_xray_credentials.sh > credentials.env`.
   - Set `SHORT_ID_COUNT=<n>` before the command if you need more or fewer than three short IDs.
   - Inspect `credentials.env`, copy the values to your password manager, and remove the file once the secrets are vaulted.
3. Apply the credentials to your inventories:
   - Option A: encrypt a dedicated variable file with Ansible Vault (`ansible-vault encrypt ansible/group_vars/vision_reality/secrets.yml`) and paste the values in YAML form, e.g.

     ```yaml
     xray_uuid: "<uuid from script>"
     xray_short_ids:
       - "<short id 1>"
       - "<short id 2>"
       - "<short id 3>"
     xray_reality_private_key: "<private key>"
     xray_reality_public_key: "<public key>"
     ```

   - Option B: export them as environment variables immediately before invoking `ansible-playbook` (`export XRAY_UUID=...`).

The script prints human-readable hints while it pulls the minimal Alpine and Xray containers, so Docker remains the only prerequisite on the operator's host.

### Running the playbook from a Dockerized Ansible controller

To run the automation against a remote host without installing Ansible locally, use an Ansible container and mount the repository plus SSH credentials:

1. Save an SSH private key (for example, `~/.ssh/id_ed25519`) that has access to the remote server. Add the host to `~/.ssh/known_hosts` by running `ssh <user>@<host>` once or set `ANSIBLE_HOST_KEY_CHECKING=False` if you prefer to rely on fingerprint prompts during the first run.
2. Update `ansible/inventory.yml` or create a derivative inventory file with the remote host information, e.g.

   ```yaml
   all:
     children:
       vision_reality:
         hosts:
           edge-01:
             ansible_host: 198.51.100.12
             ansible_user: deployer
             ansible_port: 22
   ```

3. Vault the credentials produced by `scripts/generate_xray_credentials.sh` or export them as environment variables in the current shell session.
4. Invoke the playbook from an Ansible container (the example below uses the `quay.io/ansible/ansible-runner:stable-2.15` image, but any image with the `ansible` CLI will work):

   ```bash
   docker run --rm -it \
     -v "$(pwd)":/workspace \
     -w /workspace \
     -v "$HOME/.ssh/id_ed25519":/root/.ssh/id_ed25519:ro \
     -v "$HOME/.ssh/known_hosts":/root/.ssh/known_hosts:ro \
     -e XRAY_UUID -e XRAY_SHORT_IDS -e XRAY_PRIVATE_KEY -e XRAY_PUBLIC_KEY \
     -e ANSIBLE_HOST_KEY_CHECKING=${ANSIBLE_HOST_KEY_CHECKING:-True} \
     quay.io/ansible/ansible-runner:stable-2.15 \
       ansible-playbook -i ansible/inventory.yml ansible/site.yml
   ```

   Replace the inventory path with your custom file if you maintain separate staging and production inventories.
5. Review the container output. The playbook renders the Docker Compose definition, restarts the Xray container when templates change, and surfaces service logs if Docker reports a non-running state.

Use the standard Ansible tags to control lifecycle actions even when running from Docker:

- `--tags docker_down` to stop the service.
- `--tags docker_up` to bring the service back.
- `--tags docker_recreate` to force container recreation after configuration changes.

Monitor output for template changes; handlers will run `docker compose up -d --remove-orphans` when necessary.

## GitHub Actions Workflows

The repository ships with workflows that enforce best practices outlined in [`specs.md`](../specs.md):

- **PR Checks (`.github/workflows/pr-check.yml`):** Executes `ansible-playbook --syntax-check` with representative variables to prevent syntax regressions.
- **Credential Generation (`.github/workflows/generate-credentials-manual.yml` and `.github/workflows/generate-credentials-pr.yml`):** Uses isolated containers to emit UUIDs, short IDs, and Reality key pairs. Store generated values securely immediately after the run.

To adopt these workflows:

1. Configure repository-level secrets for any required environment variables.
2. Optionally fork the workflow definitions into organizational templates if you need centralized governance.
3. Monitor workflow runs to capture generated credentials and to verify syntax checks remain green.

## Maintenance Procedures

- **Template updates:** When updating `ansible/templates/*.j2`, rerun the playbook in a staging environment to confirm handlers apply changes cleanly.
- **Dependency refresh:** Periodically update Docker images and Ansible collections. Document deviations from upstream projects (`Jeonkwan/less-vision`, `myelectronix/xtls-reality-docker`) in commit messages or release notes.
- **Credential rotation:** Use the credential generation workflows to replace keys and UUIDs on a scheduled basis. Update inventories and redeploy with the new secrets.
- **Monitoring:** Integrate host-level monitoring (e.g., Docker metrics, service availability probes) and document alert responses alongside this guide.
- **Documentation sync:** Reflect any operational changes back into this guide and [`specs.md`](../specs.md) to keep onboarding material current.
