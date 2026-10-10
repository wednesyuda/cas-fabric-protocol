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
