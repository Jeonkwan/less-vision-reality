"""Exercise artifact corruption and OpenSSH key serialization failure boundaries."""
import importlib.util,pathlib,unittest,hashlib,tempfile,subprocess
root=pathlib.Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('prepare',root/'scripts/prepare-native.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Integrity(unittest.TestCase):
 def test_corruption_rejected(self):
  with self.assertRaises(ValueError):m.verify(b'corrupt',hashlib.sha256(b'original').hexdigest())
 def test_key_without_trailing_newline_is_accepted_by_openssh(self):
  spec=importlib.util.spec_from_file_location('validation',root/'scripts/native-validation.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  with tempfile.TemporaryDirectory() as tmp:
   original=pathlib.Path(tmp)/'original';stored=pathlib.Path(tmp)/'stored'
   subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(original)],check=True)
   module.write_private_key(stored,original.read_text().rstrip())
   actual=subprocess.check_output(['ssh-keygen','-y','-f',str(stored)],text=True).strip()
   expected=' '.join(original.with_suffix('.pub').read_text().split()[:2])
   self.assertEqual(' '.join(actual.split()[:2]),expected);self.assertEqual(stored.stat().st_mode & 0o777,0o600)
if __name__=='__main__':unittest.main()
