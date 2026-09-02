# ИскИн в установленном проекте

Этот файл — точка входа для Hermes Agent и Hermes Desktop Project. Он задаёт границы и указатели; подробные правила находятся в канонических документах ниже.

## Перед работой

1. Прочитай `process/operating-model.md`, чтобы восстановить четыре вида состояния и lifecycle.
2. Прочитай `process/autonomy-policy.md` перед действием с побочным эффектом.
3. Прочитай `process/action-selection.md` перед выбором следующего действия.
4. Для проверки результата используй `process/quality-gates.md` и `process/evidence-provenance.md`.
5. Состояние конкретного продукта находится в `product-memory/`; фактические циклы и ограничения Hermes — в `telemetry/`.
6. Загрузи только утверждённые проектные навыки из `.hermes/skills/` и отдельно зафиксируй фактический runtime skill resolution.

## Границы

- Пакет универсален: в нём нет заранее заполненных product outcomes, quality gates, evidence, runner-ов или исторических статусов.
- Hermes предлагает и оформляет черновики intent, outcomes, uncertainties, quality gates, evidence scopes и product-specific runners.
- Человек утверждает продуктовую цель, критерии результата, значимые продуктовые решения, изменения process policy и финальный acceptance.
- Пользователь не обязан вручную проектировать гейты или заполнять процессные документы; Hermes готовит черновики и показывает вопросы для human gate.
- Product/toolchain-specific код и команды принадлежат установленному проекту, а не этому шаблону.
- Наличие файла навыка не доказывает его runtime-доступность в текущей сессии Hermes.
- Не объявляй outcome `proved` или `accepted` без обязательных воспроизводимых evidence и соответствующего human gate.
- Не подменяй каноническое evidence временным выводом, mock-проверкой или заявлением агента.

## Канонические источники

| Правило или состояние | Источник |
|---|---|
| Виды состояния и lifecycle | `process/operating-model.md` |
| Полномочия и human gates | `process/autonomy-policy.md` |
| Приоритет следующего действия | `process/action-selection.md` |
| Product gates и challenge по риску | `process/quality-gates.md` |
| Manifest, report, proof-record и invalidation | `process/evidence-provenance.md` |
| Intent, outcomes, uncertainties, decisions и evidence | соответствующие файлы `product-memory/` |
| Определения telemetry | `telemetry/metrics.md` |
| Фактические циклы и ограничения Hermes | `telemetry/run-log.md` |

## Утверждённые навыки

- `understand-state`
- `choose-next-action`
- `change-product`
- `prove-result`
- `challenge-result`
- `control-pilot`

## После существенного цикла

Выполни `control-pilot`: сверь outcome status и cycle closure, обязательные gates, provenance, skill resolution, intervention events, ограничения Hermes и следующий разрешённый шаг. При drift сохрани старое evidence, создай `invalidation_event` и переведи outcome в `reopened`, `evidence-pending` или `blocked` по фактическому состоянию.
