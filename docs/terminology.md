# Terminology

A shared vocabulary for CAS Fabric Protocol.

New terms are only introduced when existing software engineering terminology cannot accurately express the concept.

---

## Core Terms

**Node**  
Any autonomous participant in the fabric. A node has identity, declares capabilities, and communicates through the fabric. A node may be an LLM, a vision system, a database interface, a sensor, a robot, or any other computational unit.

**Fabric**  
The shared substrate through which nodes communicate, share memory, and coordinate. The fabric is not a controller. It enables coordination without imposing it.

**Memory Fabric**  
The active cognitive memory layer of the ecosystem. Distinguished from passive databases by its ability to observe context and proactively surface relevant information. Implements the Limbic Layer.

**Autonomic Layer**  
Infrastructure that runs continuously without invoking reasoning nodes. Health monitoring, routing, discovery, synchronization.

**Limbic Layer**  
The active memory and values fabric. Always present. Never explicitly called. Shapes context for all reasoning.

**Neocortex Layer**  
Reasoning nodes. Expensive. Called only when lower layers cannot resolve.

**Values Fabric**  
The ethical and philosophical substrate embedded within the Memory Fabric. Not an agent. Not a filter. A gravitational field that shapes what every node considers as relevant context.

**Tension Signal**  
A signal emitted by the Memory Fabric when a node's declared intent conflicts with the Values Memory above a defined threshold.

**Presence Marker**  
A metadata field appended to every context payload by the Memory Fabric, indicating that values have been consulted during context preparation.

**CAS Test**  
The five-question design review that every protocol feature must pass before acceptance. See PRINCIPLES.md.

**Fast Path**  
Memory relevance scoring that uses vector similarity, recency, and pattern matching — without invoking LLM nodes.

**Slow Path**  
Memory relevance scoring that invokes a Reasoning Node for semantic judgment. Used only when Fast Path confidence falls below threshold.

**Confidence Threshold**  
The minimum confidence score required before a Reasoning Node may initiate action. Protocol default: 0.98.

**Dissent**  
A structured disagreement emitted by a Reasoning Node when it believes the prepared context is insufficient, the intent is unclear, or the confidence threshold cannot be met. Dissent is not refusal — it is information.

---

## The Five Viewpoints

Five required perspectives for any non-trivial decision, formalized in RFC-003. Each maps to a distinct question and a distinct failure mode if skipped. See RFC-003 for full specification.

Implementations are free to name these however fits their domain. The behavioral contracts must be honored.

**Coordination Viewpoint**  
Receives intent. Decomposes. Routes via Task Auction. Does not execute.  
Answers: *who should do this, and in what order?*

**Knowledge Viewpoint**  
Deep knowledge synthesis. Slow. Authoritative. Called rarely — only when Fast Path memory retrieval is insufficient.  
Answers: *what do we actually know about this?*

**Risk Viewpoint**  
Parallel risk evaluation, never sequential. Deliberately adversarial by design. Advisory only — never blocks.  
Answers: *what could make this go wrong?*

**Execution Viewpoint**  
Receives the finalized, risk-reviewed plan. Executes with precision. Verifies reality against plan at each step.  
Answers: *is this actually being done as planned?*

**Values Viewpoint**  
Implemented as a permanent Memory Fabric component, not an on-demand Reasoning Node. The gravity field within which the other four viewpoints operate.  
Answers: *should this be done at all, this way?*

---

## Terms Deliberately Not Used

**Agent** — avoided because it implies autonomy without specifying the cooperation contract. Use *Node* instead.

**Orchestrator** — avoided because it implies centralized control. CAS Fabric has no permanent orchestrator.

**Master / Slave** — not used. Use *Coordinator* and *Worker* if hierarchy must be expressed.

**Smart Contract** — not used. Has specific blockchain connotations not intended here.


---

## Plasticity Terms

**Skill**
A self-contained unit of capability that a node can load, execute, and release. Skills are transient. Nodes are persistent.

**Skill Genome**
The shared, persistent repository of all skills available to the ecosystem. The collective memory of capability. Not an orchestrator — passive storage from which nodes express capability as needed.

**Skill Manifest**
A node's current advertisement of active skills. Changes as skills are loaded and released. Published to the Autonomic Layer so other nodes can discover capabilities.

**Retention Score**
A metric computed by each node for each active skill, determining whether to retain or release it. Factors include utilization rate, recency, memory footprint, energy cost, and ecosystem demand.

**Plasticity Engine**
The component within a node responsible for computing retention scores, initiating skill acquisition, and managing skill release. Analogous to synaptic plasticity in biological neurons.

**Forgetting**
The deliberate release of a skill when its retention score falls below threshold. Not failure — adaptation. The skill returns to the Genome, available for future acquisition.

**Task Auction**
The coordination mechanism defined in RFC-003 by which nodes propose their capabilities in response to a goal broadcast, and a Coordinator assembles the optimal combination.

**Auctioneer**
The role of the Coordinator node in a Task Auction. Selects from offered proposals — does not design or micromanage.

**Ecosystem Demand Signal**
An aggregate metric in the Skill Genome tracking how frequently each skill is being acquired across all nodes. Feeds into individual node retention score calculations.
