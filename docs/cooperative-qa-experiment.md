# Paired cooperative QA experiment

This experiment compares frozen single-reasoner answers with those same answers
reviewed by an independent verifier process/model over authenticated NATS.
It is a two-stage composition experiment, not coordinator election or emergence.
The baseline is archived, not regenerated in parallel; sequential cooperative
latency is archived primary latency plus current verification latency.

Primary: experimental non-thinking Qwen3:4b. Verifier: Qwen2.5:3b with a separate
role prompt, flat decision schema and CPU execution requested explicitly. Check
actual provider residency rather than infer it from configuration. Both roles
see the same evidence; only the evaluator sees reference answers and score labels.
Use identical model/template identities and freeze packet provenance. Report
improvements and regressions together, including added model calls/tokens/latency.

The experimental `experiment.document.verify` capability may accept, revise,
abstain, or request review. It cannot authorize actions. Citation validation is
mandatory but does not prove semantic entailment. Accept preserves the original
candidate; revise requires supported-source membership; abstention/review cannot
claim supporting citations. Missing, expired or invalid verification goes to
human review rather than approving the unverified candidate. The runtime probe
stops the verifier and confirms this behavior over NATS.

Generated credentials, questions and model outputs are private. Production role
permissions, deployment defaults, running soak and reflection scores are not
updated by this experiment. Peer judgments are not human semantic labels and are
not automatically used as correctness feedback for adaptive scoring.

The owner-reviewed historical QA packet is a development set. Controlled conflict,
unknown and injection cases are diagnostic, not independent statistical trials.
A cooperative gain here needs fresh held-out operational QA and independent
semantic/citation review before deployment. It establishes only a limited
composition benefit if measured quality improves without unacceptable regressions.

## Development result, 2026-10-10

The authenticated 17-case paired replay at source e918379 scored 8/17 for the
archived baseline and 6/17 after verification. OPQA-6 improved, while OPQA-13,
OPQA-14 and CONTROL-injection-0 regressed. Ten verifier responses failed
validation. All 17 additional model requests completed; verification added
587.19 seconds total (34.54 seconds per case) on the CPU-only provider.
The real verifier-unavailability probe returned review with no action allowed.
These lexical development diagnostics reject adoption of this model composition;
safe failure is not a quality pass. The pilot remains held. Source e918379 is
the measured implementation; subsequent non-object response hardening does not
change these scores. The earlier run had no authenticated subscriber and is an
invalid transport attempt, not a model-quality result.

## Decision-conditioned grammar retest

At source 2fa6af7, the generator schema uses decision-specific alternatives:
abstain/review require empty sources, accept follows the candidate's abstention
state, and factual accept/revise require at least one allowed source. The schema
is also included in the system prompt. Post-generation citation validation is
unchanged. A synthetic actual-provider canary confirmed empty-source abstention;
provider residency confirmed zero VRAM use.

The same 17 frozen cases then scored baseline 8/17 and cooperative 8/17, with
zero regressions, zero improvements and zero verifier validation errors. All
17 added model calls completed, adding 747.02 seconds total (43.94 per case),
21,052 prompt tokens and 1,587 output tokens. The verifier-loss probe again
requested review without permitting actions. CPU provider cleanup was verified.
The contract correction is successful; this composition still has no measured
quality benefit and remains unsuitable for adoption. CI passed for 2fa6af7;
local validation passed 70 tests plus 54 subtests and fatal Ruff checks.

The controlled conflict response acknowledged opposing schedules in its reason
but chose `revise`/`answer` with both sources and an unavailable-information
answer. This is a semantic decision failure, not a scoring omission of the
reason field. Do not infer review status from keywords or relax the gate.
Next work should isolate evidence-based decision correctness before adding
nodes or claiming emergence. Both replays remain development diagnostics;
fresh held-out semantic review and the production pilot remain pending.

## Isolated decision diagnostics

At source 82d5cc6, explicit conflict-first instructions were tested on eight
synthetic development cases frozen before inference. They include reversed
source order, conflicting quantities, agreeing claims, different subjects,
explicit supersession, a correctable candidate and absent information. Gold
labels are not sent to the model. This is a provider-level diagnostic, not a
NATS composition or independently reviewed held-out quality test.

Qwen2.5 completed all eight with zero envelope errors, but scored only 2/8
before exposing review explanations (235.30 seconds). Two schedule cases chose
review and explained both values in `reason`, while `answer` omitted that
explanation. Source bade5e5 makes review reasons visible without changing the
model's decision. Deterministic replay of those archived outputs scored 4/8;
it used no new model calls and is not a fresh generation result. Quantity
conflict, different-subject, correctable-candidate and missing-information
controls still failed. In particular, the model guessed that one contradictory
quantity was erroneous and treated distinct subjects as needing review.
The prompt candidate therefore fails specificity controls and is not adopted.

A bounded comparison using the already available cas-qwen3-nothink:4b model
on the same CPU-only provider timed out at 120 seconds on its first case.
The run was stopped after one recorded result, with the remaining packet
unevaluated. This is a runtime feasibility failure, not a semantic verdict or
an 0/8 score. Both model identities and zero-VRAM residency were recorded.
The owned provider was stopped; production providers and soak were preserved.

The diagnostic runner now stops on a provider timeout/connection failure and
reports planned versus completed cases, preventing an unusable provider from
consuming the whole packet. Validation: 73 tests plus 54 subtests and fatal
Ruff checks passed. No larger operational replay follows this failed control
gate. Next feasibility work should establish an isolated verifier execution
budget (for example on the P2000) before further model comparisons. Model
decision correctness and independent semantic review remain required; neither
rendering a reason nor a process exit code grants production approval.
