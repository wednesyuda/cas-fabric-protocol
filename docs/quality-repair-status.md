# Quality repair status — 2026-10-11

The owner completed all 51 blinded development reviews: 4B 8/17, 8B 14/17,
CAS 15/17 for content correctness and appropriate decisions. CAS versus 8B
has two gains and one regression; sequential time is 2.70 times 8B. These
are reused development cases, not held-out quality approval. Correct abstention
may have no supporting citation; raw unsupported-citation choices are not
hallucination rates.

The retained repair clarifies extraction of historical names/values from user
utterances without demanding an interpretation the question does not request.
77 existing regression tests pass. A completed P2000-isolated 8B development
rerun remains 14/17; OPQA-3, OPQA-12 and the conflict control fail. More elaborate
verifier variants fixed OPQA-2 in targeted tests but still failed extraction or
conflict handling and added cost. They were rejected and reverted; no quality
pass is claimed. Provider-level targeted tests do not replace authenticated
end-to-end or independent quality review.

An early diagnostic discovered the owned provider also exposed A4000 through
Vulkan despite CUDA visibility. That run was interrupted and excluded from
P2000 comparisons. Vulkan was disabled on the owned provider; actual P2000
residency was verified. Existing production processes were preserved.

A stronger non-thinking 14B model is being downloaded only into isolated
comparison storage. Availability, digest, actual residency, request completion
and accuracy must be measured before any claim about its usefulness. Do not
attribute stronger-model gains to CAS without a matched larger single-model
baseline.

A private 40-case new-reference packet and interactive review form are prepared.
No new packet inference has occurred. Owner reference confirmation is pending;
thresholds were confirmed before inference. New source exclusion uses actual
source identity/content hashes, not incidental links in an index. Scope is
historical source-conditioned QA and explicit synthetic controls; this does
not establish current business SOP, retrieval coverage or population accuracy.

The original synthetic staging soak completed 86,449.99 seconds with 1,439
accepted requests and zero operational errors. It proves operational stability
for that canary only. Existing held-out quality failure remains in force;
pilot held, no merge/release/activation.
