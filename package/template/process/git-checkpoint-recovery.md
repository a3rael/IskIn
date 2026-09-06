# Git checkpoint и recovery

Этот документ — единственная каноническая точка шаблона для durable checkpoint и восстановления между сессиями. Он дополняет `process/operating-model.md`, `process/autonomy-policy.md`, `process/action-selection.md` и `process/evidence-provenance.md`; остальные документы не дублируют его полный контракт.

## Recovery preflight

Новая сессия сначала запускает глобальный `iskin-control-pilot`, который вызывает `iskin-understand-state`. Transcript Hermes — только вспомогательный источник. Сессия читает Git branch, `HEAD`, status и diff, затем `product-memory/`, evidence, `telemetry/`, process policy и фактическую версию/revision skill bundle.

Она восстанавливает active outcome, lifecycle, последний завершённый шаг, evidence, authority boundaries и next action. Каждый факт помечается как подтверждённый или требующий проверки.

## Clean tree

При clean tree `HEAD` — last stable checkpoint. Из проектных источников должны восстанавливаться active outcome, lifecycle, актуальное evidence и next action. Актуальное evidence не повторяется без evidence-significant причины.

## Dirty tree

При dirty tree предполагается возможное прерывание (interruption) между checkpoint. Изменения сохраняются. Сначала определяется их фактическое состояние, выполняются read-back и проверка возможных side effects. Сессия различает завершённые и незавершённые действия и продолжает работу, перепроверяет её или эскалирует вопрос на основании фактов и полномочий.

Слепые reset, delete, stage и commit запрещены. Нельзя автоматически откатывать или удалять незавершённые изменения.

## Checkpoint commit

Hermes может создать локальный checkpoint commit только после одного цельного verified transition, если:

- применимые обязательные проверки прошли;
- product memory, lifecycle, evidence и telemetry согласованы;
- записанные данные перечитаны;
- staged scope точен и не содержит посторонних пользовательских изменений;
- `git diff --cached --check` проходит;
- результат внешнего действия не остаётся неизвестным.

Commit фиксирует согласованные product files, outcome/lifecycle, evidence/provenance, telemetry, next action и authority boundaries. Количество коммитов не является метрикой успеха. Remote, push, tag, merge и publication требуют отдельного human decision.

## Skill bundle compatibility

Фактический skill bundle revision фиксируется в evidence или telemetry. Textual skill change alone не invalidates evidence. Incompatible изменение обязательного process, state или provenance contract требует остановки или явной миграции.

Automatic update global skills во время цикла не выполняется. Версия skills не заменяет проверку применимости, evidence scope или process contract.

## Граница шаблона

Шаблон предполагает заранее доступный global runtime bundle `iskin-*`; project-local skills отсутствуют намеренно. Если global skills недоступны или структура ИскИн не подтверждена, сессия сообщает конкретный blocker и не изменяет продукт.
