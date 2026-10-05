#!/usr/bin/env python3
"""Download a reviewed official release on the control host, never on the VM."""
import argparse,hashlib,io,json,pathlib,urllib.request,zipfile
RELEASES={
 '25.10.15':'df22ad60c1251c9fb63d7f85b3677872edf61c6715eba64b06adbfec658f4938',
 '26.3.27':'23cd9af937744d97776ee35ecad4972cf4b2109d1e0fe6be9930467608f7c8ae',
}
BINARY_SHA256={
 '25.10.15':'1d6b0fb6f2348683d59304c9f0bbf3611daa068527159b749374f12da252e78c',
 '26.3.27':'8255dd939c34cf966cc91517b6324dd3c8d0bcf49ffac8beca049a38c46845ed',
}
def verify(data,expected):
 if hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Official archive SHA-256 mismatch')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--version',choices=RELEASES,default='26.3.27');p.add_argument('--directory',type=pathlib.Path,required=True);p.add_argument('--github-env',type=pathlib.Path);p.add_argument('--json',action='store_true');a=p.parse_args()
 url=f'https://github.com/XTLS/Xray-core/releases/download/v{a.version}/Xray-linux-64.zip'
 with urllib.request.urlopen(url,timeout=90) as r:data=r.read()
 verify(data,RELEASES[a.version]);a.directory.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(io.BytesIO(data)) as z:binary=z.read('xray')
 verify(binary,BINARY_SHA256[a.version])
 path=(a.directory/'xray').resolve();path.write_bytes(binary);path.chmod(0o755)
 digest=hashlib.sha256(binary).hexdigest()
 if a.github_env:
  with a.github_env.open('a') as f:f.write(f'XRAY_BINARY_PATH={path}\nXRAY_BINARY_SHA256={digest}\n')
 if a.json:
  print(json.dumps({'path':str(path),'sha256':digest}));return
 print(f'Verified official Xray {a.version}; archive SHA-256 {RELEASES[a.version]}; binary SHA-256 {digest}')
if __name__=='__main__':main()
