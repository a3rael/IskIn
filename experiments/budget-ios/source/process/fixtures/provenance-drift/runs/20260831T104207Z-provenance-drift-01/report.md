# Process-only provenance drift report

report_version: 1
run_id: `20260831T104207Z-provenance-drift-01`
status: `invalidation-detected`
execution_mode: `process-only`
product_evidence_created: `false`

## Sequence

1. **Scope drift:** only `scope-input.txt` changed from the content represented by the manifest.
2. **Fingerprint checkpoint:** expected SHA-256 `589c429b8ca7ed5f954465c3a44d7d02606e49e65f640dcba49430ba829a82b5`; observed SHA-256 `d3efeadfe09313d3cc531c3fa5e3415f2f6d9a8e600681092286b7e00f8b1fae`.
3. **Mismatch:** expected and observed fingerprints differ; checkpoint failed closed.
4. **Invalidation event:** `INV-PROC-20260831T104320Z` recorded in the proof-record.
5. **Synthetic outcome:** `evidence-pending` because the recorded proof no longer matches the current scope file.

## Provenance

- manifest: `manifest.json`
- manifest_sha256: `138522c7c9de2b11e5f4859442fe29590b3b1d7e38643123a987b18123fe8344`
- scope_file: `scope-input.txt`
- historical_input_version: `v1`
- observed_input_version: `v2`
- report remains immutable after proof-record creation; a correction requires a new run_id.

## Safety boundary

This was a synthetic process exercise only. No product command, product code, product evidence, or product outcome was executed or created. The exercise does not prove or change P0-02, P0-03, or any product gate.
