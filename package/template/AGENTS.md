# ИскИн в установленном проекте

Это короткая точка входа для Hermes Agent и Hermes Desktop Project. Навыки ИскИн v0.4 загружаются из глобального runtime; `runtime/skills/` — их канонический источник, а project-local copies отсутствуют намеренно.

## Вход в проект и новая сессия

1. Начни с глобального `iskin-control-pilot`.
2. Выполни recovery preflight через `iskin-understand-state`.
3. Каноническое состояние читай из Git, `product-memory/`, evidence и `telemetry/`; transcript Hermes используй только как вспомогательный источник.
4. При отсутствии global skills ИскИн или структуры проекта сообщи конкретный blocker до изменения продукта; вне структуры ИскИн навык неприменим.

## Канонические источники

- Виды состояния и lifecycle: `process/operating-model.md`.
- Полномочия и human gates: `process/autonomy-policy.md`.
- Выбор следующего действия: `process/action-selection.md`.
- Product gates и evidence: `process/quality-gates.md`, `process/evidence-provenance.md`.
- Git checkpoint и recovery: `process/git-checkpoint-recovery.md`.
- Определения telemetry: `telemetry/metrics.md`; фактические циклы: `telemetry/run-log.md`.

## Git и полномочия

Git — обязательная инфраструктура. Локальный checkpoint commit создаётся только после законченного проверенного перехода и согласованного read-back состояния. Remote, push, tag, merge и публикация требуют отдельного human decision. Полный контракт находится в `process/git-checkpoint-recovery.md`.

Не выполняй установку или доверие project-local skills для v0.4: global runtime bundle должен быть установлен заранее. Не изменяй продукт при неподтверждённой применимости, неизвестном external result или несогласованном dirty tree.
