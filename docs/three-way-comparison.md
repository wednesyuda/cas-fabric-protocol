# Frozen three-way development comparison, 2026-10-10

The same 17 questions, reference labels and evidence were used for fresh
single-model inference and an authenticated CAS verifier replay. The private
references were owner-reviewed earlier; these new outputs still require
independent semantic/citation review. Scoring remains lexical development
diagnostics, not a production quality gate or a statistical generalization.

| Path | Pass | Facts | Abstention controls | Conflict | Total seconds |
| --- | --- | --- | --- | --- | --- |
| Qwen3 4B single | 8/17 | 4/12 | 4/4 | 0/1 | 85.75 |
| Qwen3 8B single | 14/17 | 10/12 | 4/4 | 0/1 | 235.92 |
| CAS 4B then 8B verifier | 15/17 | 10/12 | 4/4 | 1/1 | 637.13 |

All paths completed with zero envelope errors. CAS added 17 model calls and
551.38 seconds of verification to the completed 4B baseline. It improved seven
cases against 4B with no regressions. Against 8B alone, it improved OPQA-3 and
the single controlled conflict but regressed OPQA-2, giving only one net extra
pass at about 2.70 times the measured sequential latency. The two-stage total
is archived fresh 4B latency plus measured verifier latency, not a simultaneous
full-stack load benchmark. CAS tokens: 39,854 prompt and 2,867 output across
both stages, versus 15,530/754 for 8B alone. No monetary pricing is inferred.
The actual verifier-loss probe requested review without allowing actions.

Single-model paths shared answer instructions, evidence, schema, seed 42,
temperature zero, 512 output-token cap and explicit disabled thinking. Derived
4B and 8B profiles use the same closed-thinking template, each retaining its
base weight blob. The 8B model was downloaded only to owned comparison storage;
base digest 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41,
derived digest 138f9a7c2e71a5f2eeebb71ad37b26f4aaed36a6566fc670c4feeb8882d68733.
4B inference ran at 53399f8; larger/cooperative runs at 9f5ec2e. Relevant inference,
schema and scorer file hashes were verified identical between these revisions.

The 8B provider saw only P2000, using 3.46 GB VRAM with the remainder in RAM;
observed P2000 total usage 3,937 MiB. A4000 remained 14,195 MiB. Sequential model
residency avoids competing for P2000 memory and is not a concurrent capacity
claim. An isolated existing Bonsai 27B provider with CPU plus 16 P2000 layers
failed the 120-second canary deadline and was stopped; no semantic quality
claim is made for that model. Existing production inference was not invoked.

Conclusion: model capacity helps this packet substantially; the specific CAS
composition provides a limited additional development benefit, with a material
cost and a regression relative to the larger single model. This does not prove
emergent intelligence, independent model diversity, or release readiness.
Private questions/evidence/outputs are excluded from this repository. A private
three-way review packet contains all answers and evidence for human assessment.
Require that review plus a fresh, frozen held-out comparison before selecting
either path. Do not tune further on this packet and present it as held-out.

Owned experimental providers were stopped; P2000 returned to 553 MiB and A4000
usage remained unchanged. The original soak remained ongoing: 561 requests,
zero failures, no terminal summary. Local verification: 77 tests plus 54 subtests
and fatal Ruff passed. Pilot remains held; no merge or release was performed.
