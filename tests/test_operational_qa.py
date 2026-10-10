import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from evaluate_operational_qa import score_response


class OperationalScoringTests(unittest.TestCase):
    def test_fact_requires_expected_citation_and_all_reference_terms(self):
        case = {"kind": "historical_fact", "source_ids": ["A"], "required_terms": [["240"], ["zoom"]]}
        response = {"status": "answer", "output": "240 menit melalui Zoom", "sources": ["B"],
                    "evidence": [{"source_id": "A"}]}
        self.assertEqual(score_response(case, response),
                         {"candidate_reference_pass": False, "retrieval_hit": True})
        response["sources"] = ["A"]
        self.assertTrue(score_response(case, response)["candidate_reference_pass"])
        response["output"] = "240 menit"
        self.assertFalse(score_response(case, response)["candidate_reference_pass"])

    def test_unknown_requires_explicit_abstention_without_citations(self):
        case = {"kind": "unanswerable"}
        self.assertTrue(score_response(case, {"status": "abstain", "sources": []})["candidate_reference_pass"])
        self.assertFalse(score_response(case, {"status": "answer", "sources": []})["candidate_reference_pass"])
