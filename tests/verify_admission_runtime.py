"""Controlled real-NATS regression, no model/GPU or operational documents."""
import asyncio
import json
import sys
import threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reference/python"))
from fabric_nats import NATSFabric
import reasoning_node_service as reasoning

async def main():
    release, entered = threading.Event(), threading.Event()
    calls = []
    def provider(prompt):
        calls.append(prompt); entered.set(); release.wait(5); return "synthetic result"
    reasoning.ollama_generate = provider
    node, client = reasoning.ReasoningNode(), NATSFabric()
    await node.fabric.connect(); await client.connect()
    await node.fabric.subscribe_async("capability.reasoning.llm", node.handle_reasoning,
                                      max_active=1,max_queued=1,max_queue_wait=1)
    def payload(intent):
        return {"intent":intent,"reasoning_request":{"intent":intent,
                "values_signature":{"values_consulted":True},"prepared_context":{}}}
    try:
        first=asyncio.create_task(client.request("reasoning.llm",payload("first"),timeout=.2))
        for _ in range(100):
            if entered.is_set():break
            await asyncio.sleep(.01)
        assert entered.is_set()
        second=asyncio.create_task(client.request("reasoning.llm",payload("second"),timeout=.1))
        await asyncio.sleep(.02)
        busy=await client.request("reasoning.llm",payload("third"),timeout=.1)
        assert busy["code"]=="busy"
        await asyncio.gather(first,second)
        assert len(calls)==1
        release.set()
        await asyncio.gather(*list(node.fabric._dispatch_tasks))
        assert len(calls)==1, "expired queued request invoked provider"
        print(json.dumps({"expired_queued_provider_calls":0,"overload":"busy",
                          "inflight_provider_retained_slot":True,"metrics":node.fabric.admission_metrics}))
    finally:
        release.set(); await node.close(); await client.close()
if __name__=="__main__":asyncio.run(main())
