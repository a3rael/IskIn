# Метрики эксперимента agent-native PDLC

Метрики разделяют обязательный порог качества и безопасности, продуктовую доказанность и процессную эффективность. Качество и безопасность не обмениваются на скорость. После прохождения обязательного порога telemetry используется для итерационной оптимизации продуктового результата, автономности, времени, инструментальных затрат и повторной работы.

Исторические значения v0.2/v0.3 не пересчитываются. Freeze counter v0.3 и его критерии стабильности остаются историческим versioned process-control, а не заменяются этой формулировкой цели.

## Порядок оценки

1. Проверить обязательные продуктовые гейты, provenance и отсутствие необработанных safety/evidence gaps.
2. Оценить принятый продуктовый результат.
3. Измерить human steering, эскалации и способность к автономному выбору.
4. Измерить elapsed time, инструментальные затраты и повторную работу.
5. Учесть ограничения Hermes: tool-call limits, session recovery, permissions, runtime skills и Hermes Desktop infrastructure.
6. Проверять переносимость на втором полигоне; fixed-workflow comparison не является обязательной метрикой или критерием успеха.

| Метрика | Определение |
|---|---|
| `proved_without_complete_product_gate` | Число случаев, когда outcome получил `proved` при незакрытом обязательном продуктовом гейте. Цель: `0`. |
| `evidence_pending_returns` | Число возвратов outcome в `evidence-pending` из-за обязательного продуктового evidence gap. |
| `blocked_cycles` | Число циклов с `Cycle closure: blocked`. |
| `process_incomplete_cycles` | Число циклов с `Cycle closure: process-incomplete`. |
| `canonical_run_coverage` | Доля proof-попыток, где сохранены команда, repository runner и durable artifact/link. |
| `fixture_coverage_by_gate` | Доля proof-попыток с полной проверкой fixture, требуемого конкретным гейтом. |
| `evidence_gap_recording_rate` | Доля обнаруженных gaps, записанных в `product-memory/uncertainties.md` и связанных с evidence/run-log. |
| `evidence_gap_closure_rate` | Доля закрытых обязательных продуктовых gaps от числа открытых за период. |
| `state_consistency_pass_rate` | Доля циклов без расхождения между outcome, гейтами, evidence, uncertainties и telemetry. |
| `process_deviation_count` | Число расхождений фактического процесса с правилами. |
| `skill_resolution_distribution` | Число циклов по статусам `runtime-project`, `file-only`, `missing`, `unstable`. |
| `human_intervention_count` | Число ручных вмешательств, записанных в run-log. |
| `human_intervention_rate` | `human_intervention_count / substantial_cycles`. |
| `human_intervention_reason_distribution` | Распределение вмешательств по причинам: evidence, status, blocker, tooling, scope, override. |
| `next_outcome_override_count` | Число случаев начала независимого outcome при открытом обязательном продуктовом evidence gap по явному решению человека. |
| `gate_manifest_coverage` | Доля canonical proof-попыток с manifest до запуска, уникальным `run_id`, отдельными G1/G3 scopes и SHA-256 каждого входа. Цель: `100%`. |
| `versioned_proof_record_coverage` | Доля завершённых proof-попыток с report и proof-record одной версии и одного `run_id`, где зафиксированы SHA-256 manifest и report. Цель: `100%`. |
| `historical_artifact_overwrite_attempts` | Число попыток перезаписать manifest, report или proof-record существующего запуска. Цель: `0`. |
| `fingerprint_checkpoint_coverage` | Доля требуемых checkpoint перед `proved`, следующим независимым outcome и изменением scope-файла, выполненных и записанных. Цель: `100%`. |
| `invalidation_event_rate` | Доля обнаруженных drift-событий с durable `invalidation_event` и корректировкой статуса. Цель: `100%`. |
| `intervention_event_recording_rate` | Доля человеческих решений, меняющих статус, scope, действие, правило или исключение, записанных как structured `intervention_event`. Цель: `100%`. |
| `freeze_counter` | Число завершённых существенных циклов v0.3 из трёх: `0/3`, `1/3`, `2/3`, `3/3`. Process-only изменение и статические проверки не считаются. |

## Метрики итерационной оптимизации

| Метрика | Определение |
|---|---|
| `accepted_outcome_rate` | Доля outcomes, которые после обязательных gates и воспроизводимого evidence получили явное human acceptance. |
| `elapsed_time_seconds` | Время от начала выбранного существенного цикла до его prove/control closure; process-only и ожидание human decision выделяются отдельно. |
| `tool_call_count` | Число tool-вызовов в цикле с отдельным учётом повторных и восстановительных вызовов. |
| `tool_limit_resumptions` | Число возобновлений после внешнего ограничения лимитом tool-вызовов. |
| `rework_attempts` | Дополнительные implementation, focused-check и canonical attempts, вызванные ошибкой, drift, supersession или неполным доказательством. |
| `repeat_proof_count` | Число новых canonical proofs после первой proof-попытки для того же outcome; причины классифицируются отдельно. |
| `invalidated_proof_count` | Число исторических proofs, переставших применяться к текущей версии входов из-за evidence-relevant drift. |
| `hermes_permission_blocked_actions` | Число действий, остановленных permission/approval-механизмом Hermes до выполнения требуемого шага. |
| `session_recovery_count` | Число восстановлений состояния между сессиями или после потери непрерывности контекста. |
| `runtime_skill_resolution` | Распределение циклов по `runtime-project`, `file-only`, `missing`, `unstable` с отдельной оценкой влияния на product proof и cycle closure. |
| `desktop_infrastructure_incidents` | Наблюдаемые инциденты Hermes Desktop, влияющие на выполнение, маршрутизацию, ввод, окна или read-back. |

Эти метрики не разрешают ослаблять quality/safety floor. Улучшение считается допустимым только если обязательные product gates, provenance и lifecycle discipline остаются закрытыми.

Ручное вмешательство — действие человека, меняющее выбранный шаг, статус, трактовку гейта, scope или правило, а также явное решение об исключении. Для каждого вмешательства фиксируются цикл, причина, цель, действие и последствия.

## Метрики Test Automation Addendum

| Метрика | Текущее наблюдение в run `20260831T185729Z-1879` |
|---|---|
| `ui_checks_via_xcuitest_share` | `1/1` критических UI-сценария, `100%` при ненулевом знаменателе |
| `computer_use_runs` | `0` |
| `xcodebuild_test_duration_seconds` | `25` |
| `external_paid_check_cost` | `N/A` |
| `required_screenshot_attachments` | `3/3`, `PASS` |

Значения относятся только к этому run и не пересчитывают исторические v0.2/v0.3 записи.

## Наблюдение после завершения автономного прогона — 2026-09-01

Показатели за весь завершённый autonomous run после human acceptance P0-02—P0-05:

| Метрика | Значение |
|---|---:|
| `substantive_human_steering_interventions` | `0` |
| `mandatory_product_escalations` | `0` |
| `technical_resumptions_after_tool_limit` | `2` |

Эта запись фиксирует отдельные наблюдаемые показатели и не изменяет определения базовых метрик или исторические значения.
