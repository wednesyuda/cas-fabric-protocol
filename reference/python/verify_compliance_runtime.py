"""
Runtime compliance runner for the CAS Fabric protocol seed.

Runs all milestone canaries in order and returns non-zero if any
milestone fails. This is intentionally a thin wrapper around the
existing runtime canaries so each milestone remains independently useful.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path


CANARIES = [
    ("M0", "verify_milestone0_runtime.py"),
    ("M1", "verify_milestone1_canonical_runtime.py"),
    ("M2", "verify_milestone2_runtime.py"),
    ("M3", "verify_milestone3_runtime.py"),
    ("M4", "verify_milestone4_runtime.py"),
    ("M5", "verify_milestone5_runtime.py"),
    ("M6", "verify_milestone6_runtime.py"),
]


def main() -> int:
    root = Path(__file__).resolve().parent
    results = []
    started = time.time()
    for milestone, script_name in CANARIES:
        script = root / script_name
        step_started = time.time()
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(root),
            text=True,
            capture_output=True,
            timeout=900,
        )
        output = (proc.stdout + proc.stderr).strip()
        results.append(
            {
                "milestone": milestone,
                "script": script_name,
                "ok": proc.returncode == 0,
                "returncode": proc.returncode,
                "duration_s": round(time.time() - step_started, 3),
                "output_tail": output[-1000:],
            }
        )
        if proc.returncode != 0:
            print(
                "FAIL compliance="
                + json.dumps(
                    {
                        "failed_milestone": milestone,
                        "results": results,
                    },
                    sort_keys=True,
                )
            )
            return proc.returncode

    print(
        "PASS compliance="
        + json.dumps(
            {
                "milestones": [item["milestone"] for item in results],
                "duration_s": round(time.time() - started, 3),
                "results": results,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
