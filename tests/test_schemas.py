import json
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft7Validator, FormatChecker

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reference" / "python"))
from task_coordinator_service import GoalStore


class SchemaTests(unittest.TestCase):
    def test_all_schemas_are_valid_draft7(self):
        schemas = list((Path(__file__).resolve().parents[1] / "schemas").glob("*.json"))
        self.assertEqual(len(schemas), 5)
        for path in schemas:
            with self.subTest(schema=path.name):
                Draft7Validator.check_schema(json.loads(path.read_text()))

    def test_persistent_goal_matches_public_schema(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temp:
            schema = json.loads((Path(__file__).resolve().parents[1] / "schemas" / "goal.schema.json").read_text())
            goal = GoalStore(str(Path(temp) / "goals.json")).create("Read", ["memory.query"])
            Draft7Validator(schema, format_checker=FormatChecker()).validate(goal)
