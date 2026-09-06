# Шаблон ИскИн v0.3

Шаблон устанавливает универсальный процесс agent-native PDLC и интеграцию с Hermes Agent и Hermes Desktop Project.

После установки Hermes предлагает и оформляет черновики `intent`, `outcomes`, `uncertainties`, quality gates, evidence scopes и product-specific runners. В пределах своих полномочий Hermes собирает и записывает фактические evidence и telemetry.

Человек утверждает продуктовую цель, критерии результата, значимые продуктовые решения, изменения process policy и финальный acceptance. Пользователь не обязан вручную проектировать гейты или заполнять процессные документы: Hermes должен подготовить черновик и вынести на human gate только требующие решения вопросы.

`proved` — самостоятельный вывод Hermes из полного актуального evidence после обязательных product gates, proof-record и fingerprint checkpoint; отдельный human acceptance для него не требуется. `accepted` — отдельный финальный статус человека или заранее утверждённого правила.

Подробное распределение полномочий является каноническим в `process/autonomy-policy.md`.

В шаблоне нет продуктового кода, конкретных гейтов, product-specific fixtures, исторических статусов или внешних зависимостей. При этом process-only fixture `process/fixtures/provenance-drift/` присутствует для проверки provenance drift; она не является product evidence и не запускает продуктовый код.

## Быстрый порядок настройки

1. Прочитать `AGENTS.md`.
2. Заполнить `product-memory/intent.md`.
3. Определить outcomes и обязательные quality gates.
4. Зафиксировать autonomy policy и human gates.
5. Создать первые evidence scopes и канонические runners.
6. Выполнить ручной шаг доверия и проверить runtime skill resolution в Hermes.

## Подключение проектных навыков в Hermes Desktop

После установки в корне проекта выполни:

```text
cd <project-root>
hermes skills trust
```

Установщик не выполняет эту команду: она изменяет доверенное runtime-состояние Hermes. Затем полностью перезапусти Hermes Desktop, открой эту папку как Hermes Desktop Project и создай новую сессию.

Проверь через runtime загрузку всех шести навыков:

- `understand-state`;
- `choose-next-action`;
- `change-product`;
- `prove-result`;
- `challenge-result`;
- `control-pilot`.

Различай три состояния: файл `SKILL.md` присутствует; навык показан как `local/enabled`; навык фактически загружается по имени в runtime текущей сессии. `hermes skills list` недостаточен, если загрузка по имени завершается `Skill not found`. При относительном `TERMINAL_CWD=./workspace` и неудачной загрузке это известный случай несовместимости Hermes Desktop v0.3, а не подтверждение подключения; само относительное значение не доказывает причину сбоя.
