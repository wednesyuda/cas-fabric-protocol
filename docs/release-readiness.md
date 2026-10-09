# Reference release candidate

Candidate: **v0.1.0-beta.1** (reference runtime). RFCs remain Draft. This is a
single-owner, trusted-network protocol reference, not a production control plane.
The RFC versions are unchanged. The reference auction now adds an opaque
`execution_capability` to proposals and assignments. Upgrade coordinator and
workers together: older workers without this route fail execution rather than
falling back to a generic provider.

## Acceptance criteria

- Unit/regression and schema checks pass on Python 3.12.
- Fatal Python lint rules pass; source compiles.
- New runtime logic has at least 80% changed-line coverage.
- Runtime dependency versions are resolved in `reference/python/requirements.lock`;
  `pip-audit` reports no known vulnerabilities for that complete runtime graph.
- M0–M6 pass on isolated NATS/Qdrant with a deterministic provider and a real model.
- 100 concurrent goal creations retain distinct, persistent IDs.
- Unknown capabilities return `None`; invalid updates and duplicate submissions
  cannot corrupt lifecycle history or repeat execution.
- Editing intent, required skills and priority is rejected after leaving `created`.
- With two distinct worker outputs, the winning worker executes and the loser does not.
- Restart during an actual blocked worker execution preserves created goals and memory; interrupted goals become failed,
  queryable records without automatically replaying external work.
- NATS reconnect restores capability subscriptions; test infrastructure is cleaned up.
- Changes are reviewed separately; no public release or production rollout occurs
  before maintainer review.

## Reproduce

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r reference/python/requirements.lock -r requirements-dev.txt
make check PYTHON=.venv/bin/python
.venv/bin/python -m pip_audit -r reference/python/requirements.lock --no-deps --disable-pip
.venv/bin/python scripts/verify_release.py
```

The last command requires Linux and Docker. It creates new containers with unique
names, pinned image digests, memory/CPU limits and loopback-only ports 19022/19033.
It starts the reference services itself; no production services are required.
Port 19034 serves the deterministic model fixture. Fixture success proves transport
and lifecycle behavior, **not model quality**. Evidence is saved under
`release-evidence/<run-id>/`; only the containers/processes created by the run are removed.

For real-model testing, provide an **isolated** Ollama-compatible service:

```sh
.venv/bin/python scripts/verify_release.py --model-url http://localhost:TEST_PORT --model MODEL_NAME \
  --provider-manifest provider-profile.json \
  --provider-source /path/to/adapter.py --provider-source /path/to/prompting.py
```

Run gates from a clean committed checkout. For an exported candidate, first run
`scripts/release_identity.py` in that checkout and include the ignored
`candidate-manifest.json` in the export. The gate verifies the recorded files and
records commit, canonical source hash, Python/package versions and image digests.
A real-provider manifest must record `model`, immutable `model_digest`, adapter
`source_sha256` (basename to byte SHA256), effective generation/recovery options,
embedding model/digest and provider version. Supply every declared source with
`--provider-source`; the gate verifies and snapshots those bytes. Keep operational
profiles and snapshots in ignored evidence rather than committing private settings.
Configuration metadata is an operator declaration, not provider authentication.
Hosted CI saves fixture evidence, tests, coverage and dependency audit as an artifact.

Model output must be non-empty; M0–M6 canaries do not assess factual correctness.
The separate knowledge pilot uses synthetic data and must not be represented as
proof of accuracy on real operational documents.

## Reference policies and limits

- `CAS_NATS_URL` applies to all default fabric instances; an explicit constructor
  address takes precedence. NATS subscriptions return handles for owner cleanup.
- Goals follow the canonical lifecycle. `goal.complete` permits external completion
  from `created`. `completed`, `failed`, and `suspended` are immutable in this
  reference; resume/retry means creating a new goal. This is an implementation
  policy, not a new requirement on other protocol implementations.
- Goal execution fields (`intent`, `required_skills`, `priority`) can only be edited
  in `created`. This prevents the auction intent changing before execution.
- The selected worker validates its recorded assignment before invoking shared
  model/memory providers. Response node/goal/skill checks enforce consistency,
  not authenticated identity. Worker deduplication is volatile, bounded to 1024
  assignments, and can evict completed entries. Restart loses that cache; orphaned
  unfinished entries need operator reconciliation/restart. A full worker does not
  bid. This does not provide durable exactly-once side effects.
- JSON stores use flush/fsync and atomic replacement. A failed commit leaves the
  previous in-memory and on-disk snapshot intact. One coordinator owns each pair of
  files. Atomic replacement does not supply distributed transactions, multi-writer
  locking, or guarantee survival of filesystem/host power loss.
- Startup marks `broadcast`, `assigned`, and `executing` goals failed with
  `coordinator_restart` history. An operator reconciles interrupted external work.
- Memory query limit is an integer from 1 to 100. Auction proposal windows are
  bounded to 0–30000ms. Model HTTP requests retain the existing 120s timeout.
- Blocking model HTTP runs in a thread so health and other requests remain responsive.
  Thread cancellation cannot abort already-running HTTP I/O; this runtime is not
  intended for high concurrency or unlimited request rates.

## Security boundary and stable-release blockers

The trusted deployment boundary includes every NATS publisher, worker, local store
writer, and model/vector provider. Transport access controls belong to the operator:
bind loopback or a private network; configure NATS credentials/TLS/subject permissions
before widening access. Claims in proposals and `values_signature` are not authenticated
identities. Do not allow untrusted publishers, public endpoints, or multiple tenants.

Seed Values policies are keyword heuristics, not an authorization or safety boundary.
`requires_human_review` is metadata; text generation is not approval to execute an action.
The reference does not implement RFC-003 confidence calibration/clarification/action
gates or the complete canonical reasoning-response envelope. There are no action
executors in this release. Stable production readiness requires a specified trust model,
enforced action authorization, concurrency/backpressure budgets, durable multi-writer
storage where needed, retention/backup policy, production observability/SLOs and a
measured rollout/soak. Those claims must not be inferred from green milestone canaries.

## Rollout and rollback

Keep beta evaluation separate from production. Back up goal/reflection snapshots and
Qdrant storage before any operator-managed migration. Start one coordinator with new
store paths; verify health, memory read/write and goal lifecycle; observe error rate,
latency and available resource headroom. Stop rollout on data corruption or unexpected
execution. Roll back by stopping candidate services and restarting the previously pinned
runtime/configuration against its own retained snapshots. Do not reuse failed beta test
state as production data. The isolated gate exercises stop/restart/reconnect recovery;
it does not deploy or verify a production rollout.

## Workflow provenance

Prepared using [Addy Osmani agent-skills](https://github.com/addyosmani/agent-skills)
at `1401c8b8030e023baeebb31781a6653fe8e93026`: using-agent-skills,
test-driven-development, code-review-and-quality, shipping-and-launch.
Baseline CAS source: `f42dfee96d92cbc7b5e4a582a20f976c82d7eefe`.
Review lesson: test persistence failure, caller-owned metadata, duplicate submissions
and cleanup errors in addition to the happy path; a passing canary cannot prove
general compliance or stable-production readiness.

Audit lesson (2026-10-10): distinguish goal creation from concurrent model execution;
exercise interrupted execution with a real worker, and verify which worker actually
executes rather than relying only on auction metadata. Freeze provenance before
recording release evidence.
