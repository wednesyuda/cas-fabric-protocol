"""Negative authorization checks on the dedicated profile's NATS instance."""
import asyncio
import json
import os
import sys
from pathlib import Path
import nats
from nats.errors import AuthorizationError
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reference/python"))
from fabric_nats import NATSFabric

async def main(root, url):
    root=Path(root); errors=[]
    async def error(exc): errors.append(str(exc))
    async def connect(role):
        auth=json.loads((root/(role+".json")).read_text())
        return await nats.connect(url,user=auth["user"],password=auth["password"],
                                  inbox_prefix="_INBOX."+role,error_cb=error,max_reconnect_attempts=0)
    requester=await connect("requester");memory=await connect("memory")
    worker=await connect("worker-memory")
    try:
        rejected=False
        try: await asyncio.wait_for(nats.connect(url,user="requester",password="wrong",max_reconnect_attempts=1,error_cb=error),timeout=3)
        except Exception:
            rejected=any("authorization" in item.lower() for item in errors)
        assert rejected
        checks=0
        for subject in ("goal.assignment.worker-memory","goal.proposal.fake","capability.memory.write","capability.goal.complete","capability.reasoning.llm"):
            before=len(errors);await requester.publish(subject,b'{}');await requester.flush();await asyncio.sleep(.05)
            assert len(errors)>before, subject
            checks+=1
        before=len(errors)
        await worker.subscribe("capability.auction.execute.worker-reasoning.*")
        await worker.flush();await asyncio.sleep(.05)
        assert len(errors)>before
        before=len(errors)
        await requester.subscribe("_INBOX.coordinator.>")
        await requester.flush();await asyncio.sleep(.05)
        assert len(errors)>before
        async def answer(msg): await msg.respond(b'{"ok":true}')
        await memory.subscribe("capability.memory.query",cb=answer);await memory.flush()
        context=await connect("context")
        try:
            response=await context.request("capability.memory.query",b'{}',timeout=1)
            assert json.loads(response.data)["ok"]
        finally: await context.close()
        print(json.dumps({"invalid_credentials_rejected":True,"requester_forbidden_publish_checks":checks,
                          "other_worker_subject_denied":True,"other_role_inbox_denied":True,
                          "authorized_request_reply_pass":True}))
    finally: await requester.close();await memory.close();await worker.close()
if __name__=="__main__":asyncio.run(main(sys.argv[1],sys.argv[2]))
