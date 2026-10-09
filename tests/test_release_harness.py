import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verify_release


class HarnessTests(unittest.TestCase):
    def test_created_container_removed_if_start_fails(self):
        calls = []

        def docker(command, **kwargs):
            calls.append(command)
            if command[:2] == ["docker", "create"]:
                return subprocess.CompletedProcess(command, 0, stdout="owned-id\n")
            if command[:2] == ["docker", "start"]:
                raise subprocess.CalledProcessError(1, command)
            return subprocess.CompletedProcess(command, 0)

        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp, \
                patch.object(verify_release, "ROOT", Path(temp)), \
                patch.object(verify_release, "source_identity", return_value={"commit": "fixture"}), \
                patch.object(sys, "argv", ["verify_release.py"]), \
                patch("verify_release.subprocess.run", side_effect=docker), \
                patch.dict("os.environ", clear=False):
            with self.assertRaises(subprocess.CalledProcessError):
                verify_release.main()
        self.assertIn(["docker", "rm", "-f", "owned-id"], calls)

    def test_mismatched_provider_source_rejected_before_infrastructure(self):
        import json
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp:
            root = Path(temp)
            adapter = root / "adapter.py"
            adapter.write_text("changed provider")
            manifest = root / "profile.json"
            manifest.write_text(json.dumps({"model": "test-model", "model_digest": "digest",
                                           "source_sha256": {"adapter.py": "wrong-hash"}}))
            argv = ["verify_release.py", "--model-url", "http://localhost:21435",
                    "--model", "test-model", "--provider-manifest", str(manifest),
                    "--provider-source", str(adapter)]
            with patch.object(verify_release, "ROOT", root), \
                    patch.object(verify_release, "source_identity", return_value={"commit": "fixture"}), \
                    patch.object(sys, "argv", argv), patch("verify_release.subprocess.run") as docker:
                with self.assertRaisesRegex(ValueError, "provider sources do not match"):
                    verify_release.main()
                docker.assert_not_called()
                self.assertFalse((root / "release-evidence").exists())
