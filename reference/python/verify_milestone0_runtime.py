"""
Runtime canary for Milestone 0 production verification.

The check passes only if a live CAS Fabric node emits an autonomic
health pulse over the real NATS bus.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime

from fabric_nats import NATSFabric


async def main() -> int:
    fabric = NATSFabric()
    await fabric.connect(connect_timeout=5.0)

    received: list[dict] = []

    await fabric.subscribe_async(
        "autonomic.health",
        lambda msg: received.append(msg["payload"]),
    )

    deadline = asyncio.get_running_loop().time() + 12.0
    while asyncio.get_running_loop().time() < deadline:
        if received:
            pulse = received[-1]
            required = {"node_id", "timestamp", "status", "load", "version", "active_skill_count"}
            missing = sorted(required - set(pulse))
            if missing:
                print("FAIL missing_fields=" + ",".join(missing))
                await fabric.close()
                return 1
            if pulse["status"] != "healthy":
                print("FAIL unhealthy_pulse=" + json.dumps(pulse, sort_keys=True))
                await fabric.close()
                return 1
            if int(pulse.get("active_skill_count", 0)) < 1:
                await asyncio.sleep(0.25)
                continue
            try:
                datetime.fromisoformat(str(pulse["timestamp"]).replace("Z", "+00:00"))
            except ValueError:
                print("FAIL timestamp_not_iso8601=" + json.dumps(pulse, sort_keys=True))
                await fabric.close()
                return 1
            print("PASS health_pulse=" + json.dumps(pulse, sort_keys=True))
            await fabric.close()
            return 0
        await asyncio.sleep(0.25)

    print("FAIL no_autonomic_health_pulse_within_12s")
    await fabric.close()
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
