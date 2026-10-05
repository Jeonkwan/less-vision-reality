"""Exercise reviewed CLI labels and failures without logging generated keys."""
import os,pathlib,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[2]
class Keys(unittest.TestCase):
 def test_reviewed_output_labels_and_failures(self):
  for output,status,expected in [('PrivateKey: private\nPassword: public\n',0,0),
                                 ('PrivateKey: private\nPassword (PublicKey): public\nHash32: hash\n',0,0),
                                 ('Private key: private\nPublic key: public\n',0,0),
                                 ('PrivateKey: sensitive-value\n',0,1),
                                 ('sensitive-value',9,9)]:
   with self.subTest(output=output),tempfile.TemporaryDirectory() as tmp:
    p=pathlib.Path(tmp);docker=p/'docker'
    docker.write_text('#!/bin/sh\nprintf \'%s\' "$MOCK_OUTPUT"\nexit "$MOCK_STATUS"\n');docker.chmod(0o755)
    result=subprocess.run(['sh',str(ROOT/'.github/actions/generate-credentials/scripts/xray-keys.sh')],
      env={**os.environ,'PATH':tmp+':'+os.environ['PATH'],'MOCK_OUTPUT':output,'MOCK_STATUS':str(status),'GITHUB_OUTPUT':str(p/'out')},capture_output=True,text=True)
    self.assertEqual(result.returncode,expected,result.stderr)
    self.assertNotIn('sensitive-value',result.stdout+result.stderr)
    if expected==0:self.assertEqual((p/'out').read_text(),'private=private\npublic=public\n')
if __name__=='__main__':unittest.main()
