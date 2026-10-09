# Reference candidate changes after independent audit

The previous beta assessment was too broad. Astra medium reproduced gaps in
in-flight goal editing and worker selection; the current candidate fixes those
behaviors and adds executable regressions. Stable production readiness remains
outside this reference beta scope.

1. Lock execution fields after `created`; reproduce the intent A-to-B auction race
   and require both executed and persisted intent to remain A.
2. Execute through the selected worker's opaque capability, validate assignment
   and response identity fields, suppress bids from full workers, and test distinct
   worker outputs. The integration gate interrupts an actual blocked worker,
   restarts the coordinator and verifies that late output cannot rewrite failure.
3. Require clean committed source or a verified export manifest. Capture source,
   model and adapter identities; save hosted CI evidence for maintainer review.

Run the acceptance gates described in [release readiness](../docs/release-readiness.md).
Local and earlier integration checks inform these changes; final frozen-commit,
hosted-CI and real-provider results belong in the external verification record
so reporting them does not modify the source being verified.

No production rollout, stable release, tag or merge is included. Opaque subjects
and response consistency checks do not authenticate workers. Volatile worker
records do not guarantee durable exactly-once execution. M0-M6 canaries prove
transport/lifecycle integration rather than operational answer accuracy.
