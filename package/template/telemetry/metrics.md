# Метрики ИскИн

Фиксируй значения только после наблюдаемого цикла. Нулевой знаменатель отмечай как `N/A`, а не как 100%.

| Метрика | Определение |
|---|---|
| `proved_without_complete_product_gate` | Число outcomes, получивших `proved` без всех обязательных гейтов. Цель: `0`. |
| `canonical_run_coverage` | Доля proof-попыток с командой, repository runner и durable artifact/link. |
| `fixture_coverage_by_gate` | Доля proof-попыток с полной fixture-проверкой для конкретного гейта. |
| `state_consistency_pass_rate` | Доля циклов без расхождений между durable-источниками. |
| `human_intervention_count` | Число структурированных human interventions. |
| `human_intervention_rate` | `human_intervention_count / substantial_cycles`. |
| `elapsed_time_seconds` | Время существенного цикла с отдельным учётом ожидания решения человека. |
| `tool_call_count` | Число вызовов инструментов с отдельным учётом повторов и восстановления. |
| `rework_attempts` | Повторные implementation/check/proof попытки из-за ошибки, drift или неполного evidence. |
| `invalidated_proof_count` | Число исторических proof, потерявших применимость из-за drift. |
| `permission_blocked_actions` | Действия, остановленные approval-механизмом до выполнения. |
| `session_recovery_count` | Восстановления состояния между сессиями. |
| `tool_limit_resumptions` | Возобновления после ограничения числа вызовов инструментов. |
| `skill_resolution_distribution` | Распределение `runtime-project`, `file-only`, `missing`, `unstable`. |
| `accepted_outcome_rate` | Доля outcomes с явным human acceptance после обязательных гейтов. |

Наблюдения и значения конкретных циклов записывай в `run-log.md`, а не в этот каталог определений.
