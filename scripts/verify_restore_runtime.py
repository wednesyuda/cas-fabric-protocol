"""Owned-Qdrant restore drill, JSON recovery and real ENOSPC regression."""
import errno
import json
import os
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from types import SimpleNamespace
import time
import uuid
from pathlib import Path
from unittest.mock import patch
import httpx
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"reference/python"))
from task_coordinator_service import GoalStore,ReflectionStore
from state_lock import StateLocks
from backup_state import backup,restore
from verify_release import QDRANT_IMAGE


def main():
    tag=uuid.uuid4().hex[:10];owned=[]
    evidence=ROOT/"release-evidence"/("restore-"+tag);evidence.mkdir(parents=True)
    started=time.monotonic()
    with tempfile.TemporaryDirectory(prefix="cas-restore-") as temp:
        root=Path(temp);goals=GoalStore(str(root/"goals.json"));refs=ReflectionStore(str(root/"reflections.json"))
        goal=goals.create("RESTORE-CANARY",["memory.query"]);refs.save()
        try:
            for port in (22033,22035):
                cid=subprocess.check_output(["docker","create","--name",f"cas-restore-{tag}-{port}","--memory","512m","--cpus","1",
                       "-p",f"127.0.0.1:{port}:6333",QDRANT_IMAGE],text=True).strip();owned.append(cid)
                subprocess.run(["docker","start",cid],check=True,stdout=subprocess.DEVNULL)
            time.sleep(3)
            with httpx.Client(base_url="http://127.0.0.1:22033",timeout=30) as client:
                client.put("/collections/canary",json={"vectors":{"size":3,"distance":"Cosine"}}).raise_for_status()
                client.put("/collections/canary/points?wait=true",json={"points":[{"id":str(uuid.uuid4()),"vector":[1,0,0],
                           "payload":{"content":"RESTORE-CANARY"}}]}).raise_for_status()
            with StateLocks([goals.path,refs.path]):
                try:backup(goals.path,refs.path,"http://127.0.0.1:22033",root/"blocked")
                except RuntimeError:pass
                else:raise AssertionError("backup permitted active coordinator owner")
            backup(goals.path,refs.path,"http://127.0.0.1:22033",root/"backup")
            restore(root/"backup",root/"restored","http://127.0.0.1:22035")
            restored=GoalStore(str(root/"restored/goals.json"));restored.load()
            assert restored.get(goal["goal_id"])==goal
            with httpx.Client(base_url="http://127.0.0.1:22035",timeout=30) as client:
                points=client.post("/collections/canary/points/scroll",json={"limit":10,"with_payload":True}).json()["result"]["points"]
                assert any(point["payload"]["content"]=="RESTORE-CANARY" for point in points)
            # Verify rejection of corruption before any restore target is created.
            (root/"backup/goals.json").write_text("{}")
            try:restore(root/"backup",root/"corrupt-target","http://127.0.0.1:22035")
            except ValueError:pass
            else:raise AssertionError("corrupt snapshot accepted")
            assert not (root/"corrupt-target").exists()
            before=goals.path.read_bytes();memory=dict(goals.goals)
            @contextmanager
            def full_file(**kwargs):
                with open("/dev/full","w",encoding="utf-8") as stream:
                    yield SimpleNamespace(name=str(root/"owned-failed-temp"),write=stream.write,
                                          flush=stream.flush,fileno=stream.fileno)
            try:
                with patch("task_coordinator_service.tempfile.NamedTemporaryFile",side_effect=full_file):
                    try:goals.create("must not persist",["memory.query"])
                    except OSError as exc:assert exc.errno==errno.ENOSPC
                    else:raise AssertionError("ENOSPC not observed")
            finally:
                pass
            assert goals.path.read_bytes()==before and goals.goals==memory
            result={"restored_goal_and_history":"pass","restored_qdrant_canary":"pass","active_owner_backup_rejected":True,
                    "corrupt_snapshot_rejected":True,"actual_ENOSPC_preserves_state":True,"restore_elapsed_s":time.monotonic()-started,
                    "scope":"isolated data restore, not host reboot or production rollback"}
            (evidence/"summary.json").write_text(json.dumps(result,indent=2));print(json.dumps(result))
        finally:
            for cid in owned:subprocess.run(["docker","rm","-f",cid],check=True,stdout=subprocess.DEVNULL)
if __name__=="__main__":main()
