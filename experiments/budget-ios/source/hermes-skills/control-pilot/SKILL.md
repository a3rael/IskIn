---
name: control-pilot
description: Maintain the health of an agent-native PDLC pilot by reconciling durable state, checking autonomy boundaries, and proposing evidence-based process improvements.
---

# Control pilot

After every meaningful cycle, reconcile outcomes, uncertainties, evidence, decisions and telemetry. Keep two axes separate:

- product state: the single outcome lifecycle status and applicable product-gate evidence;
- process state: `Cycle closure`, provenance integrity, freeze counter and resolution of required project skills and rules.

Check that each outcome transition is supported by the applicable product gates. Check that the cycle records `Outcome status`, `Cycle closure`, gate results, `run_id`, manifest, versioned report/proof-record, fixture coverage, evidence gaps, process deviations, skill resolution and structured human interventions.

Treat a canonical run as valid only when the command, repository-saved execution method, gate-specific pre-run manifest with SHA-256 inputs, unique `run_id`, versioned report and proof-record with matching hashes, and durable artifact or stable link are all present. Treat a temporary command or output as `ad-hoc`; it cannot close a product gap.

## Provenance checkpoints

Run the scope fingerprint checkpoint only at these boundaries:

1. before `proved`;
2. before the next independent outcome;
3. before changing a file in the scope of a proved result.

If an expected and observed fingerprint differ, record a structured `invalidation_event` with event ID, run ID, gate, path, expected SHA-256, observed SHA-256 and consequence. Preserve the old proof as historical, reopen the current outcome to `evidence-pending` or `blocked`, and prevent the next independent outcome when a mandatory product gap is open.

Detect and record:

- `proved` without every mandatory product gate passing;
- an open mandatory product evidence gap hidden by a `proved` claim;
- an ad-hoc check presented as canonical evidence;
- missing gate-specific manifest or incomplete fixture coverage;
- a report/proof-record or manifest overwrite attempt;
- a mismatch between outcome, gate, evidence, uncertainties or telemetry;
- skill resolution of `file-only`, `missing` or `unstable`;
- a next independent outcome started while an applicable mandatory product evidence gap was open;
- an unrecorded human intervention, invalidation event or process deviation.

An open non-mandatory, research, process or tooling gap does not block the next independent outcome unless it prevents an applicable mandatory product gate. It does make the cycle `process-incomplete` when the process contract was not fully met.

Return:

```text
Cycle:
Outcome status:
Cycle closure: complete | process-incomplete | blocked
Product reconciliation: pass | mismatch
Process reconciliation: pass | mismatch
Applicable gates:
Run ID:
Manifest and scope fingerprints:
Versioned report/proof-record:
Fixture coverage:
Fingerprint checkpoints:
Invalidation events:
Evidence gaps:
Process deviations:
Skill resolution:
Human interventions:
Freeze counter:
Next independent outcome allowed: yes | no
Required correction:
```

When the same loss pattern recurs, propose a narrow change to a skill, gate or action-selection rule and record the hypothesis. Do not change process policy or product goal without human approval. The v0.3 process-only change and static checks start the freeze counter at `0/3`; they are not substantial product cycles.
