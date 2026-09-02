---
name: control-pilot
description: Use after a meaningful cycle to reconcile durable state, provenance, autonomy boundaries, and process health.
version: 0.3.0
metadata:
  hermes:
    tags: [control, reconciliation, provenance]
    related_skills: [understand-state, prove-result, challenge-result]
---

# Control pilot

After every meaningful cycle, reconcile outcomes, uncertainties, evidence, decisions and telemetry.

Keep product state and process state separate. Check the outcome lifecycle, applicable gates, cycle closure, skill resolution, provenance, fixture coverage, human interventions, process deviations and next allowed action.

Treat a proof as canonical only when its command, repository runner, gate-specific pre-run manifest, unique `run_id`, versioned report, proof-record with matching hashes and durable artifact are all present.

Run provenance checkpoints only at the defined boundaries. On mismatch, preserve the old proof, record an `invalidation_event` and reopen the current outcome.

Detect and record proved-without-gate, hidden mandatory gaps, ad-hoc evidence presented as canonical, missing scopes, overwrites, state mismatches, unrecorded interventions and forbidden next outcomes.

Completion criterion: the reconciliation report states product result, process result, provenance result, open gaps, interventions, next-action permission and any required correction.
