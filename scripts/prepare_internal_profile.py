"""Generate owner-only files for an isolated, authenticated single-host pilot."""
import argparse
import json
import os
import secrets
from pathlib import Path

ROLES = {
    "requester": (["capability.goal.create", "capability.goal.submit", "capability.goal.status"], []),
    "ingester": (["capability.memory.write"], []),
    "coordinator": (["goal.broadcast", "goal.assignment.*", "capability.auction.execute.>", "skill.reflection"],
                    ["capability.goal.*", "capability.reflection.status", "goal.proposal.*"]),
    "context": (["capability.memory.query"], ["capability.reasoning.prepare_context"]),
    "memory": ([], ["capability.memory.query", "capability.memory.write"]),
    "reasoning": (["capability.reasoning.prepare_context"], ["capability.reasoning.llm"]),
    "worker-memory": (["goal.proposal.*", "capability.memory.query"],
                      ["goal.broadcast", "goal.assignment.worker-memory", "capability.auction.execute.worker-memory.*"]),
    "worker-reasoning": (["goal.proposal.*", "capability.reasoning.llm"],
                         ["goal.broadcast", "goal.assignment.worker-reasoning", "capability.auction.execute.worker-reasoning.*"]),
}


def prepare(root, roles=None):
    root = Path(root).resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.chmod(root, 0o700)
    users = []
    for role, (publish, subscribe) in (ROLES if roles is None else roles).items():
        auth = {"user": role, "password": secrets.token_urlsafe(32)}
        path = root / (role + ".json")
        path.write_text(json.dumps(auth))
        os.chmod(path, 0o600)
        permissions = {"publish": {"allow": publish} if publish else {"deny": [">"]},
                       "subscribe": {"allow": subscribe + ["_INBOX." + role + ".>"]},
                       "allow_responses": {"max": 1, "expires": "240s"}}
        if role in ("requester", "ingester"):
            permissions.pop("allow_responses")
        users.append({**auth, "permissions": permissions})
    config = root / "nats.json"
    config.write_text(json.dumps({"listen": "0.0.0.0:4222", "max_payload": 1048576,
                                 "authorization": {"users": users}}, indent=2))
    os.chmod(config, 0o600)
    return root

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    prepare(args.directory)
    print("Prepared private authentication files; do not commit or print their contents.")
