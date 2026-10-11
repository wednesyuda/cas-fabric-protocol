# CAS thesis versus reference-runtime evidence

The reference fabric demonstrates implementable contracts, not the complete
Complex Adaptive System thesis. A functioning Q&A product is one workload and
does not prove emergent cooperative intelligence.

| Principle | Existing evidence | Remaining limit |
| --- | --- | --- |
| Local decisions | Workers propose skills from their local configuration and load; selected workers own execution | Executor mappings are static; autonomous acquisition/release is not demonstrated |
| Composition | Memory, context, reasoning and workers communicate over capabilities; selected-worker identity is checked | One Python implementation and NATS/Qdrant stack; cross-language/provider interoperability unproven |
| Adaptation | Persistent reflection now distinguishes worker/skill outcomes; a failed executor changes the next auction winner | Measures execution success, not independently verified answer correctness; node identity is trusted within the deployment |
| Emergence | Auction assignments arise from proposals rather than a prescribed named worker | One permanent coordinator process; per-goal coordinator election/failover required by RFC-003 section 5.4 is absent |
| Implementation independence | Protocol contracts separate capability names from executor implementation | Ollama-specific document QA and model-template profiles are implementation details, not protocol requirements |

RFC-003's five independent viewpoints for non-trivial action decisions and its
confidence/escalation contract are not fully implemented. The internal document
workload disables actions and does not claim full RFC-003 compliance. A ranking
score is not calibrated semantic confidence, including when its value reaches 1.

The earlier aggregate-only skill reflection assigned identical historical scores
to competing workers. It could change skill statistics but did not distinguish
their performance in an auction for the same skill. Worker-scoped statistics
correct that gap while retaining aggregate status compatibility. Legacy aggregate
scores do not transfer to unseen workers, which start neutral. Reflection is
updated only after an assignment execution result, never from self-declared
proposal confidence. A neutral score is not evidence of quality.

The runtime gate uses two real NATS workers: the initially faster worker succeeds,
then fails a controlled execution; the next auction selects the other worker and
executes it. This demonstrates a narrow adaptive mechanism, not an autonomous
ecosystem or a quality gain. State persistence and rejection of corrupt writes are
tested separately. The reflection store is still coordinated and scoped to one
deployment; no distributed consensus or coordinator-independent learning is claimed.

Production hardening supports the original thesis. Model-template optimization
supports one implementation. Treating that optimization or synthetic smoke
success as proof of CAS intelligence would be a scope error. Next thesis-level
experiments should compare single-node and cooperating-node workloads on the same
independently reviewed cases, test node substitution/failure, and separate quality,
latency and cost. Per-goal coordinator ownership and genuine skill lifecycle remain
architecture work requiring explicit contracts and failure semantics.
