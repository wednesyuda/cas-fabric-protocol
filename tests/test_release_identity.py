import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from release_identity import hash_sources, source_identity


class IdentityTests(unittest.TestCase):
    def test_export_rejects_changed_source_and_normalizes_line_endings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "runtime.py"
            source.write_bytes(b"print('hello')\r\n")
            manifest = {"commit": "frozen-commit", **hash_sources(root, ["runtime.py"])}
            (root / "candidate-manifest.json").write_text(json.dumps(manifest))
            source.write_bytes(b"print('hello')\n")
            self.assertEqual(source_identity(root)["commit"], "frozen-commit")
            source.write_text("print('changed')\n")
            with self.assertRaises(ValueError):
                source_identity(root)

    def test_manifest_cannot_read_outside_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                hash_sources(Path(temp), ["../outside"])
