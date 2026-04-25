# GCE Image Automation Research for Xray Deployment

## Executive Summary

You asked whether this repository should automate creation of a reusable Google Compute Engine (GCE) image so the same prepared server can be launched repeatedly without manually creating images from an already-configured instance.

Short answer: **yes, but the image should bake only the reusable host setup, not deployment-specific Xray secrets or runtime identity**.

My recommended direction is:

1. **Use Packer with the Google Compute builder** to create the GCE custom image.
2. **Reuse Ansible from this repository** for image provisioning wherever possible.
3. **Keep the existing Xray deployment workflow as a post-boot deployment step** for secrets, final config rendering, and service activation.
4. Treat the image as a **golden base image for Xray-ready hosts**, not as a fully personalized runtime snapshot.

## Important Research Constraint

The repository link provided for `Jeonkwan/gcp-proxy` was not publicly accessible at the time of this research (`404` from both GitHub and raw content endpoints). Because of that, this review is based on:

- the current `less-vision-reality` repository,
- your description of the existing GCP proxy deployment flow,
- current Google Cloud and Packer guidance.

If access to the GCP proxy repository is provided later, this document can be tightened into a direct integration design.

## Current Repository Baseline

This repository already has a strong deployment foundation:

- **GitHub Actions deployment workflow** in `/home/runner/work/less-vision-reality/less-vision-reality/.github/workflows/deploy.yml`
- **Ansible orchestration** in `/home/runner/work/less-vision-reality/less-vision-reality/ansible/site.yml`
- **Host preparation logic** in `/home/runner/work/less-vision-reality/less-vision-reality/ansible/roles/docker_prereqs/tasks/main.yml`
- **Xray deployment logic** in `/home/runner/work/less-vision-reality/less-vision-reality/ansible/roles/xray_common/tasks/main.yml` and `/home/runner/work/less-vision-reality/less-vision-reality/ansible/roles/xray_deploy/tasks/main.yml`

That means you already have most of the configuration logic needed for an image pipeline. The missing piece is an **image build orchestrator**.

## What Should and Should Not Go Into the Image

### Good candidates for baking into the image

- OS updates and baseline packages
- Docker Engine and Docker Compose
- Common filesystem layout such as `/opt/xray`
- Optional pre-pull of the Xray container image
- Optional non-secret operational tooling needed on every host
- Any reusable base setup coming from the GCP proxy flow

### Bad candidates for baking into the image

- `XRAY_UUID`
- Reality private/public keys
- short IDs
- environment-specific SNI/domain values
- per-instance IP-dependent configuration
- any credentials, SSH private keys, or GitHub secrets

If secrets are baked into the image, every instance created from that image will inherit the same identity, which is operationally risky and defeats the current secret-handling design of this repository.

## Approaches Considered

### 1. Keep the current flow and automate `gcloud compute images create` after deployment

### Idea

Reproduce your current manual process:

1. create a temporary GCE instance,
2. run the existing deployment flow,
3. stop the instance or prepare it,
4. create a custom image from its boot disk automatically.

### Strengths

- Lowest change cost
- Very close to what already works manually
- Fastest path to a first automated result

### Weaknesses

- Weak reproducibility
- Easy to accumulate drift from ad hoc host changes
- Harder to review because the image contents come from a live instance state
- More difficult to separate reusable base setup from per-deployment secrets

### Verdict

Good as a **short-term bridge**, but not the best long-term design.

### 2. Packer with shell provisioners

### Idea

Use Packer's Google Compute builder to start a temporary builder VM and run shell scripts that install Docker, prepare directories, and possibly preload the Xray runtime.

### Strengths

- Simple
- Easy to bootstrap quickly
- Good if the source GCP proxy flow is mostly shell-based already

### Weaknesses

- Logic tends to duplicate what this repository already models in Ansible
- Harder to keep idempotent and maintainable over time
- Shell build scripts become harder to reason about as scope grows

### Verdict

Reasonable if you need a very fast first version, but it underuses the strongest asset already present in this repository: **Ansible**.

### 3. Packer with Ansible provisioners

### Idea

Use Packer to create the builder VM and use Ansible during the image build to apply reusable host setup.

This can be done with:

- **Packer + shell + Ansible**: shell installs Python or other prerequisites, then Ansible applies the reusable roles
- **Packer + Ansible only**: if the base image already has everything needed for Ansible connectivity

### Strengths

- Best alignment with the current repository structure
- Reuses existing deployment knowledge and role logic
- Easier to keep reviewable and reproducible
- Easier to split reusable host setup from runtime-secret injection
- Best long-term maintainability

### Weaknesses

- Slightly more setup than a raw shell-based build
- May require refactoring the current Ansible flow so image-safe tasks are separated from runtime deployment tasks

### Verdict

**Best overall option. Recommended.**

### 4. GCE machine images instead of custom images

### Idea

Capture a full machine image from a configured instance instead of building a custom image pipeline.

### Strengths

- Very good for cloning a complete machine state
- Captures more than just the boot disk
- Useful for disaster recovery or exact environment replication

### Weaknesses

- Usually too heavy for CI-style image baking
- Less modular than a clean golden-image pipeline
- Easier to carry forward stale metadata or environment-specific settings
- Poorer fit if you want a reusable, parameterized deployment workflow

### Verdict

Useful if your goal is **full host cloning**, but not the best default for this repository.

### 5. Startup scripts or instance templates only

### Idea

Do not bake much into the image; instead create standard instances and let startup scripts finish the install on boot.

### Strengths

- Low tooling overhead
- Flexible for small instance-specific customization

### Weaknesses

- Slow boot
- More drift risk
- Harder to validate
- Less aligned with your goal of reusing a prepared Xray-ready image

### Verdict

Good only for last-mile customization, not as the primary solution.

## Comparison Summary

| Approach | Effort | Reproducibility | Maintainability | Fit for this repo | Recommended use |
| --- | --- | --- | --- | --- | --- |
| Deploy then create image from source disk | Low | Medium-Low | Medium-Low | Medium | Transitional solution |
| Packer + shell | Medium | High | Medium | Medium | Fast initial automation |
| Packer + Ansible | Medium | High | High | High | **Recommended** |
| Machine image | Low-Medium | Medium | Medium-Low | Medium-Low | Exact cloning use cases |
| Startup scripts only | Low | Low | Low-Medium | Low | Small boot-time customization only |

## Recommended Architecture

### Recommended target state

Use a **two-stage model**:

### Stage 1: Build an Xray-ready GCE image

Built by Packer and containing only reusable host setup:

- base OS
- Docker and Docker Compose
- directories and permissions required by Xray
- optional pre-pulled `ghcr.io/xtls/xray-core:25.10.15`
- optional base proxy or networking setup from the GCP proxy repository

### Stage 2: Deploy runtime configuration onto instances created from that image

Continue using the current GitHub Actions + Ansible deployment flow to inject:

- UUID
- Reality keys
- short IDs
- SNI/domain
- final rendered `config.json`
- final `docker-compose.yml`
- service activation and validation

This preserves your current secret model while reducing bootstrapping time and making instance creation repeatable.

## Why this is the best fit here

This repository already separates deployment logic into roles. That is exactly the structure needed to split:

- **image-safe base setup**
- **runtime-specific deployment**

Instead of replacing the current deployment flow, the image pipeline should **prepare the machine so the existing flow becomes faster, safer, and more consistent**.

## Suggested Refactor Before Implementing Packer

Before adding Packer, I would split Ansible responsibilities into clearer layers:

1. **Base host layer**
   - Docker installation
   - package prerequisites
   - common directories
   - optional registry/login preparation if ever needed

2. **Image bake layer**
   - tasks safe to run during image creation
   - must not require secrets
   - may optionally pre-pull the Xray container image

3. **Runtime deploy layer**
   - secret-dependent configuration rendering
   - container startup
   - health checks
   - connection summary output

Today, `docker_prereqs` is already a strong candidate for the base/image layer, while `xray_deploy` is mostly runtime-layer logic.

## Recommended Implementation Plan

### Phase 1: Produce a minimal, safe image pipeline

1. Add a `packer/` directory with a Google Compute builder template.
2. Add a dedicated Ansible playbook for image baking.
3. Reuse only image-safe tasks from the current roles.
4. Build a custom image family such as `less-vision-reality`.
5. Keep the current deployment workflow unchanged for runtime configuration.

### Expected outcome

New instances start from an Xray-ready base image, then the existing deploy workflow applies secrets and final config.

### Phase 2: Integrate with the existing deployment experience

1. Add a GitHub Actions workflow such as `build-gce-image.yml`.
2. Trigger it manually at first.
3. Authenticate to GCP with GitHub OIDC / Workload Identity Federation if possible.
4. Output image name, family, labels, and build metadata in the workflow summary.
5. Optionally update downstream infrastructure to launch instances from the newest image family.

### Expected outcome

Image creation becomes repeatable and auditable from GitHub Actions.

### Phase 3: Converge with the GCP proxy foundation

Once the GCP proxy repository is accessible, identify which parts belong in the base image:

- OS hardening
- GCE agent or network setup
- proxy bootstrap packages
- users, firewall assumptions, logging agents, or monitoring agents

Then decide whether to:

- vendor shared Ansible into this repo,
- publish a shared role collection,
- or keep GCP proxy as the base image layer and this repo as the Xray layer.

My preference would be:

- **shared base image responsibilities** in one reusable layer,
- **Xray responsibilities** in this repository,
- clear separation between infrastructure base and application runtime.

## What I Would Pick Next

If I were choosing the next implementation step, I would pick:

### **Packer + Ansible + current deploy workflow retained**

Specifically:

1. build a reusable base image with Packer,
2. reuse Ansible for non-secret machine preparation,
3. keep secrets and final Xray config out of the image,
4. continue to run the existing deploy workflow against instances launched from that image.

This is the best balance of:

- speed,
- reproducibility,
- maintainability,
- and security.

## Why I Would Not Pick the Other Options First

- **Not deploy-then-snapshot as the main design**: it works, but it preserves drift.
- **Not shell-only Packer as the final design**: it duplicates Ansible and becomes harder to maintain.
- **Not machine images as the primary artifact**: they are heavier and less composable.
- **Not startup scripts as the main mechanism**: they shift too much work back to boot time.

## Design Risks to Watch

1. **Accidentally baking secrets into the image**
   - avoid by keeping image playbooks secret-free

2. **Image drift from runtime configuration**
   - avoid by keeping runtime config deployment separate and explicit

3. **Over-baking mutable application state**
   - avoid by baking prerequisites, not environment identity

4. **Coupling too tightly to one inaccessible external repository**
   - avoid by defining a clear contract for what comes from the GCP proxy layer

## Practical Recommendation

If you want the cleanest long-term solution, implement:

- **Packer for image creation**
- **Ansible for reusable machine preparation**
- **current GitHub Actions deploy flow for final Xray deployment**

If you want the fastest short-term solution, automate:

- temporary instance creation
- existing deploy workflow
- image creation from that instance

and then replace it with the Packer pipeline once the role boundaries are cleaned up.

## Concrete Next Actions

1. Confirm whether the future image should contain only Docker/Xray prerequisites or also include broader GCP proxy host setup.
2. Make the GCP proxy repository available, or copy its relevant setup logic into a design note.
3. Refactor Ansible into image-safe versus runtime-only layers.
4. Add a minimal Packer template for Google Compute custom images.
5. Add a manual GitHub Actions workflow to build the image.
6. Launch new instances from that image and run the existing deploy workflow unchanged.
7. Only after that, decide whether any runtime steps should move from deploy time into image bake time.

## Source References

- Google Cloud custom images: https://cloud.google.com/compute/docs/images
- Google Cloud machine images: https://cloud.google.com/compute/docs/machine-images
- Google Cloud startup scripts: https://cloud.google.com/compute/docs/startupscript
- Packer Google Compute builder: https://developer.hashicorp.com/packer/plugins/builders/googlecompute
- Packer provisioners: https://developer.hashicorp.com/packer/docs/provisioners
