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

1. In every new session, run `python3 .iskin/policy_gate.py --action read_only_recovery`, then begin with `iskin-understand-state`. Treat transcript only as supporting context, never as the canonical process state.
2. Use `iskin-choose-next-action` only after recovery produces confirmed state, including the approval state. Stop on a confirmed incompatibility of project state, lifecycle, process, approval, or evidence/provenance contract.
3. Continue from the last stable checkpoint when the worktree is clean. When it is dirty, investigate and verify unfinished changes before any action; never blindly reset, stage, commit, or discard them.
4. Before routing to `iskin-change-product` or `iskin-prove-result`, require a complete approval package in the immutable file referenced by registry `product-memory/approval-packages.md`, a pre-approval checkpoint commit made before the package was shown, and a durable approval event in machine state plus the human-readable `product-memory/decisions.md` record with `implementation_authorized: true`. A discovery response, selected option, agreement with one package element, or lack of objection never satisfies this barrier. Without it, route only to discovery, package preparation, or the human decision.
5. After the human approval response, rerun `python3 .iskin/policy_gate.py --action change_product`; exit `0` is the only implementation permission. Confirm that the approval event references the same package ID and checkpoint SHA shown to the human, and that the package paths still match that checkpoint. If the package changed, invalidate the old approval and require a new package/checkpoint/approval sequence.
6. Route one bounded change through `iskin-change-product`, then route evidence work through `iskin-prove-result`. Invoke `iskin-challenge-result` only for an established trigger.
7. Before a lifecycle or checkpoint commit, run `python3 .iskin/policy_gate.py --action checkpoint`; a non-zero result blocks the commit. Avoid repeating current evidence without a documented reason.
8. Reconcile outcome/lifecycle, evidence, telemetry, approval state, authority boundaries, human interventions, and next permitted action after a meaningful cycle.

## Authority boundary

This skill does not bypass human gates, resolve confirmed incompatibility by assumption, or perform external Git actions such as push, tag, merge, release, or publication.

Completion criterion: the cycle ends with one durable state snapshot that identifies the stable checkpoint, current outcome/lifecycle, evidence status, authority boundaries, and exactly one next permitted action or blocker.
