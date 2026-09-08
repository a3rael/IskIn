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

1. In every new session, run `python3 .iskin/policy_gate.py --action read_only_recovery`, then begin with `iskin-understand-state`. Record both exit code and machine status. A missing gate or unsupported schema is `PROCESS_BLOCKED`/`UNSUPPORTED_PROJECT_STATE`: diagnose read-only only, with no migration, checks, telemetry, retroactive package/checkpoint, implementation, proof, or commit. Treat transcript only as supporting context, never as the canonical process state.
2. If the repository has no `HEAD`, require `BOOTSTRAP_REQUIRED` before any discovery or approval preparation. Run `python3 .iskin/policy_gate.py --action stage_bootstrap_baseline`; require exit `0`, then read its exact `allowed_paths` list. The gate is read-only: run scoped `git add -- <each returned path>` only, never `git add .` or a broad glob. Re-read the gate JSON, `git diff --cached --name-only --no-renames`, unstaged/untracked status, and `git diff --cached --check`; then run `--action bootstrap_checkpoint`. Continue only when exit is `0`, status is `BOOTSTRAP_REQUIRED`, and `bootstrap_checkpoint` is in `allowed_actions`; create only the local technical initial commit. The gate must not stage or commit. If any action is denied or scope differs, do not commit and report the blocker. After the commit rerun the gate and continue into discovery; bootstrap is not approval and does not authorize product work.
3. Use `iskin-choose-next-action` only after recovery produces confirmed state, including the approval state. Stop on a confirmed incompatibility of project state, lifecycle, process, approval, or evidence/provenance contract.
4. Continue from the last stable checkpoint when the worktree is clean. When it is dirty, investigate and verify unfinished changes before any action; never blindly reset, stage, commit, or discard them.
5. Before routing to `iskin-change-product` or `iskin-prove-result`, require a complete approval package in the immutable file referenced by registry `product-memory/approval-packages.md`, a pre-approval checkpoint commit made before the package was shown, and a durable append-only event under `product-memory` plus the human-readable `product-memory/decisions.md` reference with `implementation_authorized: true`. A discovery response, selected option, agreement with one package element, or lack of objection never satisfies this barrier. Without it, route only to discovery, package preparation, or the human decision.
6. After the human approval response, write exactly one new event and its human-readable references, stage only those paths, run `python3 .iskin/policy_gate.py --action approval_checkpoint`, and create the technical approval commit only after exit `0`. Then rerun `python3 .iskin/policy_gate.py --action change_product`; both exit `0` and `IMPLEMENTATION_ALLOWED` are required. No new human gate is created by the approval checkpoint. Confirm that the event references the same package ID and checkpoint SHA shown to the human, and that package paths still match that checkpoint. If the package changed, invalidate the old approval and require a new package/checkpoint/approval sequence.
7. Route one bounded change through `iskin-change-product`, then route evidence work through `iskin-prove-result`. Invoke `iskin-challenge-result` only for an established trigger.
8. Before a lifecycle or checkpoint commit, run `python3 .iskin/policy_gate.py --action checkpoint`; require exit `0` and the action-specific allowed status. A non-zero result blocks the commit. Avoid repeating current evidence without a documented reason.
9. For an ordinary outcome transition, do not edit the immutable package or demand a new approval revision. Create one new versioned `product-memory/lifecycle-events/<event_id>.json`, update only matching projections/telemetry and related evidence/proof, then run `python3 .iskin/policy_gate.py --action lifecycle_checkpoint` and commit only after exit `0`. The event must follow the explicit state machine; `proved` requires current canonical evidence/provenance and `accepted` requires a human decision reference.
10. Reconcile outcome/lifecycle, evidence, telemetry, approval state, authority boundaries, human interventions, and next permitted action after a meaningful cycle.

## Authority boundary

This skill does not bypass human gates, resolve confirmed incompatibility by assumption, or perform external Git actions such as push, tag, merge, release, or publication.

Completion criterion: the cycle ends with one durable state snapshot that identifies the stable checkpoint, current outcome/lifecycle, evidence status, authority boundaries, and exactly one next permitted action or blocker.
