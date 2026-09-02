---
name: prove-result
description: Produce reproducible evidence that an active product outcome meets its criteria, and identify insufficient or contradictory evidence.
---

# Prove result

Read the outcome's observable behavior, `process/quality-gates.md`, `process/evidence-provenance.md`, current evidence and uncertainties. Identify only the applicable product gates and their gate-specific fixture; do not import a fixture or scope from another gate.

Before checking product behavior, record skill resolution for every required project skill as `runtime-project`, `file-only`, `missing`, or `unstable`. A tooling or indexing gap is a process gap, not a product gate, unless it prevents an applicable product check.

## Provenance-first run

For a canonical run, before invoking the command:

1. assign a unique `run_id` and create a new run directory;
2. write an immutable manifest containing the command, runner, environment and SHA-256 for every input in each applicable gate scope;
3. for P0-02 use the exact G1/G3 scopes in `process/evidence-provenance.md`; `BudgetCoreChecks.swift` is G3-only;
4. fail before product execution if the run directory or manifest already exists.

Run each applicable build, static, domain-rule and UI check. For every check record `gate_id`, `check`, `applicable_fixture`, `expected`, `observed`, `run_status` and artifact location. Do not run the canonical P0-02 command merely to validate this skill change.

After execution, write a new versioned report and proof-record in the same run directory. Both must contain the same `run_id`; the proof-record must contain the manifest SHA-256 and report SHA-256, gate results, actual result and durable artifact links. Never overwrite a manifest, report, proof-record or historical report. A temporary command or output is `ad-hoc` and cannot set `proved`.

Before setting `proved`, before starting the next independent outcome, and before changing a file in the scope of a proved result, run the fingerprint checkpoint. On drift, create a structured `invalidation_event`, preserve historical evidence for the old version and keep or return the current outcome to `evidence-pending` or `blocked`.

Use the single outcome lifecycle status: `proposed`, `active`, `evidence-pending`, `proved`, `accepted`, or `blocked`. Keep a separate cycle field:

```text
Cycle closure: complete | process-incomplete | blocked
```

`file-only` or unstable skill resolution normally makes `Cycle closure: process-incomplete`; it does not by itself prevent product `proved`. Missing product evidence keeps the outcome `evidence-pending`; inability to run a mandatory product check makes it `blocked`.

Finish every run with:

```text
Outcome:
Outcome status:
Cycle closure:
Applicable gates:
Run ID:
Manifest:
Canonical command:
Repository runner:
Versioned report:
Versioned proof-record:
Fixture coverage:
Fingerprint checkpoints:
Invalidation events:
Evidence gaps:
Process deviations:
Skill resolution:
Next allowed action:
```

Record exact evidence, failures, limitations, process deviations, invalidation events and structured human interventions in `product-memory/evidence.md` and `telemetry/run-log.md`. Do not substitute a narrative claim for a check.
