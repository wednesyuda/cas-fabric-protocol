import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from verify_internal_runtime import save_result


class WorkloadGateTests(unittest.TestCase):
    def test_failed_responses_preserve_evidence_and_exit_nonzero(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            result = {"operational_errors": 2, "authenticated_goal_lifecycle": "fail"}
            with self.assertRaises(SystemExit) as failure:
                save_result(path, result)
            self.assertEqual(failure.exception.code, 1)
            self.assertEqual(json.loads((path / "summary.json").read_text()), result)

    def test_valid_responses_complete_normally(self):
        with tempfile.TemporaryDirectory() as temp:
            save_result(Path(temp), {"operational_errors": 0, "authenticated_goal_lifecycle": "pass"})
