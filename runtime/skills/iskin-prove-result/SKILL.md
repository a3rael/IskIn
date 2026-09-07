---
name: iskin-prove-result
description: "Use when collecting canonical evidence for an approved IskIn outcome."
version: 0.4.0-dev
metadata:
  hermes:
    tags: [iskin, evidence, provenance]
    related_skills: [iskin-change-product, iskin-challenge-result, iskin-control-pilot]
---

# Prove an IskIn result

## Applicability

Use only for an IskIn outcome with a complete approved approval package, a durable approval event with `implementation_authorized: true`, approved applicable gates, and a defined evidence scope. Otherwise return `not applicable` or `blocked` without changing files. Read-only diagnosis of existing state is allowed and does not create product proof.

## Procedure

1. Read the outcome, approval event, `process/quality-gates.md`, `process/evidence-provenance.md`, current evidence, and uncertainties.
2. Run only applicable canonical checks. Create or update canonical evidence, provenance, and proof records according to the project contract; read back every record written.
3. Record the version or revision of the IskIn skill bundle used for the evidence in the permitted evidence or telemetry record.
4. Reuse existing evidence only after verifying its scope, provenance, and proof relevance. A textual skill improvement alone does not invalidate evidence.
5. Invalidate evidence only when an evidence-significant dependency changed: an obligatory process/evidence contract, the verified scope, or another required interface. Preserve historical evidence and record the required invalidation event.
6. Set `proved` only when the approval barrier is confirmed and every approved mandatory gate, canonical artifact, proof record, and current fingerprint requirement succeeds. An implementation without confirmed approval cannot receive canonical product proof or transition to `proved`. Do not set `accepted` without a human decision or pre-approved rule.

## Authority boundary

This skill does not weaken gates, bypass the approval barrier, manufacture evidence, overwrite historical evidence, or treat transient output as canonical proof.

Completion criterion: each mandatory gate, provenance link, skill revision, evidence gap, and outcome status is recorded and read back with the status limited to what evidence supports.
