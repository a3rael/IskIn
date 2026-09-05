---
name: challenge-result
description: Use when risk, weak coverage, conflicting evidence, or a likely blind spot warrants an independent read-only challenge.
version: 0.3.0
metadata:
  hermes:
    tags: [challenge, risk, evidence]
    related_skills: [prove-result, control-pilot]
---

# Challenge result

Run only when a trigger in `process/quality-gates.md` applies. Start from durable sources but do not rely on the implementation agent's self-assessment.

Work read-only with respect to the checked implementation and decision state. Try to falsify the claimed behavior with an independent check, adversarial scenario or invariant. The checked code, configuration, criteria, statuses and acceptance remain unchanged.

During an ordinary challenge run, results may be saved only in the designated evidence and telemetry locations. If the user explicitly prohibits any writes, return the challenge result in the response without changing files. Do not describe the result as saved when no write was performed.

When writes are permitted, record a reproducible counterexample, evidence gap or explicit limit of the search in `product-memory/evidence.md` and `telemetry/run-log.md`. An opinion without evidence does not change the outcome.

Completion criterion: the challenge result states what was checked, what was observed, what remains unknown and where the evidence is stored.
