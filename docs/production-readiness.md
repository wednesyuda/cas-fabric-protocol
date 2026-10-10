# Internal production gates

Scope: one owner, one host, document Q&A, no action executors. These gates do not
publish a release or establish model accuracy without a held-out corpus evaluation.

## Request budgets and admission

`expires_at_ms` is an absolute Unix timestamp in milliseconds. Outgoing requests
use the minimum of the supplied deadline, inherited request deadline and local
transport timeout. Hosts must have synchronized clocks; monotonic asyncio timers
bound queue waits. Expired requests are rejected before invoking a handler.
`deadline_ms` in legacy goal broadcast is not the new absolute timestamp.

Coordinator submit and reasoning generation each admit one active and two queued
requests; queue wait is at most 15 seconds. Extra requests get `busy`. Their native
NATS pending buffers are limited to 256 messages/1 MiB; extreme bursts can trigger
NATS slow-consumer errors rather than guarantee a reply to every publisher.
Bounded dispatch is opt-in; short handlers retain existing serial delivery.

A timeout does not cancel provider I/O. A running HTTP request retains its slot
until completion and its expired answer is discarded. There is no automatic retry.
Python thread context carries the deadline to the HTTP timeout. A slow provider
cannot release capacity merely because its client stopped waiting.

`admission_metrics` exposes accepted, busy, expired and in-flight counts by subject.
Metrics contain no prompts. Final workload/latency/quality/restore gates are separate.

Reflection retains aggregate skill statistics and worker-scoped execution scores.
Auctions use the latter so one worker's history cannot raise every peer's score.
These scores measure execution status, not semantic answer correctness; valid
abstention is not independent quality evidence. See `docs/cas-evidence.md` for the
distinction between runtime contracts and the unproven broader CAS thesis.

## Authenticated internal profile

Run `scripts/prepare_internal_profile.py /private/new-directory` to create distinct
role credentials and broker permissions. Bind the container's host port to
127.0.0.1 only; the broker's internal listen address is deliberately container-wide.
Never publish generated files. Each service reads CAS_NATS_AUTH_FILE and uses its
own inbox prefix. Credential-bearing URLs are rejected before connecting/logging.
Alternative NKey credentials/TLS settings are supported but have not been exercised
by the loopback gate; use a separate TLS gate before crossing a host boundary.

Requester may create/submit/status goals. A separately authorized ingester writes
memory. Backend services and coordinator have different permissions. Worker IDs
must match their scoped assignment and execution subjects. Negative runtime tests
verify forbidden requester publishes, wrong credentials, another role's inbox,
another worker's execution subject, and authorized request/reply. The full stack
also runs under these profiles. Workers remain trusted proposal authors; transport
permissions do not cryptographically sign arbitrary node_id payload fields.

The isolated profile is not installed over existing services. `internal.env.example`
and `cas-internal@.service` provide persistent paths and role configuration. Create
a service-specific env file with CAS_SERVICE_SCRIPT (the existing Python entrypoint),
validate paths/permissions and systemd syntax on the target host before installation.
Readiness, restore and actual workload gates precede operator pilot traffic.

## Document mode and quality boundary

Internal profiles must set CAS_DOCUMENT_QA=1. The authenticated full-stack fixture
asserts reasoning.response, grounded source membership and actions_allowed=false.
The document mode uses Ollama /api/chat with structured answer/abstention/review
output; CAS_EMBED_URL separates the embedding provider from generation.

Unsupported/fabricated citations and invalid JSON fail closed. Absent evidence and
policy review flags prevent generation. A model-detected conflict returns
needs_review rather than allowing action. Source membership is not semantic
entailment: genuine quality requires scoring actual claims against approved documents.
No calibrated numerical confidence or full RFC-003 compliance is claimed.

The private evaluation runner reads approved Obsidian documents locally, excludes
credential-looking material, freezes content hashes and evaluates real-text
extraction, unknowns and controlled conflicts/injections. No raw corpus is committed.
Extraction/stress tests do not replace human-scored operational Q&A or end-to-end
retrieval quality. Failed quality gates hold pilot activation even if CI passes.

`scripts/evaluate_operational_qa.py` runs private QA packets through authenticated
ingestion, goal submission, retrieval and generation on isolated ports 22042/22043.
It records expected-source retrieval separately from candidate-reference keyword
checks. Historical user statements are labelled as historical, not approved SOP.
Independent reference review and semantic/citation scoring remain mandatory even
if every automated diagnostic passes. Raw packets and responses remain private.

## State ownership, backup and restore

The coordinator holds OS locks on both store paths. A second writer or backup is
rejected while those paths are owned; locks release on process death. Explicit
persistent paths are required in the internal profile, not the reference /tmp defaults.

Stop admission, drain bounded work and stop all goal/memory writers before calling
backup_state.py. Its locks protect JSON coordinator ownership; they do not pause
an independent ingester or make Qdrant/JSON a distributed transaction. Backups store
hashes, Qdrant version/config and collection snapshots. Restore requires an empty
Qdrant instance, an absent state directory, matching version and valid file hashes.
Never restore over live/new state. Partial failed restore targets remain for
investigation and must not be used as a successful release.

The isolated drill restores a goal/history and Qdrant canary, rejects active owners
and corrupted backups, and uses a real /dev/full ENOSPC write to prove the old JSON
snapshot and memory remain intact. This is a data-restore proof, not a reboot,
power-loss, off-host disaster recovery or production rollback proof.

## Workload and soak gates

verify_internal_runtime.py can use an isolated real Ollama chat endpoint and a
separate embedding endpoint. The workload traverses authenticated goal submission,
selected worker, context/memory and model. It reports accepted-request errors,
answer statuses, end-to-end p50/p95/p99, host load and GPU usage, without raw prompts.
It uses a synthetic canary; success does not establish real-document accuracy.

Example warm workload: --model-url http://127.0.0.1:21436 --embed-url
http://127.0.0.1:21434 --count 100. Cold starts must be reported separately.
Example staging soak: same providers, --count 1 --duration 86400 --interval 60.
Do not run two instances: this gate owns fixed isolated ports 22022/22033.
Only its own container IDs/processes are cleaned up; existing providers are reused
without restart. Actual elapsed time and completed requests, not a scheduling
command, determine whether the 24-hour gate is complete. A model/quality failure
holds the pilot regardless of staging reliability. A seven-day user pilot requires
actual usage, human-reviewed answers, thresholds, kill switch and operator coverage.
