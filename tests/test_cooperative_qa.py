import sys
import contextlib
import io
import json
import tempfile
import os
import unittest
from unittest.mock import AsyncMock, patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from document_verifier_node import checked_response, handle, verification_schema, verifier_options, generate
from evaluate_cooperative_qa import fail_closed, score
from evaluate_verifier_decisions import score_decision
import evaluate_verifier_decisions
import evaluate_model_baseline
from experiment_inference import complete


class VerificationTests(unittest.TestCase):
    def test_incomplete_single_baseline_cannot_become_a_cooperative_packet(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            packet = root / "input.json"
            case = {"id": "unknown", "kind": "unanswerable", "question": "Unknown?",
                    "baseline": {"evidence": [{"source_id": "A", "text": "Other facts."}]}}
            packet.write_text(json.dumps({"cases": [case, {**case, "id": "unknown-2"}]}))
            output = root / "result"
            args = ["baseline", "--packet", str(packet), "--output", str(output),
                    "--model", "test", "--backend", "ollama", "--url", "http://127.0.0.1:21437"]
            with patch.object(sys, "argv", args), \
                 patch.object(evaluate_model_baseline, "source_identity", return_value={"commit": "test"}), \
                 patch.object(evaluate_model_baseline, "complete", side_effect=TimeoutError("timed out")) as model, \
                 contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
                evaluate_model_baseline.main()
            self.assertEqual(model.call_count, 1)
            self.assertFalse((output / "baseline-packet.json").exists())
            summary = json.loads((output / "summary.json").read_text())
            self.assertEqual(summary["cases"], 1)
            self.assertEqual(summary["planned_cases"], 2)
            self.assertEqual(summary["passed"], 0)

    def test_larger_provider_adapter_preserves_schema_budget_and_usage(self):
        result = {"choices": [{"message": {"content": '{"answer":"x"}'}}],
                  "usage": {"prompt_tokens": 14, "completion_tokens": 7}}
        options = {"temperature": 0, "seed": 42, "num_predict": 512}
        with patch("experiment_inference.urllib.request.urlopen", return_value=io.BytesIO(json.dumps(result).encode())) as provider:
            content, tokens = complete("http://127.0.0.1:18039", "llamacpp", "cas-bonsai-27b", [], {"type": "object"}, options)
        request = provider.call_args.args[0]
        payload = json.loads(request.data)
        self.assertTrue(request.full_url.endswith("/v1/chat/completions"))
        self.assertEqual(payload["response_format"]["json_schema"]["schema"], {"type": "object"})
        self.assertEqual(payload["max_tokens"], 512)
        self.assertEqual(tokens["output_tokens"], 7)
        self.assertEqual(content, '{"answer":"x"}')
        with self.assertRaises(ValueError):
            complete("http://127.0.0.1:18039", "invalid", "x", [], {}, options)

    def test_verifier_explicitly_disables_thinking_and_preserves_gpu_option(self):
        body = {"message": {"content": '{"decision":"abstain","answer":"Tidak tersedia.","sources":[],"reason":"Tidak ada bukti."}'},
                "prompt_eval_count": 12, "eval_count": 10}
        with patch.dict(os.environ, {"CAS_VERIFIER_URL": "http://127.0.0.1:21437", "CAS_VERIFIER_NUM_GPU": "-1"}), \
             patch("experiment_inference.urllib.request.urlopen", return_value=io.BytesIO(json.dumps(body).encode())) as provider:
            result, tokens = generate("Pertanyaan?", {"abstain": True}, [{"source_id": "A"}])
        payload = json.loads(provider.call_args.args[0].data)
        self.assertIs(payload["think"], False)
        self.assertEqual(payload["options"]["num_gpu"], -1)
        self.assertEqual(result["decision"], "abstain")
        self.assertEqual(tokens["output_tokens"], 10)

    def test_gpu_verification_requires_explicit_opt_in(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(verifier_options()["num_gpu"], 0)
        with patch.dict(os.environ, {"CAS_VERIFIER_NUM_GPU": "-1"}):
            self.assertEqual(verifier_options()["num_gpu"], -1)
        for invalid in ("2", "invalid"):
            with patch.dict(os.environ, {"CAS_VERIFIER_NUM_GPU": invalid}), self.assertRaises(ValueError):
                verifier_options()

    def test_provider_timeout_stops_packet_without_claiming_full_evaluation(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "diagnostic"
            with patch.object(sys, "argv", ["diagnostic", "--output", str(output)]), \
                 patch.object(evaluate_verifier_decisions, "source_identity", return_value={"commit": "test"}), \
                 patch.object(evaluate_verifier_decisions, "generate", side_effect=TimeoutError("timed out")) as model, \
                 contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit):
                evaluate_verifier_decisions.main()
            self.assertEqual(model.call_count, 1)
            summary = json.loads((output / "summary.json").read_text())
            self.assertEqual(summary["cases"], 1)
            self.assertGreater(summary["planned_cases"], summary["cases"])
            self.assertTrue(summary["aborted_transport_failure"])
            self.assertEqual(summary["pilot_gate"], "hold")

    def test_verifier_choices_keep_citation_validation_at_response_boundary(self):
        evidence = [{"source_id": "A"}]
        schema = verification_schema({"abstain": True}, evidence)
        self.assertEqual(schema["properties"]["sources"]["items"]["enum"], ["A"])
        self.assertEqual(set(schema["properties"]["decision"]["enum"]),
                         {"accept", "revise", "abstain", "needs_review"})
        for decision, sources in (("revise", []), ("abstain", ["A"]), ("needs_review", ["A"])):
            with self.subTest(decision=decision), self.assertRaises(ValueError):
                checked_response({"decision": decision, "answer": "x", "sources": sources,
                                  "reason": "x"}, {"abstain": True}, evidence)

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

    def test_review_explanation_is_visible_without_changing_decision(self):
        candidate = {"answer": "Tidak tersedia.", "sources": [], "abstain": True}
        result = checked_response({"decision": "needs_review", "answer": "Perlu review.",
            "sources": [], "reason": "Bukti Senin dan Jumat bertentangan."}, candidate, [{"source_id": "A"}])
        self.assertEqual(result["status"], "needs_review")
        self.assertIn("Senin dan Jumat bertentangan", result["output"])
        self.assertEqual(result["sources"], [])
        result = checked_response({"decision": "revise", "answer": "Senin.", "sources": ["A"],
            "reason": "Ada konflik yang belum diselesaikan."}, candidate, [{"source_id": "A"}])
        self.assertEqual(result["status"], "answer")
        self.assertEqual(result["output"], "Senin.")

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
