import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reference" / "python"))
from memory_fabric import MemoryType, QueryRequest


class MemoryLimitsTests(unittest.TestCase):
    def test_invalid_limits_rejected(self):
        for limit in (0, -1, 101, True, 1.5, "10"):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                QueryRequest("records", [], [MemoryType.SEMANTIC], limit=limit)

    def test_valid_limits_preserved(self):
        for limit in (1, 10, 100):
            self.assertEqual(QueryRequest("records", [], [MemoryType.SEMANTIC], limit=limit).limit, limit)
