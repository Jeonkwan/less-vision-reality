# Secrets Management Guide

Expanding on the security expectations in [`specs.md`](../specs.md), this guide describes how to provision, rotate, and consume secrets required by the Vision/Reality automation.

## Required Secrets

The automation requires the following sensitive inputs:

- **`xray_uuid`** – The primary client UUID. Generated via workflow outputs or internal tooling.
- **`xray_short_ids`** – YAML list of short identifiers for the Reality transport.
- **`xray_reality_private_key` / `xray_reality_public_key`** – Key pair used by the Reality server.
- **Optional overrides** such as `xray_sni`, custom container images, or additional ports that may contain sensitive metadata.

## Storage Recommendations

- **Ansible Vault:** Encrypt group or host variable files (`ansible/group_vars/*.yml`) using `ansible-vault encrypt`.
- **Environment variables:** Export secrets at runtime (e.g., `XRAY_UUID`, `XRAY_PRIVATE_KEY`) when invoking `ansible-playbook`. Combine with CI secrets for GitHub Actions.
- **External secret managers:** Integrate HashiCorp Vault, AWS Secrets Manager, or organizational equivalents by fetching values in a pre-task and registering them as Ansible facts.

## Provisioning Workflow

1. Run the **Generate Xray Credentials** workflows to produce UUIDs, short IDs, and key pairs. When GitHub Actions is not availa
   ble, execute `./scripts/generate_xray_credentials.sh` locally to obtain the same values via disposable Docker containers.
2. Copy the outputs immediately; they are not stored persistently. Redirect the script output to an `.env` file only long enough
   to paste the values into Vault-encrypted YAML.
3. Update encrypted inventory files or CI secrets to include the new values.
4. Commit only the encrypted vault files—never plaintext secrets.

## Rotation Strategy

- Schedule credential regeneration at regular intervals or after suspected compromise.
- Automate vault editing with `ansible-vault edit` to prevent temporary plaintext files.
- After rotation, execute the playbook to apply updated templates and ensure handlers recreate containers as needed.

## Auditing and Compliance

- Maintain a changelog of vault password rotations and inventory updates.
- Use GitHub Actions audit logs to track who triggered credential generation workflows.
- Compare current configurations against inspirations (`Jeonkwan/less-vision`, `myelectronix/xtls-reality-docker`) to document rationale for security-related deviations.

## Incident Response

- Revoke compromised credentials immediately by updating vault files and redeploying.
- Inspect Docker logs and host-level metrics for anomalies.
- Document incident timelines within this guide or auxiliary runbooks to keep `specs.md` aligned with operational history.
