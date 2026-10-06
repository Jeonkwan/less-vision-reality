# Podman runtime validation — 2026-10-06

Owner-approved scope: add rootful Podman as an extra runtime, preserving native
and Docker. Only disposable flatwhite may be mutated. Decaf and Cream are excluded.
No merge or release is authorized.

## Baseline and isolated host

Implementation starts from both published v2.2.0 main commits: proxy
`8d062e286943dd3b4f3c2829cfac8e567c79dda5`, infrastructure
`8e13b8794b46501880f49de2da43ea4dd4e0bb54`.

[Preflight inspection](https://github.com/Jeonkwan/lightsail-proxy/actions/runs/37416856247)
identified serving Decaf and Cream and confirmed the disposable scope.
[Guarded creation](https://github.com/Jeonkwan/lightsail-proxy/actions/runs/37417144019)
created `lightsail-singapore-a-flatwhite-20261006051026`, `18.141.16.60`,
owned static IP/key and workspace `flatwhite`. DNS temporarily points
`flatwhite.mokamaker.site` at that IP. Existing shared credentials stay in Actions.

## Compatibility finding and checks

The initial deployment validated configuration but failed actual TCP startup.
[Read-only kernel evidence](https://github.com/Jeonkwan/less-vision-reality/actions/runs/37418845436)
showed crun/AppArmor denial of socket creation with the optional Podman
no-new-privileges flag, matching Ubuntu bug
[2118824](https://bugs.launchpad.net/ubuntu/+source/libpod/+bug/2118824).
Omit that optional flag while retaining UID/GID 65532, zero effective/permitted/
bounding capabilities, default AppArmor/seccomp, private bridge networking and a
read-only config mount. No global AppArmor policy change. Container specification
v2 replaces the earlier failed definition without relying on config/image changes.

[Corrected deployment](https://github.com/Jeonkwan/less-vision-reality/actions/runs/37419095197)
passed. [Three-runtime CI](https://github.com/Jeonkwan/less-vision-reality/actions/runs/37419099945)
passed native, Docker and Podman paths. Actual rootful Podman tests check both
reviewed images (26.3.27 and 25.10.15), real config permission acceptance/rejection,
and actual TCP startup. Local ownership/switch tests cover all six opt-in and
activation-failure recovery conditions, ambiguity and unrelated published ports.
Infrastructure Terraform/bootstrap/ownership checks also passed.

## Live acceptance

Pending: [focused flatwhite run](https://github.com/Jeonkwan/less-vision-reality/actions/runs/37419346942).
The harness checks fresh Docker-free Podman deployment; supplied sing-box 1.11.4
and pinned mihomo 1.19.32 transport by IP/hostname; unchanged/changed deployment;
invalid selector/candidate; Podman lifecycle, crash recovery and actual journald
rotation; transitions to/from native and Docker with opt-in refusals; unrelated
container fixtures; and final Podman reboot. Existing native/Docker lifecycle
suites are not repeated. No peer fallback is permitted.

Runner transport success does not establish complete iOS TUN/DNS or mobile ISP
behavior. Live acceptance uses Xray 26.3.27; 25.10.15 Podman compatibility evidence
is limited to actual image/config/startup CI checks.

## Teardown

Pending until all acceptance gates pass. Destroy only the exact recorded instance
and owned static IP/key/snapshots, delete its empty workspace, and park
flatwhite.mokamaker.site at 127.0.0.1. Preserve Decaf/Cream and shared backends,
credentials and environments.
