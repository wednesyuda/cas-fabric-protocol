# Contributing

CAS Fabric Protocol is an open specification developed through structured discussion.

This is not a code repository. It is a living document that defines how cooperative intelligent systems should behave.

---

## Before You Contribute

Read these two documents first. They are not optional.

1. [PRINCIPLES.md](./PRINCIPLES.md) — the philosophical foundation
2. [RFC-000](./rfcs/RFC-000-design-philosophy.md) — the constitutional document

If a proposal conflicts with PRINCIPLES.md, it will not be accepted regardless of technical merit.

---

## How RFCs Work

Every change to this protocol must go through an RFC.

### RFC Structure

Every RFC must contain these sections:

**Problem** — What specific problem does this solve? One paragraph maximum.

**Motivation** — Why does this matter in the context of a Complex Adaptive System?

**Specification** — The normative rules. Use MUST, SHOULD, MAY following RFC 2119 conventions.

**Examples** — At least one concrete example of a valid implementation. This is not the only valid implementation — it is proof that the specification is implementable.

**Open Questions** — What has not yet been decided? Honest incompleteness is better than false certainty.

**CAS Test** — Every RFC must include the five-question CAS Test table.

### RFC Status

| Status | Meaning |
|---|---|
| Stub | Placeholder. Problem identified, solution not yet designed. |
| Draft | Being actively written. Not ready for implementation. |
| Review | Ready for community review. |
| Accepted | Stable. Implementations may rely on this. |
| Deprecated | Superseded by a later RFC. |

---

## The CAS Test

Before submitting an RFC, verify it passes all five questions:

1. **Is it local?** Can the decision be made with local knowledge only?
2. **Is it composable?** Can it combine with other nodes without modification?
3. **Is it adaptive?** Can behavior change without changing the protocol?
4. **Is it emergent?** Does coordination arise from interaction, not central control?
5. **Is it implementation-independent?** Are implementors free to choose their stack?

If any answer is no, revise before submitting.

---

## What Belongs Here

This repository contains:

- RFC specifications
- JSON schemas for protocol messages
- Minimal examples that demonstrate the specification (not a complete implementation)
- Governance documents

This repository does not contain:

- Framework code
- Agent implementations
- Application code
- Reference implementations (those live in separate repositories)

---

## Opening an Issue

Use GitHub Issues to:

- Propose a new RFC (label: `rfc-proposal`)
- Report an ambiguity in an existing RFC (label: `clarification`)
- Identify a conflict between RFCs (label: `conflict`)
- Ask a question (label: `question`)

Do not use Issues for implementation questions. This repository specifies the protocol, not how to implement it.

---

## Tone

This is a specification for systems that cooperate with humans.

Write with precision. Write with humility. Acknowledge what you do not know.

The Open Questions section of every RFC exists for a reason — use it.
