# Архитектура ИскИн v0.4

## Слои

### Универсальное ядро

Доменный и процессный контракт ИскИн: четыре вида состояния, lifecycle результата, outcome status, cycle closure, ограниченная автономность, human gates, воспроизводимое evidence, provenance, challenge и telemetry.

Источники истины ядра в установленном проекте:

- `process/` — правила процесса и provenance;
- `product-memory/` — состояние конкретного продукта: immutable approval specification отделена от append-only lifecycle events и projections;
- `telemetry/` — факты выполнения и измерения.

### Hermes-интеграция

Интеграционный слой — устанавливаемый `AGENTS.md` и шесть проектных навыков в `.hermes/skills/`. Он связывает универсальный контракт с Hermes Agent и Hermes Desktop Project, фиксирует обязательный ручной шаг `hermes skills trust`, runtime skill resolution, permission blocks, session recovery и tool-call limits. Полный порядок проверки находится в `docs/integration/hermes-desktop.md`.

Наличие файла навыка и результат `hermes skills list` не доказывают его runtime-доступность. Доказательством считаются только наличие имени в runtime-каталоге текущей сессии и успешная загрузка навыка по имени. Статус разрешения навыка фиксируется отдельно как `runtime-project`, `file-only`, `missing` или `unstable`.

### Продуктовая адаптация

Установленный проект сам заполняет продуктовое намерение, outcomes, гейты, scopes, runners, evidence и telemetry. Код, тесты, команды и окружение продукта не входят в универсальный пакет.

### Установка

`installer/` отвечает только за проверяемое локальное размещение версии пакета. Установщик не является частью продуктового процесса и не изменяет глобальную конфигурацию Hermes.

### Экспериментальная лаборатория

`experiments/` содержит исторические полигоны. Их документы, правила, статусы и product memory используются для анализа наблюдений, но не являются инструкциями центрального репозитория.

### Проектируемый эксперимент v0.4

Первый v0.4 эксперимент использует Git-based product sandbox: проверенный локальный commit является durable checkpoint законченного перехода, а новая сессия восстанавливает состояние из Git и project state, не из transcript. Полная спецификация двух сценариев и каноническая checkpoint model находятся в `v0.4-git-checkpoint-experiment.md`; утверждённое решение — `../decisions/2026-09-06-v0.4-git-checkpoint-experiment.md`.

Global bundle v0.4 проектируется только в `runtime/skills/`; его граница зафиксирована в `../decisions/2026-09-06-v0.4-runtime-skill-boundary.md`. Bundle не установлен в Hermes. v0.3 project skills и установленный пакет остаются неизменным baseline.

### Specification и lifecycle state

Approval package — это immutable human-readable specification и machine-readable companion/index. Текущий outcome status, evidence и telemetry не входят в package paths. Они изменяются через versioned lifecycle events и проверяемые projections. Подробная архитектура: `v0.4-specification-lifecycle-state.md`; решение: `../decisions/2026-09-08-v0.4-specification-lifecycle-state.md`.

## Правило единственного источника

Каждое правило имеет один канонический источник. `AGENTS.md` содержит указатели и границы полномочий; подробные правила находятся в `process/`; факты продукта — в `product-memory/`; наблюдаемые циклы — в `telemetry/`. Исторический материал не дублируется в `package/`.
