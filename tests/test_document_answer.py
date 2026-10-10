import json
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"reference/python"))
from document_answer import validate_answer
from reasoning_node_service import ReasoningNode

class Answers(unittest.TestCase):
    def test_fabricated_citation_and_false_abstention_fail(self):
        for value in ({"answer":"x","sources":["missing"],"abstain":False},
                      {"answer":"x","sources":["doc"],"abstain":True},
                      {"answer":"x","sources":[],"abstain":False}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_answer(json.dumps(value),[{"source_id":"doc"}])

class DocumentMode(unittest.IsolatedAsyncioTestCase):
    async def test_absent_evidence_and_review_request_never_generate(self):
        for review in (False,True):
            node=ReasoningNode();node.document_mode=True;respond=AsyncMock()
            request={"intent":"question","values_signature":{"values_consulted":True},
                     "prepared_context":{"relevant_semantic":[]},"constraints":{"requires_human_review":review}}
            with patch("reasoning_node_service.document_generate") as model:
                await node.handle_reasoning({"payload":{"intent":"question","reasoning_request":request},"respond":respond})
            model.assert_not_called()
            result=respond.call_args.args[0]
            self.assertEqual(result["status"],"needs_review" if review else "abstain")
            self.assertFalse(result["actions_allowed"])
