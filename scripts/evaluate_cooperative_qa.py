"""Paired replay of frozen primary outputs through a separate authenticated verifier."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import uuid

from document_verifier_node import CAPABILITY
from evaluate_operational_qa import score_response
from fabric_nats import NATSFabric
from prepare_internal_profile import prepare
from release_identity import source_identity
from verify_release import NATS_IMAGE

ROOT = Path(__file__).resolve().parents[1]


def score(case, response):
    if case["kind"] == "controlled_conflict":
        return bool(response.get("status") == "needs_review" and not response.get("sources")
                    and re.search(r"(?i)(konflik|bertentangan|berbeda|tidak konsisten)", response.get("output", "")))
    return score_response(case, response)["candidate_reference_pass"]


def fail_closed(response):
    if not isinstance(response, dict):
        response = {}
    if not response or response.get("ok") is not True or response.get("actions_allowed") is not False:
        return {"ok": False, "status": "needs_review", "output": "Verifikasi gagal; perlu tinjauan manusia.",
                "sources": [], "actions_allowed": False,
                "error": (response or {}).get("error", "verifier unavailable or invalid"),
                "model_request_attempted": (response or {}).get("model_request_attempted", False),
                "tokens": (response or {}).get("tokens")}
    return response


async def run(packet, output, process):
    fabric = NATSFabric()
    await fabric.connect()
    rows = []
    try:
        ready = await fabric.request(CAPABILITY, {"probe": True}, timeout=5)
        if not ready or ready.get("type") != "experiment.verification.health":
            raise RuntimeError("authenticated verifier readiness failed")
        for case in packet["cases"]:
            baseline = case["baseline"]
            candidate = {"answer": baseline["output"], "sources": baseline["sources"],
                         "abstain": baseline["status"] != "answer", "needs_review": baseline["status"] == "needs_review"}
            before = time.monotonic()
            result = fail_closed(await fabric.request(CAPABILITY, {"question": case["question"],
                "candidate": candidate, "evidence": baseline["evidence"]}, timeout=120))
            row = {"id": case["id"], "kind": case["kind"], "baseline_pass": score(case, baseline),
                   "cooperative_pass": score(case, result), "verification_ok": result.get("ok") is True,
                   "baseline_elapsed_s": case["baseline_elapsed_s"], "verifier_elapsed_s": time.monotonic() - before,
                   "response": result}
            rows.append(row)
            with (output / "results.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(json.dumps({"completed": len(rows), "total": len(packet["cases"]),
                              "baseline_pass": row["baseline_pass"], "cooperative_pass": row["cooperative_pass"]}), flush=True)
        process.terminate()
        await asyncio.to_thread(process.wait, timeout=150)
        unavailable = fail_closed(await fabric.request(CAPABILITY, {"question": "failure probe"}, timeout=.2))
        assert unavailable["status"] == "needs_review" and unavailable["actions_allowed"] is False
    finally:
        await fabric.close()
    return {"cases": len(rows), "baseline_pass": sum(r["baseline_pass"] for r in rows),
            "cooperative_pass": sum(r["cooperative_pass"] for r in rows),
            "regressions": [r["id"] for r in rows if r["baseline_pass"] and not r["cooperative_pass"]],
            "improvements": [r["id"] for r in rows if not r["baseline_pass"] and r["cooperative_pass"]],
            "verifier_errors": sum(not r["verification_ok"] for r in rows),
            "verification_requests": len(rows),
            "extra_model_request_attempts": sum(bool(r["response"].get("model_request_attempted")) for r in rows),
            "completed_extra_model_calls": sum(bool(r["response"].get("tokens")) for r in rows),
            "total_verifier_elapsed_s": sum(r["verifier_elapsed_s"] for r in rows),
            "verifier_unavailability": "needs_review, no action", "pilot_gate": "hold",
            "scope": "paired replay of frozen baseline; lexical diagnostics, not independent semantic scoring",
            "reference_review": "historical QA references approved by owner; new outputs need review",
            "latency_scope": "baseline archived; cooperative latency is archived baseline plus measured verification"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    packet_path = Path(args.packet)
    packet = json.loads(packet_path.read_text())
    output = Path(args.output)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    (output / "source-manifest.json").write_text(json.dumps(source_identity(ROOT), indent=2))
    import hashlib
    (output / "input-manifest.json").write_text(json.dumps({"packet_sha256": hashlib.sha256(packet_path.read_bytes()).hexdigest(),
        "baseline_provenance": packet["baseline_provenance"], "verifier_model": "qwen2.5:3b"}, indent=2))
    cid = None
    process = None
    with tempfile.TemporaryDirectory(prefix="cas-cooperation-") as temp:
        profile = prepare(Path(temp) / "auth", {"requester": (["capability." + CAPABILITY], []),
                                               "verifier": ([], ["capability." + CAPABILITY])})
        env = {**os.environ, "CAS_NATS_URL": "nats://127.0.0.1:22052",
               "CAS_NATS_AUTH_FILE": str(profile / "verifier.json"),
               "CAS_VERIFIER_URL": "http://127.0.0.1:21437", "CAS_VERIFIER_MODEL": "qwen2.5:3b"}
        try:
            cid = subprocess.check_output(["docker", "create", "--name", "cas-cooperation-" + uuid.uuid4().hex[:10],
                "--memory", "256m", "--cpus", "1", "-p", "127.0.0.1:22052:4222", "--mount",
                f"type=bind,src={profile/'nats.json'},dst=/etc/nats/profile.json,readonly", NATS_IMAGE,
                "-c", "/etc/nats/profile.json"], text=True).strip()
            subprocess.run(["docker", "start", cid], check=True, stdout=subprocess.DEVNULL)
            with (output / "verifier.log").open("w") as log:
                process = subprocess.Popen([sys.executable, str(ROOT / "scripts/document_verifier_node.py")],
                                           env=env, stdout=log, stderr=subprocess.STDOUT)
                time.sleep(3)
                if process.poll() is not None:
                    raise RuntimeError("verifier exited during startup")
                os.environ.update(env)
                os.environ["CAS_NATS_AUTH_FILE"] = str(profile / "requester.json")
                summary = asyncio.run(run(packet, output, process))
                (output / "summary.json").write_text(json.dumps(summary, indent=2))
                print(json.dumps(summary), flush=True)
                if summary["verifier_errors"] or summary["regressions"]:
                    raise SystemExit(1)
        finally:
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=150)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            if cid:
                subprocess.run(["docker", "rm", "-f", cid], check=True, stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
