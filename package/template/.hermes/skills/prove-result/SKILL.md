---
name: prove-result
description: Use to produce reproducible evidence that an active product outcome meets its approved criteria.
version: 0.3.0
metadata:
  hermes:
    tags: [evidence, provenance, verification]
    related_skills: [change-product, challenge-result, control-pilot]
---

# Prove result

Read the outcome, `process/quality-gates.md`, `process/evidence-provenance.md`, current evidence and uncertainties. Identify only the applicable product gates and each gate's own fixture and scope.

Before execution, record skill resolution and create a new run directory plus immutable manifest. The manifest must contain a unique `run_id`, command, repository runner, environment and SHA-256 for every input in every applicable gate scope.

Run the product's canonical commands and record gate, check, fixture, expected, observed, status and artifact location. A temporary command, mock or transient output is `ad-hoc` and cannot establish `proved`.

After execution, create a new versioned report and proof-record with the same `run_id`, manifest/report SHA-256 links, gate results and durable artifacts. Never overwrite an existing run.

Before `proved`, before the next independent outcome and before changing a file in a proved scope, run the fingerprint checkpoint. On drift, preserve historical evidence, create an `invalidation_event` and keep the current outcome `evidence-pending`, `reopened` or `blocked`.

When every pre-approved mandatory product gate has passed, canonical evidence and the proof-record have been created and read back, and the mandatory fingerprint checkpoint confirms that the scope is current, Hermes may set the outcome to `proved`. This is an evidence-derived status and does not require a separate human acceptance. Do not set `accepted`; that status requires a human decision or a separately pre-approved rule.

If evidence is incomplete, stale or contradictory, do not set `proved`; keep the outcome `evidence-pending`, `reopened` or `blocked` according to the actual state.

Completion criterion: every mandatory gate, artifact, provenance link, gap and deviation is recorded and read back, and the outcome transition is limited to the evidence-supported status.
