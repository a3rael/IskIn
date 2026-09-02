---
name: change-product
description: Use for a bounded product change serving one active outcome while preserving approved rules and evidence requirements.
version: 0.3.0
metadata:
  hermes:
    tags: [implementation, outcome, change]
    related_skills: [choose-next-action, prove-result]
---

# Change product

Work on one active outcome at a time. Read its intent, criteria, dependencies, uncertainties and applicable gates before changing files.

Keep the change bounded and reversible. Add or update checks that express the expected observable behavior. Do not widen scope, alter policy or silently change acceptance criteria.

When implementation is complete, set the outcome to `evidence-pending` through the project memory workflow and hand off to `prove-result`. Do not set `proved` or `accepted` yourself.

Record assumptions, incomplete evidence and process deviations in the appropriate durable files.

Completion criterion: the bounded change and its remaining evidence requirements are traceable to one outcome.
