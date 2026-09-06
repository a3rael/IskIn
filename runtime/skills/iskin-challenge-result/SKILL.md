---
name: iskin-challenge-result
description: "Use when an established challenge trigger requires independent critical review."
version: 0.4.0-dev
metadata:
  hermes:
    tags: [iskin, challenge, evidence]
    related_skills: [iskin-prove-result, iskin-control-pilot]
---

# Challenge an IskIn result

## Applicability

Use only when a trigger in `process/quality-gates.md` requires challenge and an IskIn project structure is present. Otherwise return `not applicable` without changing files.

## Procedure

1. Read the trigger, claimed result, `process/quality-gates.md`, `process/evidence-provenance.md`, and durable evidence without relying on the implementation agent's self-assessment.
2. Perform an independent critical check: seek a reproducible counterexample, evidence gap, or stated search boundary.
3. Do not alter checked implementation, lifecycle, criteria, or acceptance while challenging it.
4. With write authority, store only reproducible findings in the canonical evidence and telemetry locations. With read-only authority, return the finding, scope, and remaining uncertainty in the response without writing files.

## Authority boundary

A challenge observation without evidence does not change outcome state. This skill does not create unrelated product changes or bypass human gates.

Completion criterion: the result identifies the trigger, independent check, observed evidence or gap, remaining uncertainty, and canonical storage location when a write was permitted.
