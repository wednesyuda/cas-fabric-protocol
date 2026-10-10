"""Synthetic provider-level decision diagnostics; not a production quality gate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import time

from document_verifier_node import checked_response, generate
from release_identity import source_identity


def score_decision(case, response):
    if response.get("ok") is not True or response.get("actions_allowed") is not False:
        return False
    if response.get("status") != case["expected_status"]:
        return False
    answer = response.get("output", "").lower()
    if not all(term.lower() in answer for term in case["required_terms"]):
        return False
    if case["expected_status"] == "answer":
        return bool(set(response.get("sources", [])) & set(case["expected_sources"]))
    if response.get("sources"):
        return False
    if case["expected_status"] == "needs_review":
        return bool(re.search(r"konflik|bertentangan|berbeda|tidak konsisten", answer))
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    root = Path(__file__).resolve().parents[1]
    fixture = root / "tests/fixtures/verifier-decisions.json"
    packet = json.loads(fixture.read_text(encoding="utf-8"))
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "input-manifest.json").write_text(json.dumps({
        "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
        "source": source_identity(root), "scope": packet["scope"]}, indent=2))
    rows = []
    for case in packet["cases"]:
        before = time.monotonic()
        tokens = None
        try:
            # Reference labels and terms are never sent to the model.
            value, tokens = generate(case["question"], case["candidate"], case["evidence"])
            response = checked_response(value, case["candidate"], case["evidence"])
        except Exception as exc:
            response = {"ok": False, "error": str(exc), "actions_allowed": False}
        row = {"id": case["id"], "passed": score_decision(case, response),
               "expected_status": case["expected_status"], "response": response,
               "tokens": tokens, "elapsed_s": time.monotonic() - before}
        rows.append(row)
        with (output / "results.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(json.dumps({"completed": len(rows), "id": case["id"], "passed": row["passed"]}), flush=True)
    summary = {"cases": len(rows), "passed": sum(r["passed"] for r in rows),
               "validation_errors": sum(r["response"].get("ok") is not True for r in rows),
               "failed_ids": [r["id"] for r in rows if not r["passed"]],
               "elapsed_s": sum(r["elapsed_s"] for r in rows),
               "groups": {status: {"cases": sum(r["expected_status"] == status for r in rows),
                          "passed": sum(r["passed"] and r["expected_status"] == status for r in rows)}
                          for status in ("needs_review", "answer", "abstain")},
               "scope": packet["scope"], "pilot_gate": "hold"}
    (output / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary), flush=True)
    if summary["failed_ids"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
