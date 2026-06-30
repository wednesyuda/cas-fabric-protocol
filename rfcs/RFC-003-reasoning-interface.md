# RFC-003 — Reasoning Interface

| Field | Value |
|---|---|
| RFC | 003 |
| Title | Reasoning Interface |
| Status | Draft |
| Version | 0.2 |

---

## Problem

Two problems have been conflated in most AI orchestration systems:

**Problem A:** How does a reasoning node receive well-prepared context?

**Problem B:** How does the system decide which nodes should work on a task?

Solving A with an orchestrator that also does B produces a system with a single point of failure and a bottleneck at every decision.

---

## Motivation

### On prepared context

The human neocortex does not receive raw sensory data. By the time information reaches conscious reasoning, it has already been filtered, pattern-matched, value-weighted, and memory-consolidated.

The neocortex receives **distilled, prepared, relevant** input.

A reasoning node must never receive raw input. It must always receive context prepared by the Memory Fabric.

### On coordination

The human brain does not have a central project manager that assigns tasks to neurons.

The brain broadcasts a goal state. Multiple regions respond. Coordination emerges from parallel self-organization — not from a manager dictating each step.

When you reach for a cup of coffee, no single component commands the others. Visual, motor, and balance systems self-organize around the shared goal.

This is the model for CAS Fabric task coordination.

---

## Specification

### 1. The Two Interfaces

This RFC defines two distinct interfaces:

**Interface A — Context Preparation**  
How the Memory Fabric prepares input before any reasoning node is invoked.

**Interface B — Task Auction**  
How nodes negotiate task participation when a new goal enters the system.

### 2. Interface A — Context Preparation

The Memory Fabric must prepare a Reasoning Request before any Reasoning Node is invoked:

```json
{
  "type": "reasoning.request",
  "request_id": "string",
  "originating_node": "string",
  "intent": "string",
  "prepared_context": {
    "working_memory": [],
    "relevant_episodic": [],
    "relevant_semantic": [],
    "active_goal": "string | null"
  },
  "values_signature": {
    "values_consulted": true,
    "tension_detected": false,
    "ethical_alignment_score": 0.0
  },
  "risk_assessment": {
    "risk_flags": [],
    "confidence_floor": 0.0,
    "recommended_caution": "string | null"
  },
  "constraints": {
    "max_tokens": 1000,
    "timeout_ms": 5000,
    "confidence_threshold": 0.98
  }
}
```

A Reasoning Node that receives a request without `values_signature` MUST reject it.

### 3. Reasoning Response

```json
{
  "type": "reasoning.response",
  "request_id": "string",
  "node_id": "string",
  "output": "string",
  "confidence": 0.0,
  "reasoning_trace": [],
  "memory_writes": [],
  "dissent": "string | null"
}
```

**dissent** — structured disagreement. Not refusal. Information. Must be acknowledged by the receiving system.

### 4. The Confidence Threshold

No action may be initiated when confidence falls below **0.98**.

When confidence < 0.98:
1. Emit `reasoning.clarification_needed`
2. Memory Fabric attempts additional context retrieval
3. If confidence rises above threshold → proceed
4. If not → defer with explanation, escalate if time-sensitive

### 5. Interface B — Task Auction

When a new goal enters the system, coordination follows an auction model — not a delegation model.

#### 5.1 Goal Broadcast

The initiating node (or the Memory Fabric on its behalf) broadcasts a Goal to all subscribed nodes:

```json
{
  "type": "goal.broadcast",
  "goal_id": "string",
  "intent": "string",
  "required_skills": ["string"],
  "deadline_ms": 0,
  "priority": "low | medium | high | critical"
}
```

#### 5.2 Node Proposal

Any node that can contribute responds with a Proposal:

```json
{
  "type": "goal.proposal",
  "goal_id": "string",
  "node_id": "string",
  "skills_offered": ["string"],
  "estimated_latency_ms": 0,
  "estimated_energy_cost": 0.0,
  "current_load": 0.0,
  "confidence": 0.0
}
```

#### 5.3 Auction Resolution

The Coordinator node collects proposals within a defined window and selects the optimal combination:

```json
{
  "type": "goal.assignment",
  "goal_id": "string",
  "assignments": [
    {
      "node_id": "string",
      "skills_assigned": ["string"],
      "execution_order": 0,
      "dependencies": ["node_id"]
    }
  ]
}
```

The Coordinator is an **auctioneer** — it selects from what is offered. It does not design the solution. It does not micromanage execution. It assembles the best available combination of proposals.

#### 5.4 No Permanent Coordinator

Any node may act as Coordinator for a given goal. There is no permanently designated Coordinator node.

When a goal is broadcast, the first eligible node to claim the Coordinator role for that goal wins it. Eligibility is defined by the Coordinator capability declaration.

This prevents single point of failure at the coordination layer.

---

## The Five Viewpoints Model

### Why Five

A single reasoning pass — one model, one forward pass, one perspective — is structurally prone to a specific failure: it optimizes for coherence with itself, not correctness against reality.

This is well documented in both human decision-making research and multi-agent AI literature. A decision that passes through only one point of view inherits all of that view's blind spots, undetected.

The Reasoning Interface requires that any non-trivial decision be evaluated from a minimum of five independent viewpoints before action is taken. This is not five LLM calls for the sake of five — each viewpoint has a distinct, non-overlapping responsibility, and a distinct failure mode it exists to catch.

This requirement is structural, not cosmetic. A system that merges these viewpoints into a single pass reintroduces the single-perspective failure mode this RFC exists to prevent.

### The Five Viewpoints

**1. Coordination Viewpoint**  
Receives goal broadcasts. Runs the auction. Assembles the execution plan from node proposals.  
Does not execute. Does not perform deep reasoning. Organizes.  
Contract: produces an assignment plan, not an answer.  
Failure mode it catches: tasks assigned to the wrong node, or no node, due to lack of overview.

**2. Knowledge Viewpoint**  
Deep retrieval and synthesis from accumulated memory and domain knowledge. Called for complex judgment requiring grounded context.  
Slowest, most thorough of the five. Called rarely — only when Fast Path memory retrieval (RFC-002) is insufficient.  
Contract: must cite memory sources. Must not fabricate.  
Failure mode it catches: decisions made on incomplete or fabricated information.

**3. Risk Viewpoint**  
Runs in parallel with all other viewpoints, never after. Evaluates the proposed plan specifically for failure modes, edge cases, and downstream consequences.  
Deliberately adversarial by design — its function is to find what could go wrong, not to confirm what is going right.  
Contract: produces risk flags, not decisions. Never blocks — always advises. Runs parallel, never sequential.  
Failure mode it catches: plans that look correct but fail under conditions the other four viewpoints did not consider.

**4. Execution Viewpoint**  
Receives the finalized, risk-reviewed assignment. Executes with precision and speed.  
Does not deliberate further. Does not redesign the plan mid-execution.  
Contract: verifies each step against reality before proceeding to the next. Stops and escalates if reality diverges from the plan, rather than improvising silently.  
Failure mode it catches: plans that quietly drift from their original intent during implementation.

**5. Values Viewpoint**  
Not a Reasoning Node. Implemented as a permanent component of the Memory Fabric per RFC-002 — present in every context preparation, not invoked on demand like the other four.  
Contract: every prepared context must carry a values signature (RFC-002, Section 5.4) before reaching any other viewpoint. If an implementation builds this as an on-demand Reasoning Node rather than an always-present Memory Fabric component, it is **non-compliant** with this protocol.  
Failure mode it catches: technically correct decisions that are nonetheless harmful, exploitative, or dehumanizing — failures the other four viewpoints have no mechanism to detect, because correctness and values are different axes.

### Why This Specific Set of Five

These five were not chosen arbitrarily. They map to five distinct questions any non-trivial decision must answer, and each question has a different failure mode if skipped:

```
Coordination → "Who should do this, and in what order?"
Knowledge    → "What do we actually know about this?"
Risk         → "What could make this go wrong?"
Execution    → "Is this actually being done as planned?"
Values       → "Should this be done at all, this way?"
```

Removing any one viewpoint does not make the system faster in a healthy way — it makes the system blind in one specific, predictable direction.

Implementations are free to name these viewpoints however fits their domain. The behavioral contracts above — not the names — are what compliance is measured against.

---

## Examples

### Goal auction flow

```
User: "Summarize this PDF invoice"

Memory Fabric broadcasts:
  goal.broadcast {
    intent: "summarize PDF invoice",
    required_skills: ["document.ocr", "text.summarize"]
  }

Node-03 responds: { skills_offered: ["document.ocr"], latency: 200ms, load: 0.3 }
Node-07 responds: { skills_offered: ["text.summarize"], latency: 150ms, load: 0.1 }
Node-11 responds: { skills_offered: ["document.ocr", "text.summarize"], latency: 400ms, load: 0.7 }

Coordinator selects: Node-03 + Node-07 (lower combined load, lower latency than Node-11 alone)

Assignment:
  Node-03 → document.ocr (step 1)
  Node-07 → text.summarize (step 2, depends on Node-03)
```

---

## Open Questions

- What is the appropriate proposal collection window before the Coordinator must decide?
- Should the Risk Viewpoint be automatically included in every goal auction, or only for goals above a certain priority?
- How should the system handle a goal that receives zero proposals?

---

## CAS Test

| Question | Answer |
|---|---|
| Is it local? | Yes — each node proposes based on its own local state |
| Is it composable? | Yes — any node can join any auction without modification |
| Is it adaptive? | Yes — coordination adapts to available nodes and current load |
| Is it emergent? | Yes — the execution plan emerges from proposals, not from central design |
| Is it implementation-independent? | Yes — LLM, model size, and language are entirely up to the implementor |
