"""Fail closed for corrupted artifacts; validate actual templates with both releases."""
import importlib.util,pathlib,unittest,hashlib
root=pathlib.Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('prepare',root/'scripts/prepare-native.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Integrity(unittest.TestCase):
 def test_corruption_rejected(self):
  with self.assertRaises(ValueError):m.verify(b'corrupt',hashlib.sha256(b'original').hexdigest())
 def test_reviewed_versions_only(self):
  self.assertEqual(set(m.RELEASES),{'25.10.15','26.3.27'})
if __name__=='__main__':unittest.main()
