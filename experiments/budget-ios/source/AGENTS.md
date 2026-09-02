# Agent-native PDLC pilot

This repository tests an agent-native Product Development Life Cycle in Hermes. The iOS Budget MVP is the first testbed, not the goal of the process.

## Source of truth

Before substantial work, read this file, then the relevant project state:

- `process/` — operating model, autonomy policy, action selection, and quality gates;
- `product-memory/` — approved intent, outcomes, uncertainties, evidence, and decisions;
- `telemetry/` — prior reasoning, actions, outcomes, and process losses.

Do not treat chat history or an agent's own claim as a source of truth when the corresponding project artifact is absent or contradictory.

## Operating rules

For every substantial cycle, explicitly use `understand-state`, then `choose-next-action`. Select further project skills only when their situation applies; do not run them as a fixed role workflow.

Choose actions by `process/action-selection.md`, remain within `process/autonomy-policy.md`, and keep work inside this repository. After a substantial cycle, update relevant evidence and telemetry.

Do not declare a result proved without reproducible evidence required by `process/quality-gates.md`.

Use `challenge-result` only for risk, conflicting evidence, weak coverage, or a likely blind spot. It is not a permanent reviewer role.

## Cycle contract v0.3

For every substantial cycle, follow `understand-state → choose-next-action → execution → prove-result → control-pilot` and apply `process/evidence-provenance.md` to every canonical product proof.

Keep two axes separate:

- `Outcome status` is the product lifecycle: `proposed`, `active`, `evidence-pending`, `proved`, `accepted`, `blocked`.
- `Cycle closure` is the process result: `complete`, `process-incomplete`, or `blocked`.

Set an outcome to `proved` only when every mandatory product gate for that outcome has reproducible evidence. An open mandatory product evidence gap keeps the outcome in `evidence-pending`; an unavailable required product check can make it `blocked`. A project-skill indexing or tooling gap alone affects `Cycle closure`, not product `proved`.

Record every cycle's outcome status, cycle closure, applicable gates, evidence gaps, process deviations, skill resolution, and next allowed action. Do not start a next independent outcome while an applicable mandatory product evidence gap is open, unless a human records an explicit override.

For P0-02, the proof is gate-specific: G1 and G3 have separate input scopes and SHA-256 fingerprints. A canonical proof must create a new run-specific manifest before execution and a versioned report/proof-record after execution; historical artifacts are never overwritten. Before `proved`, before a next independent outcome, and before changing a file in the scope of a proved result, perform the required fingerprint checkpoint. Drift creates an invalidation event and reopens the current result to `evidence-pending` or `blocked`.

The v0.3 freeze counter starts at `0/3` after human approval. The process-only change, static checks, and isolated drift-fixture template do not count as substantial product cycles. Human changes to status, scope, selected action, rule, or exception are recorded as structured intervention events.

## Human authority

Only a human may approve changes to product intent, acceptance criteria, autonomy policy, quality gates, this file, or the scope of the pilot.

Escalate one concrete decision when a product rule is ambiguous; an action is external, paid, privacy-sensitive, irreversible, or outside the repository; or two cycles fail to reduce a key uncertainty.

Do not publish, access external services, install dependencies, change global configuration, create commits, or perform irreversible actions unless the human explicitly authorizes that exact action.
