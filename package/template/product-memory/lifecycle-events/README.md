# Lifecycle events

`<event_id>.json` — versioned append-only machine-readable transition event. The directory is mutable project state and is not part of the immutable installation core.

Schema version `1` has exactly these fields:

- `schema_version`, `event_type: lifecycle`, `event_id`;
- `outcome_id`, `package_id`, `package_checkpoint_sha`;
- `from_status`, `to_status` from the explicit state machine in `process/operating-model.md`;
- `actor`, `reason`;
- `evidence_refs`, `proof_refs`, `human_decision_ref`;
- `occurred_at_utc`, `git_parent_sha`.

The event is staged together with the current projections and related evidence/proof paths, then authorized by:

```text
python3 .iskin/policy_gate.py --action lifecycle_checkpoint
```

The gate checks that the event is new, its Git parent is the current `HEAD`, its transition follows the current state, and its package checkpoint is the approved one. Existing events are never edited or deleted.
