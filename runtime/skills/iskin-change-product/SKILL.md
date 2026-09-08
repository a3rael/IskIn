---
name: iskin-change-product
description: "Use when making one bounded change for an active IskIn outcome."
version: 0.4.0-dev
metadata:
  hermes:
    tags: [iskin, change, checkpoint]
    related_skills: [iskin-choose-next-action, iskin-prove-result]
---

# Change one IskIn outcome

## Applicability

Use only in an IskIn Git repository after recovery identifies one active outcome, one permitted action, a complete approved approval package, its pre-approval checkpoint commit, and a durable approval event with `implementation_authorized: true`. The event must reference the package ID and checkpoint SHA whose package paths remain unchanged. Otherwise return `not applicable` or `blocked` without changing files.

## Procedure

1. Run `python3 .iskin/policy_gate.py --action change_product` from the project root before reading or changing product files. Exit `0` **and** machine status `IMPLEMENTATION_ALLOWED` are required; any other exit, missing executable, `UNSUPPORTED_PROJECT_STATE`, or `PROCESS_BLOCKED` stops this skill without product checks, telemetry writes, or checkpoint work.
2. Read the active outcome, the canonical event `product-memory/approval-events/<event_id>.json`, its linked human-readable decision, and `process/autonomy-policy.md`, `process/action-selection.md`, `process/quality-gates.md`, and `process/evidence-provenance.md`.
3. Make only the selected bounded change inside the approved package. Do not alter package paths, intent, quality gates, evidence scope, lifecycle policy, or authority boundaries without invalidating the approval and requiring a new pre-approval checkpoint and human gate.
4. Run every applicable check for this transition. Treat an unknown external result or unresolved error as incomplete, not as success.
5. Synchronize projections and telemetry with the observed result by appending one lifecycle event under `product-memory/lifecycle-events/`; never rewrite or delete an old event and never put mutable status into the immutable approval package.
6. For a lifecycle-only transition, stage only the new event, matching projections/telemetry and related evidence/proof paths, then run `python3 .iskin/policy_gate.py --action lifecycle_checkpoint`. For implementation/product code use the separate product checkpoint scope; a lifecycle-only checkpoint must not contain arbitrary product code. Read back durable records and create a local checkpoint commit only after the action gate returns `0`.

## Authority boundary

This skill never deletes, resets, stages, or commits a dirty worktree blindly. It never performs push, tag, merge, release, or publication.

An answer to a discovery question, a selected option, agreement with one package element, lack of objection, or an intent file without the approval event is insufficient authority for this skill. If the approval barrier is absent, stop before changing product files.

Completion criterion: one bounded outcome transition, its checks, state updates, remaining evidence requirements, and any permitted checkpoint scope are traceable to durable project sources.
