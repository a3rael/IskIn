# Шаблон ИскИн v0.4: global runtime

Шаблон задаёт проектную часть первого эксперимента ИскИн v0.4 для Hermes Agent и Hermes Desktop Project. Global skill bundle ИскИн должен быть установлен заранее в основном профиле Hermes; этот шаблон его не устанавливает.

Проект намеренно не содержит project-local copies skills. Канонический источник global bundle находится в development repository в `runtime/skills/`, а установленный проект использует namespaced skills `iskin-*` из Hermes runtime. Если global bundle недоступен, сначала сообщи конкретный blocker; не создавай локальные копии и не изменяй продукт.

## Перед работой

1. Прочитай `AGENTS.md` и начни новую сессию с глобального `iskin-control-pilot`.
2. Проверь фактическую загрузку skills в новой сессии; наличие файла или запись в CLI registry сами по себе не доказывают runtime-load.
3. Заполняй `product-memory/` только фактами конкретного продукта и решениями человека.
4. Hermes заполняет `telemetry/` во время эксперимента; исходный шаблон содержит пустые структуры и не содержит результатов текущего прогона.
5. Вызов `hermes skills trust` не является шагом установки v0.4: project trust нужен для project-local skills, которых в этом шаблоне нет.

## Процесс и recovery

Канонические process-документы:

- состояние и lifecycle — `process/operating-model.md`;
- полномочия и human gates — `process/autonomy-policy.md`;
- выбор действия — `process/action-selection.md`;
- gates и provenance — `process/quality-gates.md`, `process/evidence-provenance.md`;
- Git checkpoint и recovery — `process/git-checkpoint-recovery.md`.

Git обязателен. Чистое дерево восстанавливается от последнего checkpoint в `HEAD`; dirty tree сначала исследуется без слепого reset, delete, stage или commit. Remote, push, tag, merge и публикация требуют отдельного human decision.

## Граница первого эксперимента

Запланированное завершение сессии между проверенными переходами — часть экспериментального сценария и не считается содержательным human steering. Новая сессия должна восстановить состояние по Git, `product-memory/`, evidence и `telemetry/`, а transcript Hermes использовать только как вспомогательный источник.

Шаблон не содержит product outcomes, фактических evidence, telemetry или environment results. Подробные записи появляются только в созданном пользователем sandbox во время эксперимента.
