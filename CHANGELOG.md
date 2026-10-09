# Changelog

## v0.1.0-beta.1 — candidate

- Apply configured NATS address consistently and normalize unavailable-capability
  behavior; reject malformed transport messages and clean up temporary subscriptions.
- Validate goal lifecycle and fields, reject repeated execution, atomically persist
  goal/reflection updates, and fail interrupted goals on coordinator restart.
- Isolate model HTTP from the event loop, reject empty generation and mismatched
  prepared intent; bound memory queries and auction proposal windows.
- Lock goal execution fields after creation; route execution through the selected
  worker and check assignment/response consistency. Suppress bids from full workers.
- Exercise actual worker interruption, distinct competing worker outputs and late
  result handling. Freeze source identities and real-provider source snapshots.
- Add regression/schema tests, pinned runtime dependencies, isolated integration and
  recovery gates, and CI. Document the reference trust boundary and release limits.
