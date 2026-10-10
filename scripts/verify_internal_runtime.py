"""Authenticated isolated full-stack gate. Linux/Docker; owned resources only."""
import argparse
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"reference/python"))
from fabric_nats import NATSFabric
from prepare_internal_profile import prepare
from verify_release import NATS_IMAGE,QDRANT_IMAGE

async def query(profile, evidence, count=1, interval=0, duration=0, real=False):
    os.environ["CAS_NATS_AUTH_FILE"]=str(profile/"ingester.json")
    ingester=NATSFabric();await ingester.connect()
    try:
        written=await ingester.request("memory.write", {"content":"Isolated smoke test has code SMOKE-24.",
               "memory_type":"semantic","metadata":{"source_id":"DOC-SMOKE"}},timeout=10)
        assert written and written["ok"], written
    finally: await ingester.close()
    os.environ["CAS_NATS_AUTH_FILE"]=str(profile/"requester.json")
    client=NATSFabric(); await client.connect()
    try:
        latencies=[];errors=0;statuses={};started=time.monotonic();index=0
        while index<count or (duration and time.monotonic()-started<duration):
            before=time.monotonic()
            result=await client.request("goal.submit",{"intent":"Apa kode isolated smoke test dalam dokumen?",
                       "required_skills":["reasoning.llm"],"proposal_window_ms":200},timeout=120)
            elapsed=time.monotonic()-before;latencies.append(elapsed);index+=1
            valid=bool(result and result.get("ok"))
            if valid:
                response=result["execution"][0]["response"]
                valid=(response.get("type")=="reasoning.response" and response.get("actions_allowed") is False)
                status=response.get("status","invalid")
                statuses[status]=statuses.get(status,0)+1
                if not real:
                    assert response["status"]=="answer" and response["sources"]==["DOC-SMOKE"]
            if not valid:errors+=1
            with (evidence/"workload.jsonl").open("a") as stream:
                sample={"index":index,"elapsed_s":elapsed,"ok":valid,"host_load":os.getloadavg(),"unix_time":time.time()}
                gpu=subprocess.run(["nvidia-smi","--query-gpu=name,memory.total,memory.used,utilization.gpu","--format=csv,noheader,nounits"],
                                   capture_output=True,text=True,timeout=10) if real else None
                if gpu and gpu.returncode==0:sample["gpu"]=gpu.stdout.strip().splitlines()
                stream.write(json.dumps(sample)+"\n")
            if interval and (index<count or duration and time.monotonic()-started<duration):
                await asyncio.sleep(max(0,interval-elapsed))
        ordered=sorted(latencies)
        def percentile(p):return ordered[min(len(ordered)-1,int((len(ordered)-1)*p))]
        return {"authenticated_goal_lifecycle":"pass" if not errors else "fail","selected_worker":"worker-reasoning",
                "document_mode_citations":"validated at response boundary","actions_allowed":False,
                "accepted_requests":index,"operational_errors":errors,"statuses":statuses,
                "latency_s":{"p50":percentile(.5),"p95":percentile(.95),"p99":percentile(.99)},
                "duration_s":time.monotonic()-started,"quality_scope":"synthetic canary, not real-document accuracy"}
    finally: await client.close()

def save_result(evidence, result):
    (evidence/"summary.json").write_text(json.dumps(result,indent=2))
    print(json.dumps({**result,"evidence":str(evidence)}))
    if result["operational_errors"] > 0 or result["authenticated_goal_lifecycle"] != "pass":
        raise SystemExit(1)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--model-url");parser.add_argument("--embed-url");parser.add_argument("--model",default="qwen3:4b")
    parser.add_argument("--embed-model",default="nomic-embed-text:v1.5")
    parser.add_argument("--count",type=int,default=1);parser.add_argument("--interval",type=float,default=0)
    parser.add_argument("--duration",type=float,default=0)
    args=parser.parse_args()
    if args.count<1 or args.interval<0 or args.duration<0:parser.error("invalid workload parameters")
    if args.model_url and not args.embed_url:parser.error("real model requires separate embedding URL")
    tag=uuid.uuid4().hex[:10]; owned=[]; processes=[]; streams=[]
    evidence=ROOT/"release-evidence"/("internal-"+tag);evidence.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="cas-profile-") as temp:
        profile=prepare(Path(temp)/"auth")
        env={**os.environ,"CAS_NATS_URL":"nats://127.0.0.1:22022","CAS_QDRANT_URL":"http://127.0.0.1:22033",
             "CAS_OLLAMA_URL":"http://127.0.0.1:19034","CAS_REASONING_MODEL":"fixture","CAS_DOCUMENT_QA":"1",
             "CAS_GOAL_STORE_PATH":str(evidence/"goals.json"),"CAS_REFLECTION_STORE_PATH":str(evidence/"reflections.json")}
        if args.model_url:
            env.update(CAS_OLLAMA_URL=args.model_url,CAS_EMBED_URL=args.embed_url,
                       CAS_EMBED_MODEL=args.embed_model,CAS_REASONING_MODEL=args.model)
        def start(script,role=None):
            log=(evidence/(Path(script).stem+"-"+str(len(processes))+".log")).open("w");streams.append(log)
            extra={"CAS_NATS_AUTH_FILE":str(profile/(role+".json"))} if role else {}
            if role and role.startswith("worker-"):extra.update(CAS_WORKER_ID=role,CAS_WORKER_SKILLS="memory.query" if role.endswith("memory") else "reasoning.llm")
            proc=subprocess.Popen([sys.executable,str(script)],env={**env,**extra},stdout=log,stderr=subprocess.STDOUT);processes.append(proc)
        try:
            for service,image,port,extra in [("nats",NATS_IMAGE,"22022:4222",["--mount",f"type=bind,src={profile/'nats.json'},dst=/etc/nats/profile.json,readonly"]),
                                             ("qdrant",QDRANT_IMAGE,"22033:6333",[])]:
                cmd=["docker","create","--name",f"cas-internal-{tag}-{service}","--memory","512m","--cpus","1","-p","127.0.0.1:"+port,*extra,image]
                if service=="nats":cmd += ["-c","/etc/nats/profile.json"]
                cid=subprocess.check_output(cmd,text=True).strip();owned.append(cid)
                subprocess.run(["docker","start",cid],check=True,stdout=subprocess.DEVNULL)
            if not args.model_url:
                start(ROOT/"tests/model_fixture.py")
            for script,role in [("canonical_memory_node_service.py","memory"),("context_preparation_service.py","context"),
                                ("reasoning_node_service.py","reasoning"),("task_coordinator_service.py","coordinator"),
                                ("auction_worker_node_service.py","worker-memory"),("auction_worker_node_service.py","worker-reasoning")]:
                start(ROOT/"reference/python"/script,role)
            time.sleep(5)
            os.environ.update(env)
            (evidence/"running.json").write_text(json.dumps({"pid":os.getpid(),"duration_s":args.duration,
                    "request_count":args.count,"interval_s":args.interval,"started_at":time.time(),"real_model":bool(args.model_url)}))
            print("RUNNING",evidence,flush=True)
            result=asyncio.run(query(profile,evidence,args.count,args.interval,args.duration,bool(args.model_url)))

            save_result(evidence, result)
        finally:
            for proc in processes:
                if proc.poll() is None:
                    proc.terminate()
                    try:proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:proc.kill();proc.wait()
            for stream in streams:stream.close()
            for cid in owned:subprocess.run(["docker","rm","-f",cid],check=True,stdout=subprocess.DEVNULL)
if __name__=="__main__":main()
