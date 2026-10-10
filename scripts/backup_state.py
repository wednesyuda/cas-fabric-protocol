"""Quiescent JSON/Qdrant snapshots; refuses overwrite and active store owners."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import quote
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"reference/python"))
from state_lock import StateLocks


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def backup(goals,reflections,url,output):
    output=Path(output)
    with StateLocks([goals,reflections]),httpx.Client(base_url=url,timeout=60) as client:
        output.mkdir(mode=0o700,parents=True,exist_ok=False)
        manifest={"state":"quiescent operator snapshot","files":{},"collections":{},"qdrant":client.get("/").json()}
        for name,source in (("goals.json",goals),("reflections.json",reflections)):
            data=Path(source).read_bytes();json.loads(data)
            (output/name).write_bytes(data);manifest["files"][name]=digest(output/name)
        response=client.get("/collections");response.raise_for_status()
        for index,item in enumerate(response.json()["result"]["collections"]):
            name=item["name"];encoded=quote(name,safe="")
            info=client.get("/collections/"+encoded);info.raise_for_status()
            snapshot=client.post(f"/collections/{encoded}/snapshots");snapshot.raise_for_status()
            snapshot_name=snapshot.json()["result"]["name"]
            filename=f"collection-{index}.snapshot"
            with client.stream("GET",f"/collections/{encoded}/snapshots/{quote(snapshot_name,safe='')}") as data:
                data.raise_for_status()
                with (output/filename).open("wb") as stream:
                    for block in data.iter_bytes():stream.write(block)
            manifest["files"][filename]=digest(output/filename)
            manifest["collections"][name]={"snapshot":filename,"vectors":info.json()["result"]["config"]["params"]["vectors"],
                                            "points_count":info.json()["result"]["points_count"]}
        (output/"manifest.json").write_text(json.dumps(manifest,indent=2))
        return manifest


def restore(backup_dir,state_dir,url):
    backup_dir=Path(backup_dir).resolve();state_dir=Path(state_dir)
    manifest=json.loads((backup_dir/"manifest.json").read_text())
    if not {"goals.json","reflections.json"}.issubset(manifest["files"]):
        raise ValueError("backup missing state files")
    if any(info["snapshot"] not in manifest["files"] for info in manifest["collections"].values()):
        raise ValueError("collection snapshot missing from verified files")
    for name,expected in manifest["files"].items():
        path=(backup_dir/name).resolve()
        if path.parent!=backup_dir or digest(path)!=expected:raise ValueError("backup hash/path validation failed")
    with httpx.Client(base_url=url,timeout=120) as client:
        response=client.get("/collections");response.raise_for_status()
        if response.json()["result"]["collections"]:raise ValueError("restore requires empty Qdrant instance")
        if state_dir.exists():raise ValueError("restore requires new state directory")
        live=client.get("/");live.raise_for_status()
        if live.json().get("version")!=manifest["qdrant"].get("version"):
            raise ValueError("restore drill requires the exact pinned Qdrant version")
        state_dir.mkdir(mode=0o700,parents=True)
        for name in ("goals.json","reflections.json"):(state_dir/name).write_bytes((backup_dir/name).read_bytes())
        for name,info in manifest["collections"].items():
            encoded=quote(name,safe="")
            result=client.put("/collections/"+encoded,json={"vectors":info["vectors"]});result.raise_for_status()
            with (backup_dir/info["snapshot"]).open("rb") as stream:
                result=client.post(f"/collections/{encoded}/snapshots/upload?priority=snapshot",files={"snapshot":stream})
                result.raise_for_status()
            result=client.get("/collections/"+encoded);result.raise_for_status()
            if result.json()["result"]["points_count"]!=info["points_count"]:
                raise ValueError("restored collection count mismatch")
    return manifest

if __name__=="__main__":
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest="mode",required=True)
    b=sub.add_parser("backup");b.add_argument("--goals",required=True);b.add_argument("--reflections",required=True)
    b.add_argument("--qdrant-url",required=True);b.add_argument("--output",required=True)
    r=sub.add_parser("restore");r.add_argument("--backup",required=True);r.add_argument("--state",required=True);r.add_argument("--qdrant-url",required=True)
    args=parser.parse_args()
    if args.mode=="backup":backup(args.goals,args.reflections,args.qdrant_url,args.output)
    else:restore(args.backup,args.state,args.qdrant_url)
    print("PASS",args.mode,"state and collection snapshot checks")
