# CAS Fabric reference candidate assessment

> Historical assessment, superseded by the 2026-10-10 Astra audit and fixes.
> The original beta verdict missed editable in-flight intents and generic-provider
> execution that did not bind work to the auction winner. Evidence below applies
> only to the earlier source, not the current candidate.

Verdict: **beta reference candidate prepared for maintainer review**. Stable
production release is **not ready**. No tag, upstream push, hosted CI run or
production deployment was performed.

Baseline: `f42dfee96d92cbc7b5e4a582a20f976c82d7eefe`.
Workflow: Addy Osmani agent-skills `1401c8b8030e023baeebb31781a6653fe8e93026`.
Candidate source, tests, dependency lock, CI workflow and rollout limits are included
in this checkout. See [release readiness](../docs/release-readiness.md).

## Verification

| Gate | Actual evidence | Result |
| --- | --- | --- |
| Regression/schema tests | Python 3.12 on Windows and Linux; 34 tests and 37 subtests | Pass |
| Fatal lint and compile | `make check` with Ruff E9/F63/F7/F82, compileall and schemas | Pass |
| Changed runtime line coverage | 106/113 executable added lines intersected with coverage JSON | 93.81% |
| Assertion strength | Inverting lifecycle guard causes 17 failing tests; original restored | Caught |
| Runtime dependency audit | pip-audit on generated complete nine-package lock | No known vulnerabilities |
| Deterministic integration | Real isolated NATS/Qdrant and model transport fixture; M0–M6 | Pass |
| Real-model integration | Same isolated protocol runtime through Qwen3 4B provider; M0–M6 | Pass |
| Concurrent creation | 100 distinct goals, persistent and queryable | Pass |
| Failure handling | Invalid update rejected; unknown capability returns None; absent skills yield failed goal | Pass |
| Coordinator recovery | Created goal persists; executing goal becomes failed without replay | Pass |
| Qdrant recovery | Written memory remains queryable after container restart | Pass |
| NATS recovery | Capability subscriptions recover after bus restart | Pass |
| Harness cleanup | All owned containers/processes removed; startup-failure unit regression | Pass |
| Separate review | Reproduction-test worker and subsequent read-only review; findings fixed and guarded | No remaining required finding in beta scope |

Evidence IDs: real-model `76c8fd0e5e38`, final fixture `2c51a9e12679`.
Raw operator logs remain local in ignored `release-evidence/`. The last harness
change concerns startup cleanup only and was verified by the final fixture gate;
the real-model run used the same final reference service code.

## What changed and why

NATS defaults now honor the configured test bus so services cannot silently use
the default production bus. Malformed input and absent responders no longer break
the documented transport behavior. Temporary auction subscriptions are released.

Goal fields and transitions are validated before mutation. Atomic JSON replacement
and copied metadata keep the stored audit history consistent when a write fails or
a caller changes its own input. Reflection uses the same commit-before-publish
principle. Repeated submissions cannot execute an existing goal again. In-flight
goals fail on restart because blindly retrying may duplicate external side effects.

Model HTTP no longer blocks the asyncio event loop. Empty generation and mismatched
prepared intent become explicit failures. Query limits and proposal windows are
bounded. This is not a confidence or authorization system.

Review found additional failure paths: mutable metadata, unsubscribe failure,
concurrent terminal updates, reflection commit failure and container startup cleanup.
Each actionable issue was fixed and regression coverage added. Review is a separate
context using the same model family, not an independent cross-model certification.

## Limits

M0–M6 assert selected milestone properties, not full semantic protocol conformance.
The deterministic provider does not validate model quality. The previous synthetic
knowledge pilot's 30/30 result was not rerun against this release reference and is
not claimed as this candidate's accuracy score.

RFCs remain Draft. The reference lacks the complete canonical reasoning-response
envelope, calibrated confidence and enforced action/review gates, authenticated
worker identity, multi-tenant isolation, high-concurrency backpressure and production
SLO/soak evidence. One trusted coordinator owns its store paths. See the deployment
boundary and stable-release blockers in the readiness document.

A hosted CI execution and maintainer approval remain required before merging or
publishing. Public release and production rollout require their own evidence and
authorization; preparing this candidate does not perform either.

Existing production model process IDs/start times stayed unchanged and health
remained OK during verification. All test infrastructure used separate loopback
ports and stores.
