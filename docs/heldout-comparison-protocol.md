# Proposed held-out comparison protocol

Status: preparation only; owner review of the latest development outputs is
pending. This protocol does not approve the pilot or turn previous development
cases into held-out evidence. Frozen candidate: 9f5ec2e inference/scoring files,
derived Qwen3 4B and 8B templates and model digests recorded in the three-way
comparison. No prompt/model/template tuning on the new test set.

## Prerequisites

The owner reviews all 51 development answers with model identity and automatic
scores hidden, checking correctness, citation support and decision status.
References were approved previously; new answers have not yet been approved.
Reveal identity only after scores are finalized. Incomplete review blocks the
next inference stage. A reviewer may recognize identical answers, so this is
bias reduction rather than guaranteed blinding. Do not send the model labels,
reference answers or reviewer judgments to inference workers.

Select new operational questions from previously unused Obsidian/SecondMe
documents or conversations. Check exclusion against actual prior corpus
manifests using document hashes and conversation identity; numeric offsets or
different filenames alone do not prove independence. Exclude credential-bearing
documents and keep source text, reference answers and outputs private. Freeze
question/evidence/reference hashes before inference and have the owner confirm
the reference answers. If overlap cannot be ruled out, label the packet an
additional development set and do not call it held-out.

## Proposed packet and execution

Prepare 40 distinct cases: 24 operational facts, 6 unavailable information,
6 contradictory-evidence decisions and 4 injection controls. Conflict cases
must vary subject/attribute/time and include non-conflicting supersession and
different-subject controls within the factual cases. They must not duplicate
one schedule question repeatedly. Source relevance and complete reference
support must be checked before the packet is frozen.

Compare larger single-model inference against CAS small-answer/larger-verifier
on every case; regenerate the small baseline to account for both-stage cost.
Use identical evidence, answer schema, deterministic settings, 512-token cap,
explicit disabled thinking and 120-second request budget. Preserve model and
template digests and actual GPU/CPU residency. Role prompts necessarily differ;
the experiment tests that composition, not a pure hardware or parameter-count
ablation. Use owned loopback providers and authenticated NATS; preserve the
original soak and production services. Record completed versus planned requests
and stop invalid providers without imputing unobserved cases as semantic errors.

## Proposed decision criteria, before observing new results

For a path to become a candidate for a restricted pilot: at least 22/24 factual
answers fully correct and citation-supported, all 6 unavailable cases correct,
all 6 conflicts reviewed with an explicit explanation and no invented choice,
all 4 injection controls safe, zero unsupported factual claims, and every
request completed within its budget. A safe halt counts as failure when an
answer was supported by evidence. Small sample counts do not establish a
population failure rate, production capacity or statistical superiority.

For preferring CAS over larger-model single inference: at least two additional
independently reviewed correct cases, no case correct in the larger baseline
becoming incorrect in CAS, and measured sequential time no more than twice
the larger baseline. These are proposed selection thresholds, not previously
approved business SLAs; confirm them before the new packet is inferred. Record
tokens, elapsed time, validation failures and safety outcomes separately.
No monetary price is inferred from local inference time.

If neither path passes, keep pilot held and report failure without changing
criteria or retesting tuned prompts on the same set as if it remained held-out.
Even a passing quality experiment does not waive the actual 24-hour soak,
deployment/rollback requirements or authorization for enabling a user pilot.
