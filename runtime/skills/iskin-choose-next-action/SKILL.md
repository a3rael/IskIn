---
name: iskin-choose-next-action
description: "Use when selecting exactly one next action after a confirmed IskIn state recovery."
version: 0.4.0-dev
metadata:
  hermes:
    tags: [iskin, action-selection, autonomy]
    related_skills: [iskin-understand-state, iskin-change-product, iskin-prove-result]
---

# Choose one IskIn action

## Applicability

Use only after a recovery snapshot confirms an IskIn repository with `process/`, `product-memory/`, and `telemetry/`. Otherwise return `not applicable` without changing files.

## Procedure

1. Read `process/action-selection.md` and `process/autonomy-policy.md` with the recovered outcome, dependencies, evidence gaps, and authority boundaries.
2. Reject action selection if active outcome, lifecycle, checkpoint state, relevant evidence, or authority is not sufficiently confirmed. Return the missing fact or confirmed blocker instead.
3. Consider the allowed candidates. Prefer state reconciliation, a mandatory evidence gap, blocker reduction, regression repair, or the nearest approved outcome as defined by `process/action-selection.md`.
4. Select exactly one smallest reversible and observable action. State its expected evidence, stopping condition, and whether it may write files.
5. Record the choice only when the current authority and process policy permit that write; otherwise return the choice and required human decision without writing.

## Authority boundary

This skill does not widen scope, invent authority, start a different outcome, or execute the selected action. It does not select an action from an unconfirmed or dirty state merely to continue.

Completion criterion: exactly one permitted action is traceable to confirmed IskIn state and policy, or a concrete reason is returned for not selecting one.
