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
2. Run `python3 .iskin/policy_gate.py --action read_only_recovery` and use its JSON `allowed_actions` as a prerequisite, not as a suggestion. Record both exit code and status; reject action selection on non-zero exit, `PROCESS_BLOCKED`, or `UNSUPPORTED_PROJECT_STATE`. If `HEAD` is absent, run `--action bootstrap_checkpoint`, require `DISCOVERY_ALLOWED` plus `INITIAL_BASELINE_UNCOMMITTED`, and select only the bootstrap handoff; never select product work or approval.
3. Reject action selection if active outcome, lifecycle, checkpoint state, relevant evidence, authority, or approval state is not sufficiently confirmed. Return the missing fact or confirmed blocker instead.
4. Consider the allowed candidates. Prefer state reconciliation, a mandatory evidence gap, blocker reduction, regression repair, or the nearest approved outcome as defined by `process/action-selection.md`.
5. If a complete approval package in its immutable package file, a pre-approval checkpoint commit made before display, or a durable append-only approval event under `product-memory` with a matching `decisions.md` reference and `implementation_authorized: true` is absent, select only discovery, package preparation, or waiting for the human decision. Do not select implementation or product proof because of a clarification answer, selected option, agreement with one package element, lack of objection, a generic «продолжай», or a technical authority grant.
6. Reject approval when the package was not shown in the previous agent turn, when the event references another package ID/checkpoint SHA, or when any package path drifted after the checkpoint.
7. Select exactly one smallest reversible and observable action. State its expected evidence, stopping condition, and whether it may write files.
8. Record the choice only when the current authority and process policy permit that write; otherwise return the choice and required human decision without writing.

## Authority boundary

This skill does not widen scope, invent authority, start a different outcome, or execute the selected action. It does not select an action from an unconfirmed or dirty state merely to continue, and it does not treat a discovery response as approval.

Completion criterion: exactly one permitted action is traceable to confirmed IskIn state and policy, or a concrete reason is returned for not selecting one.
