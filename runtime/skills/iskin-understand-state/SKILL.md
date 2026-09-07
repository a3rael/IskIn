---
name: iskin-understand-state
description: "Use when entering an IskIn project, starting a new session, recovering after interruption, or facing unclear state."
version: 0.4.0-dev
metadata:
  hermes:
    tags: [iskin, recovery, state]
    related_skills: [iskin-choose-next-action, iskin-control-pilot]
---

# Understand IskIn state

## Applicability

Confirm that the current repository has Git metadata and the IskIn project structure: `process/`, `product-memory/`, and `telemetry/`. If it does not, return `not applicable` and do not change files.

## Recovery preflight

1. Read `process/operating-model.md`, `process/autonomy-policy.md`, and `process/evidence-provenance.md`.
2. Inspect Git branch, `HEAD`, status, and diff without changing the index or worktree.
3. Read product memory, evidence/proof records, and telemetry. Identify the active outcome, lifecycle, authority boundaries, last completed action, next recorded action, and approval state.
4. If the worktree is clean, identify `HEAD` as the last stable checkpoint. If it is dirty, treat it as a possible interruption between checkpoints; separate confirmed changes from unknown effects and evidence gaps.
5. Report approval separately as `package absent|incomplete|prepared|approved`, pre-approval checkpoint present|absent|invalid, direct question present|absent, package shown in the previous agent turn|not confirmed, durable event present|absent|inconsistent, and `implementation_authorized` granted|not granted. Never infer approval from transcript, a filled intent, an outcome status, a selected option, lack of objection, or a code diff.
6. A package that exists only in the dirty tree, a checkpoint containing product code/evidence, or a package not shown before the approval response is not approval. If product changes exist in a dirty tree without a confirmed approval event, classify the state as `process-blocked` and do not continue implementation, product proof, or checkpoint creation.
7. For an approval event, verify package ID, checkpoint SHA, `package_displayed_in_previous_agent_turn: true`, the exact question and human response, actor, authorization, and byte equality of every package path against the checkpoint.
8. Return a compact recovery snapshot: confirmed facts, unverified facts, active outcome/lifecycle, approval state, checkpoint state, blockers, authority boundaries, and information required before choosing an action.

## Authority boundary

This skill is read-only. It does not repair state, delete or reset files, stage changes, create commits, or infer an external result from transcript alone.

Completion criterion: the recovery snapshot traces every claimed state fact to Git or durable IskIn project sources and explicitly labels every unresolved fact.
