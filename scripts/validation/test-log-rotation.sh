#!/usr/bin/env bash
set -euo pipefail
name=cream-bounded-log-probe
trap 'sudo -n docker rm -f "$name" >/dev/null 2>&1 || true' EXIT
sudo -n docker pull busybox:1.37.0
sudo -n docker run -d --name "$name" --network none --memory 32m --cpus 0.25 --log-driver json-file --log-opt max-size=10m --log-opt max-file=3 busybox:1.37.0 sh -c 'yes LOG_ROTATION_PROBE | head -c 45000000'
code=$(sudo -n timeout 180 docker wait "$name")
[ "$code" = 0 ]
sudo -n python3 - <<'CHECK'
import subprocess,pathlib
p=pathlib.Path(subprocess.check_output(['docker','inspect','--format={{.LogPath}}','cream-bounded-log-probe'],text=True).strip())
files=[p]+list(p.parent.glob(p.name+'.*'))
sizes={f.name:f.stat().st_size for f in files}
print('Actual rotated probe logs:',sizes)
assert len(files)==3,sizes
assert all(n<=10*1024*1024+65536 for n in sizes.values()),sizes
assert sum(sizes.values())<=30*1024*1024+3*65536,sizes
CHECK
