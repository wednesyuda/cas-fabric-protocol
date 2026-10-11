# Experimental non-thinking Qwen3 profile

`cas-qwen3-nothink.json` is an Ollama `/api/create` request using existing
`qwen3:4b` weights. The local base template unconditionally opened `<think>`;
this derived template closes that block before generation. The weight blob was
verified identical. It changes the derived model only; do not overwrite the base.

Send this JSON to a separate loopback evaluator's `/api/create` endpoint.
The model is experimental, not the default deployment profile. Record template
hash, model digest and actual device residency. Quality gates and human review
must pass before selecting it for deployment. Use `evaluate_operational_qa.py`
with `--model-url` and `--model` to evaluate it on an isolated authenticated stack.
The existing 24-hour soak continues using its original model and template.

`cas-qwen3-nothink-8b.json` applies the identical closed-thinking template to
`qwen3:8b` for the single-small/single-larger/cooperative development comparison.
It is a larger-capacity candidate, not a pre-established quality winner. Store
downloaded weights in the owned experiment directory, retain the base model,
and record digests, template hashes and actual partial GPU/CPU residency.
The two single-model baselines share answer instructions, evidence, schema,
512-token limit, temperature zero, seed 42 and explicit `think:false`.
