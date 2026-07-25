import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path


spec = importlib.util.spec_from_file_location("googledrivedownload", Path(__file__).resolve().parents[1] / "googledrivedownload.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Md5SkipTests(unittest.TestCase):
    def test_build_existing_hash_index_returns_md5_map(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            sample = tmp_path / "photo.jpg"
            sample.write_bytes(b"hello world")

            index = module.build_existing_hash_index(tmp_path)

            self.assertEqual(index[hashlib.md5(b"hello world").hexdigest()], sample)

    def test_find_matching_local_file_returns_existing_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            sample = tmp_path / "photo.jpg"
            sample.write_bytes(b"hello world")
            index = module.build_existing_hash_index(tmp_path)

            result = module.find_matching_local_file(index, hashlib.md5(b"hello world").hexdigest())

            self.assertEqual(result, sample)


if __name__ == "__main__":
    unittest.main()
