---
name: choose-next-action
description: Use after state reconstruction to select one reversible, high-leverage action from outcomes, risks, and evidence.
version: 0.3.0
metadata:
  hermes:
    tags: [action-selection, autonomy, process]
    related_skills: [understand-state, change-product, prove-result]
---

# Choose next action

Read `process/action-selection.md` and the current project memory. Consider at least two feasible actions when the choice is nontrivial.

Prefer, in order: state reconciliation, closure of a mandatory evidence gap, blocker reduction, regression repair, stronger evidence for a high-risk result, an applicable challenge, the nearest approved outcome, and only then a narrow process improvement.

Select the smallest reversible and observable action. Record considered actions, the choice, expected evidence and rationale in `telemetry/run-log.md` before execution.

Do not select an action outside `process/autonomy-policy.md`. Escalate one concrete human decision when the rule, scope or consequence is ambiguous.

Completion criterion: one allowed action and its expected evidence are recorded before execution.
