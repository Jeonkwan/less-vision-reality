"""Regression for sparse journal files: disk retention measures allocated blocks."""
import importlib.util
import pathlib
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('validation',pathlib.Path(__file__).resolve().parents[1]/'native-validation.py')
validation=importlib.util.module_from_spec(spec)
spec.loader.exec_module(validation)

class JournalStorage(unittest.TestCase):
    def test_sparse_reserved_space_does_not_count_as_retained_disk_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            sparse=pathlib.Path(tmp)/'system.journal'
            with sparse.open('wb') as stream:
                stream.truncate(256*1024**2)
                stream.write(b'journal-header'*300)
            dense=pathlib.Path(tmp)/'user.journal'
            dense.write_bytes(b'entry'*2048)
            allocated=validation.journal_allocated_bytes([sparse,dense])
            self.assertGreater(allocated,0)
            self.assertLess(allocated,1024**2)
            self.assertGreater(sum(p.stat().st_size for p in [sparse,dense]),100*1024**2)

if __name__=='__main__':unittest.main()
