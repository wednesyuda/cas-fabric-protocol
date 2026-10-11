"""Private end-to-end QA diagnostics; candidate references require human review."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reference/python"))
from fabric_nats import NATSFabric
from prepare_internal_profile import prepare
from verify_release import NATS_IMAGE, QDRANT_IMAGE
from release_identity import source_identity


def score_response(case, response):
    """Lexical candidate-reference score, not semantic entailment approval."""
    retrieved = {item["source_id"] for item in response.get("evidence", [])}
    expected = set(case.get("source_ids", []))
    retrieval_hit = bool(expected & retrieved) if expected else None
    if case["kind"] == "unanswerable":
        passed = response.get("status") == "abstain" and not response.get("sources")
    else:
        answer = " ".join(response.get("output", "").lower().split())
        passed = (response.get("status") == "answer"
                  and bool(expected & set(response.get("sources", [])))
                  and all(any(term.lower() in answer for term in alternatives)
                          for alternatives in case["required_terms"]))
    return {"candidate_reference_pass": bool(passed), "retrieval_hit": retrieval_hit}


async def evaluate(packet, profile, output):
    os.environ["CAS_NATS_AUTH_FILE"] = str(profile / "ingester.json")
    ingester = NATSFabric()
    await ingester.connect()
    try:
        for record in packet["records"]:
            result = await ingester.request("memory.write", record, timeout=30)
            if not result or not result.get("ok"):
                raise RuntimeError("private corpus ingestion failed")
    finally:
        await ingester.close()
    os.environ["CAS_NATS_AUTH_FILE"] = str(profile / "requester.json")
    client = NATSFabric()
    await client.connect()
    rows = []
    try:
        for case in packet["cases"]:
            before = time.monotonic()
            result = await client.request("goal.submit", {
                "intent": case["question"], "required_skills": ["reasoning.llm"],
                "proposal_window_ms": 200}, timeout=120)
            executions = result.get("execution", []) if result else []
            response = executions[0].get("response", {}) if executions else {}
            valid = bool(result and result.get("ok") and response.get("type") == "reasoning.response"
                         and response.get("actions_allowed") is False)
            row = {"id": case["id"], "kind": case["kind"], "operational_ok": valid,
                   "elapsed_s": time.monotonic() - before, "response": response,
                   **score_response(case, response)}
            rows.append(row)
            with (output / "results.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(json.dumps({"completed": len(rows), "total": len(packet["cases"]),
                              "operational_ok": valid}), flush=True)
    finally:
        await client.close()
    facts = [row for row in rows if row["kind"] != "unanswerable"]
    return {"case_count": len(rows), "operational_errors": sum(not row["operational_ok"] for row in rows),
            "candidate_reference_pass": sum(row["candidate_reference_pass"] for row in rows),
            "retrieval_hits": sum(row["retrieval_hit"] is True for row in facts),
            "retrieval_cases": len(facts), "reference_review": packet["reference_review"],
            "human_semantic_scoring": "pending", "pilot_gate": "hold",
            "scope": "private historical facts; lexical diagnostics are not approved operational SOP"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model-url", default="http://127.0.0.1:21436")
    parser.add_argument("--model", default="qwen3:4b")
    args = parser.parse_args()
    packet = json.loads(Path(args.packet).read_text(encoding="utf-8"))
    os.umask(0o077)
    output = Path(args.output)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    (output / "source-manifest.json").write_text(json.dumps(source_identity(ROOT), indent=2))
    tag = uuid.uuid4().hex[:10]
    owned, processes, streams = [], [], []
    with tempfile.TemporaryDirectory(prefix="cas-operational-") as temp:
        profile = prepare(Path(temp) / "auth")
        env = {**os.environ, "CAS_NATS_URL": "nats://127.0.0.1:22042",
               "CAS_QDRANT_URL": "http://127.0.0.1:22043", "CAS_DOCUMENT_QA": "1",
               "CAS_OLLAMA_URL": args.model_url, "CAS_REASONING_MODEL": args.model,
               "CAS_EMBED_URL": "http://127.0.0.1:21434", "CAS_EMBED_MODEL": "nomic-embed-text:v1.5",
               "CAS_GOAL_STORE_PATH": str(output / "goals.json"),
               "CAS_REFLECTION_STORE_PATH": str(output / "reflections.json")}
        try:
            for service, image, port in [("nats", NATS_IMAGE, "22042:4222"),
                                          ("qdrant", QDRANT_IMAGE, "22043:6333")]:
                command = ["docker", "create", "--name", f"cas-operational-{tag}-{service}",
                           "--memory", "512m", "--cpus", "1", "-p", "127.0.0.1:" + port]
                if service == "nats":
                    command += ["--mount", f"type=bind,src={profile/'nats.json'},dst=/etc/nats/profile.json,readonly"]
                command += [image]
                if service == "nats":
                    command += ["-c", "/etc/nats/profile.json"]
                cid = subprocess.check_output(command, text=True).strip()
                owned.append(cid)
                subprocess.run(["docker", "start", cid], check=True, stdout=subprocess.DEVNULL)
            for script, role in [("canonical_memory_node_service.py", "memory"),
                                 ("context_preparation_service.py", "context"),
                                 ("reasoning_node_service.py", "reasoning"),
                                 ("task_coordinator_service.py", "coordinator"),
                                 ("auction_worker_node_service.py", "worker-reasoning")]:
                log = (output / (role + ".log")).open("w")
                streams.append(log)
                extra = {"CAS_NATS_AUTH_FILE": str(profile / (role + ".json"))}
                if role == "worker-reasoning":
                    extra.update(CAS_WORKER_ID=role, CAS_WORKER_SKILLS="reasoning.llm")
                processes.append(subprocess.Popen([sys.executable, str(ROOT / "reference/python" / script)],
                                 env={**env, **extra}, stdout=log, stderr=subprocess.STDOUT))
            time.sleep(5)
            if any(proc.poll() is not None for proc in processes):
                raise RuntimeError("operational staging service exited during startup")
            os.environ.update(env)
            summary = asyncio.run(evaluate(packet, profile, output))
            (output / "summary.json").write_text(json.dumps(summary, indent=2))
            print(json.dumps(summary), flush=True)
            if summary["operational_errors"] or summary["candidate_reference_pass"] != summary["case_count"]:
                raise SystemExit(1)
        finally:
            for proc in processes:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
            for stream in streams:
                stream.close()
            for cid in owned:
                subprocess.run(["docker", "rm", "-f", cid], check=True, stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
