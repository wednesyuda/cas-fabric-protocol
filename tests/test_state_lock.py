import os
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"reference/python"))
from state_lock import StateLocks

class Ownership(unittest.TestCase):
    def test_second_owner_is_rejected_and_can_take_over_after_release(self):
        with tempfile.TemporaryDirectory() as temp:
            paths=[Path(temp)/"goals.json",Path(temp)/"reflections.json"]
            with StateLocks(paths):
                with self.assertRaises(RuntimeError):StateLocks(paths).acquire()
            with StateLocks(paths):pass

    def test_process_exit_releases_ownership(self):
        import subprocess
        import json
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"state.json"
            module=str(Path(__file__).resolve().parents[1]/"reference/python")
            code="import sys;sys.path.insert(0,sys.argv[1]);from state_lock import StateLocks;StateLocks([sys.argv[2]]).acquire()"
            subprocess.run([sys.executable,"-c",code,module,str(path)],check=True,timeout=10)
            with StateLocks([path]):pass
