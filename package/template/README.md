# Шаблон ИскИн v0.3

Шаблон устанавливает универсальный процесс agent-native PDLC и интеграцию с Hermes Agent и Hermes Desktop Project.

После установки Hermes предлагает и оформляет черновики `intent`, `outcomes`, `uncertainties`, quality gates, evidence scopes и product-specific runners. Владелец проекта подтверждает их значимые части и добавляет фактические evidence и telemetry.

Человек утверждает продуктовую цель, критерии результата, значимые продуктовые решения, изменения process policy и финальный acceptance. Пользователь не обязан вручную проектировать гейты или заполнять процессные документы: Hermes должен подготовить черновик и вынести на human gate только требующие решения вопросы.

Подробное распределение полномочий является каноническим в `process/autonomy-policy.md`.

В шаблоне нет продуктового кода, конкретных гейтов, fixtures, исторических статусов или внешних зависимостей.

## Быстрый порядок настройки

1. Прочитать `AGENTS.md`.
2. Заполнить `product-memory/intent.md`.
3. Определить outcomes и обязательные quality gates.
4. Зафиксировать autonomy policy и human gates.
5. Создать первые evidence scopes и канонические runners.
6. Проверить доверие и runtime skill resolution в Hermes.
