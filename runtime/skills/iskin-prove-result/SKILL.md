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

Use only for an IskIn outcome with a complete approved approval package, a pre-approval checkpoint commit, a durable approval event with `implementation_authorized: true`, approved applicable gates, and a defined evidence scope. The event must reference the package ID and checkpoint SHA, prove that the package was shown in the previous agent turn, and pass package-path drift checks. Otherwise return `not applicable` or `blocked` without changing files. Read-only diagnosis of existing state is allowed and does not create product proof.

## Procedure

1. Run `python3 .iskin/policy_gate.py --action prove_result` from the project root before any product check or evidence write. Require exit `0` and `IMPLEMENTATION_ALLOWED`; on any other exit, missing gate, `UNSUPPORTED_PROJECT_STATE`, or `PROCESS_BLOCKED`, return the read-only gate JSON and stop without running product checks or writing telemetry/evidence.
2. Read the outcome, approval package at its checkpoint revision, canonical event under `product-memory`, linked `decisions.md` reference, `process/quality-gates.md`, `process/evidence-provenance.md`, current evidence, and uncertainties.
3. Run only applicable canonical checks. Create or update canonical evidence, provenance, and proof records according to the project contract; read back every record written.
4. Record the version or revision of the IskIn skill bundle used for the evidence in the permitted evidence or telemetry record.
5. Reuse existing evidence only after verifying its scope, provenance, and proof relevance. A textual skill improvement alone does not invalidate evidence.
6. Invalidate evidence only when an evidence-significant dependency changed: an obligatory process/evidence contract, the verified scope, or another required interface. Preserve historical evidence and record the required invalidation event.
7. Set `proved` only by appending a lifecycle event with the current package checkpoint, outcome ID, canonical evidence refs and valid provenance/proof record; the approval barrier and every approved mandatory gate must succeed. An implementation without confirmed approval cannot receive canonical product proof or transition to `proved`.
8. Before committing the transition, run `python3 .iskin/policy_gate.py --action lifecycle_checkpoint` with the exact lifecycle-only/evidence scope. Do not set `accepted` without an explicit human decision reference or pre-approved rule; acceptance is a separate lifecycle event and does not mutate the package.

## Authority boundary

This skill does not weaken gates, bypass the approval barrier, manufacture evidence, overwrite historical evidence, or treat transient output as canonical proof.

Completion criterion: each mandatory gate, provenance link, skill revision, evidence gap, and outcome status is recorded and read back with the status limited to what evidence supports.
