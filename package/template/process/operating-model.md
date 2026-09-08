# Операционная модель

## Разделение состояния

| Слой | Канонический источник | Правило изменения |
|---|---|---|
| Immutable product specification | `product-memory/approval-packages/<package_id>.md` и одноимённый `.json` index | после approval только новая package revision и human approval |
| Lifecycle history | `product-memory/lifecycle-events/<event_id>.json` | append-only, без редактирования и удаления |
| Human-readable projections | `intent.md`, `outcomes.md`, `uncertainties.md`, `evidence.md` | текущие представления, сверяются с event log |
| Evidence/provenance | paths из lifecycle event и canonical proof records | новые versioned artifacts, stale/invalidation fail closed |
| Управление | approval/acceptance в `decisions.md`, telemetry | отдельные human decisions и append-only записи |

Gate не делает произвольный semantic Markdown parse. Машинная истина — package index и lifecycle events; projections содержат проверяемые markers:

```text
<!-- iskin-lifecycle-event: <event_id> -->
<!-- iskin-outcome-id: <outcome_id> -->
<!-- iskin-status: <status> -->
```

`outcomes.md` и `evidence.md` должны ссылаться на последний event для текущего outcome. Несогласованность блокирует lifecycle checkpoint и recovery.

## Виды состояния

| Состояние | Содержит | Вопрос |
|---|---|---|
| Спецификация | Ценность, MVP boundary, outcome definitions, gates, evidence scopes, uncertainties | Что утверждено? |
| Работа | Активный outcome, риски и зависимости | Что мешает продвинуться? |
| Доказательства | Проверки, сборки, provenance и приёмка | Что подтверждено? |
| Управление | Полномочия, решения, метрики и уроки | Кто и почему выбирает следующий шаг? |

## Lifecycle результата

```text
proposed → approved → in-progress → evidence-pending → proved → accepted
                         ↓             ↓              ↓          ↓
                       blocked ←──────┘              reopened ←──┘
                         ↓              ↑
                         └──────────────┘
```

Допустимые переходы задаются одной state machine в executable gate:

- `proposed → approved`;
- `approved → in-progress`;
- `in-progress → evidence-pending|blocked`;
- `evidence-pending → proved|blocked`;
- `proved|accepted → reopened`;
- `blocked|reopened → in-progress|evidence-pending`.

После approval начальное доказанное состояние outcome — `approved`; обычные переходы через `lifecycle_checkpoint` не требуют новой package revision. Изменение specification требует новой revision.

`proved` может установить Hermes только с актуальными evidence/provenance refs. `accepted` требует отдельного human decision. `reopened` — событие возврата, после которого следующий переход должен быть явным.

## Две оси цикла

`Outcome status` описывает состояние продуктового результата.

`Cycle closure` описывает процессный итог цикла: `complete`, `process-incomplete` или `blocked`.

Process gap не должен маскироваться под product gap, а product evidence gap — под процессную неполноту.
