"""Linux isolated release gate. Requires Docker; never uses default service ports."""
import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYREF = ROOT / "reference" / "python"
sys.path.insert(0, str(PYREF))
sys.path.insert(0, str(ROOT / "tests"))
from fabric_nats import NATSFabric
from auction_probe import ProbeWorker
from release_identity import environment_identity, source_identity

NATS_IMAGE = "nats@sha256:7ff2e641c33dbdb0dd13a943ba0b70d841b71275c607baa53ef9b8661f0b2d8c"
QDRANT_IMAGE = "qdrant/qdrant@sha256:75eab8c4ba42096724fdcfde8b4de0b5713d529dde32f285a1f86fdcb2c9e50c"


async def ready():
    fabric = NATSFabric()
    await fabric.connect()
    try:
        for _ in range(60):
            response = await fabric.request("memory.query", {"query": "ready", "limit": 1})
            if response and response.get("ok"):
                return
            await asyncio.sleep(1)
        raise RuntimeError("memory readiness deadline exceeded")
    finally:
        await fabric.close()


async def resilience(coordinator, restart, containers):
    fabric = NATSFabric()
    winner = ProbeWorker("probe-winner", 1, blocking=True)
    loser = ProbeWorker("probe-loser", 1000)
    await fabric.connect()
    try:
        assert await fabric.request("nonexistent.release.capability", {}, timeout=0.1) is None
        created = await asyncio.gather(*[fabric.request("goal.create", {
            "intent": f"Load test {i}", "required_skills": ["memory.query"]}) for i in range(100)])
        ids = [item["goal"]["goal_id"] for item in created if item and item.get("ok")]
        assert len(set(ids)) == 100, "concurrent goal writes lost or duplicated"
        bad = await fabric.request("goal.update", {"goal_id": ids[0], "patch": {"state": "invented"}})
        assert bad and not bad["ok"]
        failure = await fabric.request("goal.submit", {
            "intent": "Unsupported skill", "required_skills": ["nonexistent.skill"],
            "proposal_window_ms": 10})
        assert failure and not failure["ok"] and failure["goal"]["state"] == "failed"
        await winner.start()
        await loser.start()
        routed = await fabric.request("goal.submit", {"intent": "Distinct worker outputs",
            "required_skills": ["release.echo"], "proposal_window_ms": 200}, timeout=10)
        assert routed["ok"] and routed["valid_proposal_count"] == 2
        assert routed["assignments"][0]["node_id"] == winner.node_id
        assert routed["execution"][0]["response"]["output"] == winner.node_id
        assert len(winner.calls) == 1 and not loser.calls
        block = await fabric.request("goal.create", {"intent": "Actual blocked execution",
            "required_skills": ["release.block"]})
        interrupted_id = block["goal"]["goal_id"]
        pending = asyncio.create_task(fabric.request("goal.submit", {"goal_id": interrupted_id,
            "proposal_window_ms": 200}, timeout=2))
        await asyncio.wait_for(winner.started.wait(), timeout=10)
        in_progress = await fabric.request("goal.status", {"goal_id": interrupted_id})
        assert in_progress["goal"]["state"] == "executing"
        # Kill only the coordinator created by this test, while a real worker is blocked.
        coordinator.kill()
        coordinator.wait(timeout=15)
        await pending
        restart()
        for _ in range(30):
            restored = await fabric.request("goal.status", {"goal_id": ids[0]})
            if restored and restored.get("ok"):
                break
            await asyncio.sleep(0.2)
        assert restored["goal"]["state"] == "created", "restart lost durable goal"
        interrupted = await fabric.request("goal.status", {"goal_id": interrupted_id})
        assert interrupted["goal"]["state"] == "failed"
        assert interrupted["goal"]["history"][-1]["metadata"]["reason"] == "coordinator_restart"
        winner.release.set()
        await asyncio.wait_for(winner.finished.wait(), timeout=5)
        assert len([call for call in winner.calls if call[0] == "release.block"]) == 1
        after = await fabric.request("goal.status", {"goal_id": interrupted_id})
        assert after["goal"]["state"] == "failed", "late worker result rewrote recovered goal"
        token = "Release persistence " + uuid.uuid4().hex
        written = await fabric.request("memory.write", {"content": token, "memory_type": "semantic"})
        assert written["ok"]
        await asyncio.to_thread(subprocess.run, ["docker", "restart", containers[1]], check=True,
                                stdout=subprocess.DEVNULL)
        await ready()
        memory = await fabric.request("memory.query", {"query": token, "limit": 20})
        assert any(item["content"] == token for item in memory["results"]), "vector store restart lost memory"
        await asyncio.to_thread(subprocess.run, ["docker", "restart", containers[0]], check=True,
                                stdout=subprocess.DEVNULL)
        for _ in range(60):
            try:
                recovered = await fabric.request("goal.status", {"goal_id": ids[0]}, timeout=1)
                if recovered and recovered.get("ok"):
                    break
            except Exception:
                recovered = None
            await asyncio.sleep(0.5)
        assert recovered and recovered["ok"], "bus reconnect lost subscriptions"
        return {"concurrent_creates": 100, "unique_ids": 100, "invalid_update_rejected": True,
                "unavailable_capability": "None", "unassigned_goal": "failed",
                "coordinator_restart_preserved_goal": True, "interrupted_goal_failed_without_replay": True,
                "actual_worker_interruption": True, "late_worker_result_preserves_failed_goal": True,
                "two_worker_selection_and_execution": True, "losing_worker_execution_count": 0,
                "vector_store_restart_preserved_memory": True, "bus_restart_recovered_subscriptions": True}
    finally:
        winner.release.set()
        await winner.close()
        await loser.close()
        await fabric.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-url", help="Optional existing ISOLATED Ollama-compatible provider")
    parser.add_argument("--model", default="fixture")
    parser.add_argument("--provider-manifest", type=Path,
                        help="Required for a real provider: JSON model digest, adapter hashes and effective options")
    parser.add_argument("--provider-source", type=Path, action="append", default=[],
                        help="Snapshot an actual adapter source; its basename and hash must match the manifest")
    args = parser.parse_args()
    identity = source_identity(ROOT)
    if args.model_url and args.provider_manifest is None:
        parser.error("real provider requires --provider-manifest for reproducible evidence")
    provider = {"kind": "deterministic fixture", "quality_benchmark": False}
    if args.provider_manifest:
        provider = json.loads(args.provider_manifest.read_text())
        if provider.get("model") != args.model or not provider.get("model_digest"):
            raise ValueError("provider manifest must identify the requested model and digest")
    snapshots = {}
    for path in args.provider_source:
        if path.name in snapshots:
            raise ValueError("duplicate provider source basename")
        snapshots[path.name] = path.read_bytes()
    expected_sources = provider.get("source_sha256", {})
    actual_sources = {name: hashlib.sha256(data).hexdigest() for name, data in snapshots.items()}
    if actual_sources != expected_sources:
        raise ValueError("provider sources do not match declared source hashes")
    if args.provider_manifest:
        provider["manifest_sha256"] = hashlib.sha256(args.provider_manifest.read_bytes()).hexdigest()
    run = ROOT / "release-evidence" / uuid.uuid4().hex[:12]
    run.mkdir(parents=True)
    (run / "source-manifest.json").write_text(json.dumps(identity, indent=2))
    (run / "provider-manifest.json").write_text(json.dumps(provider, indent=2))
    if snapshots:
        snapshot_dir = run / "provider-sources"
        snapshot_dir.mkdir()
        for name, data in snapshots.items():
            (snapshot_dir / name).write_bytes(data)
    env = dict(os.environ, CAS_NATS_URL="nats://127.0.0.1:19022",
               CAS_QDRANT_URL="http://127.0.0.1:19033",
               CAS_OLLAMA_URL=args.model_url or "http://127.0.0.1:19034",
               CAS_REASONING_MODEL=args.model, CAS_EMBED_MODEL="nomic-embed-text:v1.5",
               CAS_GOAL_STORE_PATH=str(run / "goals.json"),
               CAS_REFLECTION_STORE_PATH=str(run / "reflections.json"))
    os.environ.update({k: v for k, v in env.items() if k.startswith("CAS_")})
    containers = []
    processes = []
    streams = []

    def launch(script, extra=None):
        stream = (run / (Path(script).stem + f"-{len(processes)}.log")).open("w")
        streams.append(stream)
        process = subprocess.Popen([sys.executable, script], env={**env, **(extra or {})},
                                   stdout=stream, stderr=subprocess.STDOUT)
        processes.append(process)
        return process

    try:
        for service, image, port in (("nats", NATS_IMAGE, "19022:4222"),
                                     ("qdrant", QDRANT_IMAGE, "19033:6333")):
            name = f"cas-release-{run.name}-{service}"
            created = subprocess.run(["docker", "create", "--name", name, "--memory", "512m",
                            "--cpus", "1", "-p", f"127.0.0.1:{port}", image], check=True,
                            capture_output=True, text=True)
            container_id = created.stdout.strip()
            containers.append(container_id)
            subprocess.run(["docker", "start", container_id], check=True, stdout=subprocess.DEVNULL)
        if not args.model_url:
            launch(str(ROOT / "tests" / "model_fixture.py"))
        time.sleep(3)
        for script in ("milestone0_node_service.py", "canonical_memory_node_service.py",
                       "context_preparation_service.py", "reasoning_node_service.py"):
            launch(str(PYREF / script))
        coordinator = launch(str(PYREF / "task_coordinator_service.py"))
        for skill in ("memory.query", "reasoning.llm"):
            launch(str(PYREF / "auction_worker_node_service.py"), {
                "CAS_WORKER_ID": "release-worker-" + skill, "CAS_WORKER_SKILLS": skill})
        asyncio.run(ready())
        with (run / "compliance.log").open("w") as stream:
            subprocess.run([sys.executable, str(PYREF / "verify_compliance_runtime.py")],
                           env=env, stdout=stream, stderr=subprocess.STDOUT, check=True, timeout=1200)
        outcome = asyncio.run(resilience(coordinator, lambda: launch(str(PYREF / "task_coordinator_service.py")), containers))
        (run / "summary.json").write_text(json.dumps({"provider": "real" if args.model_url else "fixture",
            "model": args.model, "candidate_commit": identity["commit"],
            "source_sha256": identity["source_sha256"], "environment": environment_identity(),
            "images": {"nats": NATS_IMAGE, "qdrant": QDRANT_IMAGE}, "provider_profile": provider,
            "M0_M6": "pass", "resilience": outcome}, indent=2))
        print("PASS release gate:", run)
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        for stream in streams:
            stream.close()
        cleanup_failed = []
        for container_id in containers:
            result = subprocess.run(["docker", "rm", "-f", container_id], stdout=subprocess.DEVNULL)
            if result.returncode:
                cleanup_failed.append(container_id)
        if cleanup_failed:
            raise RuntimeError(f"test container cleanup failed: {cleanup_failed}")


if __name__ == "__main__":
    main()
