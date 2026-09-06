---
name: iskin-control-pilot
description: "Use when orchestrating an IskIn cycle or starting a new session."
version: 0.4.0-dev
metadata:
  hermes:
    tags: [iskin, control, recovery]
    related_skills: [iskin-understand-state, iskin-choose-next-action, iskin-prove-result]
---

# Control an IskIn cycle

## Applicability

Use only for an IskIn Git repository containing `process/`, `product-memory/`, and `telemetry/`. Otherwise return `not applicable` without changing files.

## Procedure

1. In every new session, begin with `iskin-understand-state`. Treat transcript only as supporting context, never as the canonical process state.
2. Use `iskin-choose-next-action` only after recovery produces confirmed state. Stop on a confirmed incompatibility of project state, lifecycle, process, or evidence/provenance contract.
3. Continue from the last stable checkpoint when the worktree is clean. When it is dirty, investigate and verify unfinished changes before any action; never blindly reset, stage, commit, or discard them.
4. Route one bounded change through `iskin-change-product`, then route evidence work through `iskin-prove-result`. Invoke `iskin-challenge-result` only for an established trigger.
5. Avoid repeating current evidence without a documented reason. Create a local checkpoint commit only after one complete verified transition satisfies `process/autonomy-policy.md` and the canonical model in `docs/architecture/v0.4-git-checkpoint-experiment.md`.
6. Reconcile outcome/lifecycle, evidence, telemetry, authority boundaries, human interventions, and next permitted action after a meaningful cycle.

## Authority boundary

This skill does not bypass human gates, resolve confirmed incompatibility by assumption, or perform external Git actions such as push, tag, merge, release, or publication.

Completion criterion: the cycle ends with one durable state snapshot that identifies the stable checkpoint, current outcome/lifecycle, evidence status, authority boundaries, and exactly one next permitted action or blocker.
