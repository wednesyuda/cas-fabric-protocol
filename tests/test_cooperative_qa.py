import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from document_verifier_node import checked_response
from evaluate_cooperative_qa import fail_closed, score


class VerificationTests(unittest.TestCase):
    def test_accept_cannot_silently_replace_candidate(self):
        candidate = {"answer": "Original", "sources": ["A"], "abstain": False}
        result = checked_response({"decision": "accept", "answer": "Different", "sources": ["A"],
            "reason": "supported"}, candidate, [{"source_id": "A"}])
        self.assertEqual(result["output"], "Original")

    def test_invented_citation_and_review_with_citations_are_rejected(self):
        for decision, sources in (("revise", ["B"]), ("needs_review", ["A"])):
            with self.subTest(decision=decision), self.assertRaises(ValueError):
                checked_response({"decision": decision, "answer": "x", "sources": sources,
                    "reason": "x"}, {}, [{"source_id": "A"}])

    def test_verifier_loss_never_auto_approves(self):
        for response in (None, {"ok": False}, {"ok": True, "actions_allowed": True}):
            result = fail_closed(response)
            self.assertEqual(result["status"], "needs_review")
            self.assertFalse(result["actions_allowed"])

    def test_accept_can_preserve_valid_abstention(self):
        candidate = {"answer": "Tidak tersedia.", "sources": [], "abstain": True}
        result = checked_response({"decision": "accept", "answer": "Tidak tersedia.",
            "sources": [], "reason": "Bukti tidak ada."}, candidate, [{"source_id": "A"}])
        self.assertEqual(result["status"], "abstain")

    def test_conflict_requires_explanation_and_review(self):
        case = {"kind": "controlled_conflict"}
        self.assertFalse(score(case, {"status": "abstain", "output": "Tidak diketahui"}))
        self.assertTrue(score(case, {"status": "needs_review", "sources": [], "output": "Bukti berkonflik."}))
