---
name: understand-state
description: Use before substantial work to reconstruct factual project state from durable memory, code, and evidence.
version: 0.3.0
metadata:
  hermes:
    tags: [state, evidence, project]
    related_skills: [choose-next-action, control-pilot]
---

# Understand state

1. Read `AGENTS.md` and the applicable files in `process/`, `product-memory/` and `telemetry/`.
2. Inspect the current product, configuration and available evidence. Use read-back facts, not chat claims.
3. Separate verified facts, assumptions, active outcomes, blockers, regressions and evidence gaps.
4. Record skill resolution for every required project skill as `runtime-project`, `file-only`, `missing` or `unstable`.

Return a compact state snapshot containing the target outcome, accepted facts, applicable gates, open gaps and the highest-leverage next decision. Do not change intent, criteria or policy while reconstructing state.

Completion criterion: the current outcome, mandatory gates, evidence gaps, process state and next decision are traceable to durable files.
