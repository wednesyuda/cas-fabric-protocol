"""Regenerate single-model baselines on identical private evidence for comparison."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import time
import urllib.error

from evaluate_cooperative_qa import score
from document_answer import RULE, answer_schema, validate_answer
from document_verifier_node import verifier_options
from experiment_inference import complete
from release_identity import source_identity


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--backend", choices=("ollama", "llamacpp"), required=True)
    parser.add_argument("--url", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    packet_path = Path(args.packet)
    packet = json.loads(packet_path.read_text())
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"source": source_identity(Path(__file__).resolve().parents[1]),
                "input_packet_sha256": hashlib.sha256(packet_path.read_bytes()).hexdigest(),
                "model": args.model, "backend": args.backend,
                "requested_options": verifier_options(), "think": False,
                "scope": "frozen development evidence; lexical scoring, not independent semantic approval"}
    (output / "input-manifest.json").write_text(json.dumps(manifest, indent=2))
    rows = []
    transport_failed = False
    for case in packet["cases"]:
        evidence = case["baseline"]["evidence"]
        schema = answer_schema(evidence)
        before = time.monotonic()
        tokens = None
        try:
            content, tokens = complete(args.url, args.backend, args.model,
                [{"role": "system", "content": RULE + " Output schema: " + json.dumps(schema)},
                 {"role": "user", "content": json.dumps({"question": case["question"], "evidence": evidence}, ensure_ascii=False)}],
                schema, verifier_options())
            answer = validate_answer(content, evidence)
            response = {"ok": True, "actions_allowed": False, "evidence": evidence,
                        "status": "needs_review" if answer.get("needs_review") else "abstain" if answer["abstain"] else "answer",
                        "output": answer["answer"], "sources": answer["sources"]}
        except Exception as exc:
            response = {"ok": False, "actions_allowed": False, "evidence": evidence,
                        "status": "needs_review", "output": "Inference failed; review required.",
                        "sources": [], "error": str(exc)}
            transport_failed = isinstance(exc, (TimeoutError, urllib.error.URLError))
        row = {"id": case["id"], "kind": case["kind"], "passed": response["ok"] and score(case, response),
               "response": response, "elapsed_s": time.monotonic() - before, "tokens": tokens}
        rows.append(row)
        with (output / "results.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        case.update(baseline=response, baseline_elapsed_s=row["elapsed_s"], baseline_tokens=tokens)
        print(json.dumps({"completed": len(rows), "passed": row["passed"], "model": args.model}), flush=True)
        if transport_failed:
            break
    summary = {"model": args.model, "backend": args.backend, "planned_cases": len(packet["cases"]),
               "cases": len(rows), "passed": sum(r["passed"] for r in rows),
               "validation_errors": sum(not r["response"]["ok"] for r in rows),
               "aborted_transport_failure": transport_failed, "total_elapsed_s": sum(r["elapsed_s"] for r in rows),
               "mean_elapsed_s": statistics.mean(r["elapsed_s"] for r in rows),
               "max_elapsed_s": max(r["elapsed_s"] for r in rows),
               "tokens": {k: sum((r["tokens"] or {}).get(k, 0) or 0 for r in rows) for k in ("prompt_tokens", "output_tokens")},
               "pilot_gate": "hold", "scope": manifest["scope"]}
    (output / "summary.json").write_text(json.dumps(summary, indent=2))
    if len(rows) == len(packet["cases"]) and not summary["validation_errors"]:
        packet["baseline_provenance"] = {"model": args.model, "source": manifest["source"]["commit"],
            "input_packet_sha256": manifest["input_packet_sha256"],
            "primary_results_sha256": hashlib.sha256((output / "results.jsonl").read_bytes()).hexdigest(),
            "source_method": "fresh single-model inference; frozen questions/evidence/references"}
        (output / "baseline-packet.json").write_text(json.dumps(packet, ensure_ascii=False, indent=2))
    print(json.dumps(summary), flush=True)
    if summary["validation_errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
