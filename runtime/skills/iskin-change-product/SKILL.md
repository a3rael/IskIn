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

Use only in an IskIn Git repository after recovery identifies one active outcome, one permitted action, a complete approved approval package, and a durable approval event with `implementation_authorized: true`. Otherwise return `not applicable` or `blocked` without changing files.

## Procedure

1. Read the active outcome, approval event, and `process/autonomy-policy.md`, `process/action-selection.md`, `process/quality-gates.md`, and `process/evidence-provenance.md`.
2. Make only the selected bounded change inside the approved package. Do not alter intent, quality gates, evidence scope, lifecycle policy, or authority boundaries without the required human decision.
3. Run every applicable check for this transition. Treat an unknown external result or unresolved error as incomplete, not as success.
4. Synchronize product memory and telemetry with the observed result, then set only the lifecycle state supported by the transition.
5. Prepare the precise checkpoint scope. Apply the canonical checkpoint model in `docs/architecture/v0.4-git-checkpoint-experiment.md`: read back durable records, exclude unrelated changes, and create a local checkpoint commit only after all required conditions are true.

## Authority boundary

This skill never deletes, resets, stages, or commits a dirty worktree blindly. It never performs push, tag, merge, release, or publication.

An answer to a discovery question, a selected option, agreement with one package element, lack of objection, or an intent file without the approval event is insufficient authority for this skill. If the approval barrier is absent, stop before changing product files.

Completion criterion: one bounded outcome transition, its checks, state updates, remaining evidence requirements, and any permitted checkpoint scope are traceable to durable project sources.
