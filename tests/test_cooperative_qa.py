import sys
import unittest
from unittest.mock import AsyncMock, patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from document_verifier_node import checked_response, handle, verification_schema
from evaluate_cooperative_qa import fail_closed, score
from evaluate_verifier_decisions import score_decision


class VerificationTests(unittest.TestCase):
    def test_schema_constrains_sources_by_decision(self):
        for abstain in (False, True):
            schema = verification_schema({"abstain": abstain}, [{"source_id": "A"}])
            for variant in schema["anyOf"]:
                props = variant["properties"]
                decision = props["decision"]["enum"][0]
                sources = props["sources"]
                if decision in ("abstain", "needs_review") or (decision == "accept" and abstain):
                    self.assertEqual(sources["maxItems"], 0)
                else:
                    self.assertEqual(sources["minItems"], 1)
                self.assertEqual(sources["items"]["enum"], ["A"])

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
        for response in (None, [], "invalid", {"ok": False}, {"ok": True, "actions_allowed": True}):
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

    def test_decision_diagnostic_does_not_reward_reason_only_conflict_or_blanket_review(self):
        conflict = {"expected_status": "needs_review", "required_terms": ["senin", "jumat"], "expected_sources": []}
        response = {"ok": True, "actions_allowed": False, "status": "answer",
                    "output": "Informasi tidak tersedia.", "sources": ["A"],
                    "reason": "Bukti Senin dan Jumat berkonflik."}
        self.assertFalse(score_decision(conflict, response))
        response.update(status="needs_review", output="Bukti berkonflik: Senin dan Jumat.", sources=[])
        self.assertTrue(score_decision(conflict, response))
        factual = {"expected_status": "answer", "required_terms": ["senin"], "expected_sources": ["A"]}
        self.assertFalse(score_decision(factual, response))


class VerifierReadinessTests(unittest.IsolatedAsyncioTestCase):
    async def test_readiness_does_not_call_model(self):
        respond = AsyncMock()
        with patch("document_verifier_node.generate") as model:
            await handle({"payload": {"probe": True}, "respond": respond})
        model.assert_not_called()
        self.assertEqual(respond.call_args.args[0]["type"], "experiment.verification.health")
