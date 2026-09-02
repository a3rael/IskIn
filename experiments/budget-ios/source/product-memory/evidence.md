# Доказательства

## Цикл 1 — P0-01 — ручное создание операций

**Статус результата:** `proved`.

**Наблюдаемое поведение:** создан локальный iOS-срез с формой ручного создания дохода и расхода, положительной суммой в российских рублях, фиксированной встроенной категорией и датой; операции отображаются в списке.

**Применённые проверки:**

- G2 — автоматическая валидация и создание операции;
- G1 — сборка и запуск в iOS Simulator;
- ручная приёмочная проверка в Simulator — выполнена.

**Фактические результаты:**

- `PASS` — автоматическая G2: создание дохода и расхода;
- `PASS` — автоматическая G2: положительная сумма в рублях;
- `PASS` — автоматическая G2: фиксированная встроенная категория;
- `PASS` — автоматическая G2: дата операции сохраняется;
- `PASS` — `xcodebuild ... build`: `** BUILD SUCCEEDED **`;
- `PASS` — `xcrun simctl install` и `xcrun simctl launch`: процесс `local.agentnative.budgetios` запущен, PID `46393`;
- `PASS` — screenshot устройства показывает экран `Budget MVP` с формой «Новая операция», типами «Доход»/«Расход», полем суммы, категорией, датой и кнопкой «Добавить».
- `PASS` — свежая разовая проверка временным скриптом `hermes-verify-`: автоматическая G2, сборка G1 и запуск в iOS Simulator; скрипт после выполнения удалён. Это ad-hoc verification, не результат полного тестового набора.
- `PASS` — ручная UI-приёмка в iOS Simulator: создан расход `300.00 ₽`, затем доход `1000.00 ₽`; обе операции отображаются в истории, различаются по типу и содержат категорию «Продукты» и дату `30 Aug 2026`.

**Ограничения и пробелы:**

- навык `/prove-result` отсутствует в текущем профиле и локальном репозитории; UI-проверка выполнена эквивалентным доступным read-only сценарием через Simulator;
- изменение, удаление и локальное восстановление данных не входят в этот цикл.

**Артефакт:** `testbeds/budget-ios/evidence/p0-01-launch.png`.

**Итог:** обязательные доказательства P0-01 собраны; результат переведён в `proved`. Статус `accepted` не выставлялся без отдельного человеческого принятия.

## Цикл 2 — P0-02 — история и фильтр по периоду

**Outcome status:** `evidence-pending`.

**Cycle closure:** `process-incomplete`.

**Применимые гейты:** G1, G3.

**Применимый fixture:** G3 — полный набор A, B и C.

**Canonical command:** отсутствует; выполнен только временный ad-hoc-скрипт.

**Repository runner:** отсутствует.

**Durable artifact or link:** отсутствует для автоматического ad-hoc-результата.

**Skill resolution:** `file-only` для проектных навыков; runtime-индексация как `project` не подтверждена.

**Наблюдаемое поведение:** история отображает созданные операции; пользователь выбирает режим «Все» или «Выбранный период» и задаёт даты начала и конца; при выбранном периоде отображаются только операции внутри него.

**Применённые проверки:**

- G3 — автоматическая проверка состава истории и границ периода;
- G1 — сборка, установка и запуск в iOS Simulator;
- ручная приёмочная проверка в Simulator — выполнена.

**Фактические результаты:**

- `PASS` — автоматическая проверка G3: операции на начальной и конечной границе периода включаются;
- `PASS` — автоматическая проверка G3: операция вне периода исключается;
- `PASS` — автоматическая проверка G3: изменение периода меняет состав истории;
- `PASS` — `xcodebuild ... build`: `** BUILD SUCCEEDED **`;
- `PASS` — свежий временный скрипт с префиксом `hermes-verify-` повторно выполнил `BudgetCoreChecks` и `xcodebuild`; завершился `AD_HOC_VERIFICATION_PASS`, после выполнения скрипт удалён. Это разовая проверка, а не полный тестовый набор;
- `PASS` — `xcrun simctl install` и `xcrun simctl launch`: процесс `local.agentnative.budgetios` запущен в iOS Simulator;
- `PASS` — UI без фильтра показал операции `300.00 ₽` от `30 Jul 2026` и `1000.00 ₽` от `30 Aug 2026`;
- `PASS` — UI с периодом `31 Jul 2026`—`30 Aug 2026` показал только `1000.00 ₽` и исключил операцию от 30 июля;
- `PASS` — после изменения начала периода на `30 Jul 2026` UI показал операцию `300.00 ₽` от 30 июля, то есть состав истории изменился.

**Ограничения и пробелы:**

- историческая ручная проверка до цикла 1 покрывала только две операции; полный набор A, B и C закрыт отдельным существенным циклом ниже;
- автоматическая проверка пока ad-hoc и не имеет канонического воспроизводимого запуска в репозитории;
- проектные навыки читаются из файлов, но не индексируются runtime как `project`.

**Итог:** автоматическое доказательство всё ещё не имеет канонического запуска, поэтому P0-02 остаётся `evidence-pending`; ручной gap U-001 закрыт в существенном цикле 1/3 ниже. Статус `accepted` не выставлялся без отдельного человеческого принятия.

## Существенный цикл 1/3 — ручное UI-доказательство U-001 для P0-02

**Время:** 2026-08-30T16:30:52+03:00—2026-08-30T16:48:36+03:00.

**Environment:** macOS; iPhone 17 Pro, iOS 26.5 (23F77); bundle ID `local.agentnative.budgetios`.

**Applicable gate:** G3; G1 использован как среда сборки и запуска.

**Fixture:** A — доход `1000 ₽`, категория «Продукты», `30 Aug 2026`; B — расход `300 ₽`, категория «Продукты», `30 Aug 2026`; C — расход `200 ₽`, категория «Продукты», `30 Jul 2026`.

**Canonical command:** не использовался; для подготовки среды выполнены разовая `xcodebuild`-сборка и `xcrun simctl install/launch`. U-002 остаётся открытым.

**Durable artifacts:** `testbeds/budget-ios/evidence/p0-02-ui-all.png`; `testbeds/budget-ios/evidence/p0-02-ui-selected-period.png`.

**Manual UI read-back:**

- `PASS` — в режиме «Все» после создания fixture UI и accessibility read-back показали ровно три записи: C `Расход / Продукты / 200.00 ₽ / 30 Jul 2026`, B `Расход / Продукты / 300.00 ₽ / 30 Aug 2026`, A `Доход / Продукты / 1000.00 ₽ / 30 Aug 2026`;
- `PASS` — в режиме «Выбранный период» с началом `31 Jul 2026` и концом `30 Aug 2026` UI и accessibility read-back показали ровно B и A; C отсутствует;
- `PASS` — возврат в режим «Все» восстановил в read-back все три записи A, B и C;
- `PASS` — значения суммы, типа, категории и даты для каждой записи совпали с fixture.

**Result:** U-001 закрыт. Продуктовый результат P0-02 остаётся `evidence-pending`, поскольку U-002 — обязательный незакрытый gap. `Cycle closure` остаётся `process-incomplete` из-за U-003 (`file-only`/нестабильная runtime-индексация проектных навыков).

## Существенный цикл 2/3 — попытка канонического автоматического доказательства U-002

**Время:** начало — 2026-08-30T20:39:44+03:00; остановка — 2026-08-30T20:46:11+03:00.

**Outcome status:** `evidence-pending`.

**Cycle closure:** `blocked` — обязательная автоматическая проверка не получила валидного результата.

**Applicable gates:** G1, G3.

**Выбранное действие:** создать минимальный repository runner `testbeds/budget-ios/run-p0-02-verification.sh`, зафиксировать команду `./testbeds/budget-ios/run-p0-02-verification.sh` и сохранять результат в `testbeds/budget-ios/evidence/p0-02-automatic.md`.

**Результат выполнения:** первая версия runner содержала неправильно экранированные обратные кавычки в shell-формировании Markdown-отчёта. Shell интерпретировал их как командную подстановку и рекурсивно запускал runner; это приводило к повторным запускам Simulator. Запуск был прерван до получения результата. Процессы `xcodebuild`, `simctl` и `BudgetCoreChecks` после остановки отсутствуют.

**Проверенные факты:**

- `bash -n testbeds/budget-ios/run-p0-02-verification.sh`: `PASS` после исправления экранирования;
- `git diff --check`: `PASS`;
- исправленный runner не запускался повторно после диагностики;
- `testbeds/budget-ios/evidence/p0-02-automatic.md` содержит честный `not-run`/blocked-диагноз, а не автоматический `PASS`.

**Gate evidence:**

- G1: `not-run` — нет валидного результата сборки, установки и запуска в рамках исправленного runner;
- G3: `not-run` — нет валидного автоматического отчёта полного fixture A/B/C;
- ручное доказательство U-001 из цикла 1/3 сохраняется и этим циклом не отменяется.

**Итог:** U-002 остаётся `open`; P0-02 остаётся `evidence-pending`. Наличие команды, runner и диагностического файла само по себе не закрывает U-002 без успешного фактического запуска.

**Дополнительная ad-hoc verification runner (не canonical product proof):** временный verifier с безопасным именем `hermes-verify-*` скопировал runner в песочницу и подменил `xcodebuild`, `simctl` и `swiftc` заглушками. Проверены возврат `0`, наличие отчёта с G1/G3/overall `PASS`, ровно один вызов `launch` и отсутствие рекурсии; временные файлы удалены. Это подтверждает исправление shell-контроля, но не заменяет реальный запуск, автоматическую проверку продукта или доказательство G1/G3.

## Существенный цикл 3/3 — реальное автоматическое доказательство U-002 для P0-02

**Время:** начало — 2026-08-30T20:57:00+03:00; фактический запуск зафиксирован в отчёте временем `2026-08-30T17:57:43Z`; завершение — 2026-08-30T20:57:51+03:00.

**Outcome status:** `proved`.

**Cycle closure:** `process-incomplete` — U-003 остаётся отдельным tooling-gap; он не блокирует продуктовую доказанность.

**Applicable gates:** G1, G3.

**Canonical command:** `./testbeds/budget-ios/run-p0-02-verification.sh`.

**Repository runner:** `testbeds/budget-ios/run-p0-02-verification.sh`.

**Durable artifact:** `testbeds/budget-ios/evidence/p0-02-automatic.md`.

**Environment:** Xcode 26.6, Apple Swift 6.3.3, iPhone 17 Pro, iOS Simulator UDID `F92F7E07-CBD8-402B-B5D9-B3576B873CAF`, bundle ID `local.agentnative.budgetios`.

**Fixture:** A — доход `1000 ₽` на границе периода; B — расход `300 ₽` на границе периода; C — расход `200 ₽` вне периода.

**Фактические результаты:**

- G1: `PASS` — `xcodebuild` завершился `** BUILD SUCCEEDED **`; установка и запуск завершились с кодом `0`;
- G3: `PASS` — `BudgetCoreChecks.swift` скомпилирован и выполнен с кодом `0`; подтверждены включение обеих границ, исключение C и изменение состава истории;
- отчёт содержит фактический commit `b584134dd91296bdbdd41645b3e333df9460a76b`, реальный Simulator и `## Итог: PASS`;
- после завершения активных `xcodebuild`, `simctl` и `BudgetCoreChecks` нет;
- исходный runner содержит ровно один вызов `simctl launch`; выполнение завершилось без рекурсии.

**Итог prove-result:** U-002 закрыт. Вместе с ручным доказательством U-001 из цикла 1/3 обязательные продуктовые доказательства G1/G3 для P0-02 собраны; P0-02 переведён в `proved`. Человеческое принятие `accepted` не выставлялось.

## Статусная корректировка после read-only-аудита целостности P0-02

Историческая запись выше относится к реальному запуску прежней версии runner. После доказательного запуска были изменены `testbeds/budget-ios/run-p0-02-verification.sh` и `testbeds/budget-ios/evidence/p0-02-automatic.md`, включая изменение формулировки о `TMPDIR`, без новой канонической проверки.

Текущий автоматический `PASS` поэтому не доказывает текущую версию runner. Последующие ad-hoc-проверки со заглушками проверяли только управление runner и не заменяют реальный запуск продукта.

Статусная корректировка: P0-02 — `evidence-pending`; U-002 — `open`. Минимальное действие для закрытия U-002: выполнить реальный канонический запуск текущей версии runner и сформировать новый долговечный отчёт.

Счётчик заморозки остаётся `3/3`. P0-03 не разрешён к запуску.

## Process Stabilization v0.3 — process-only change

**Статус продуктового доказательства:** новых product evidence не создано.

**Человеческое согласование:** зафиксировано в `product-memory/decisions.md`, 2026-08-31. Изменение не меняет продуктовую цель, критерии G1—G5, Swift-код, P0-02 или P0-03.

**Добавленный provenance-контур:** `process/evidence-provenance.md` задаёт pre-run gate-specific manifest с SHA-256, уникальный `run_id`, versioned report/proof-record, запрет перезаписи истории, три fingerprint checkpoints, `invalidation_event` при drift и structured `intervention_event` для человеческих решений.

**Scope P0-02:** G1 — runner, Xcode project и `BudgetAppApp.swift`, `ContentView.swift`, `BudgetOperation.swift`; `BudgetCoreChecks.swift` исключён из G1. G3 — runner, `BudgetCoreChecks.swift`, `BudgetOperation.swift`, `ContentView.swift`.

**Изолированная фикстура:** добавлен только process-only шаблон в `process/fixtures/provenance-drift/`; он не ссылается на продуктовый runner и не выполнялся. Product evidence из фикстуры не создаётся.

**Результат проверки:** изменены только процессные правила, навыки, память и telemetry из согласованного allowlist, runner подготовлен к будущему versioned output, но канонический P0-02 не запускался. Freeze counter v0.3 установлен в `0/3`; это не существенный продуктовый цикл.

## Process Stabilization v0.3 — существенный process-only цикл 1/3: provenance drift

**Время:** начало — `2026-08-31T10:42:07Z`; drift — `2026-08-31T10:43:20Z`; read-back — `2026-08-31T10:47:38Z`.

**Тип записи:** process-only evidence; это не продуктовый результат и не доказательство P0-02.

**Run ID:** `20260831T104207Z-provenance-drift-01`.

**Артефакты фикстуры:**

- `process/fixtures/provenance-drift/runs/20260831T104207Z-provenance-drift-01/manifest.json`;
- `process/fixtures/provenance-drift/runs/20260831T104207Z-provenance-drift-01/proof-record.json`;
- `process/fixtures/provenance-drift/runs/20260831T104207Z-provenance-drift-01/report.md`;
- искусственный scope-файл: `process/fixtures/provenance-drift/runs/20260831T104207Z-provenance-drift-01/scope-input.txt`.

**Проверенная последовательность:**

1. **Scope drift:** scope-файл изменён с версии v1 на синтетическую v2; manifest сохранён без изменений.
2. **Fingerprint mismatch:** ожидаемый SHA-256 `589c429b8ca7ed5f954465c3a44d7d02606e49e65f640dcba49430ba829a82b5` не совпал с observed SHA-256 `d3efeadfe09313d3cc531c3fa5e3415f2f6d9a8e600681092286b7e00f8b1fae`.
3. **Invalidation:** создано событие `INV-PROC-20260831T104320Z`; proof-record связывает его с mismatch и scope-файлом.
4. **Synthetic outcome:** `evidence-pending`; доказательство не продвигается после drift.

**Проверка provenance:** `run_id` совпадает во всех записях; SHA-256 manifest и report совпадают с hash-значениями в proof-record; историческая запись не перезаписывалась; `product_evidence_created: false`.

**Состояние продукта:** P0-02 остаётся `evidence-pending`, U-002 — `open`; продуктовые гейты, цель, Swift-код и P0-03 не изменялись и не запускались.

**Итог process-only цикла:** `Cycle closure: complete`; freeze counter v0.3 изменён с `0/3` на `1/3`. Этот счётчик относится к замороженному процессному эксперименту, а не к продуктовой доказанности.

## Существенный цикл 2/3 v0.3 — каноническое доказательство U-002 для P0-02

**Время:** начало preflight — `2026-08-31T11:18:36Z`; канонический запуск — `2026-08-31T11:19:30Z`; prove/control read-back — `2026-08-31T11:21:53Z`.

**Outcome:** P0-02 — история операций и фильтр по периоду.

**Outcome status:** `proved`.

**Cycle closure:** `process-incomplete` из-за U-003 (`file-only`/нестабильная runtime-индексация проектных навыков); это не блокирует продуктовый `proved`.

**Выбранное действие:** после восстановления состояния выполнить ровно один реальный запуск текущего repository runner для закрытия U-002; mock, заглушки, ad-hoc substitute и временный подменяющий runner не использовались.

**Applicable gates:** G1, G3.

**Canonical command:** `./testbeds/budget-ios/run-p0-02-verification.sh`.

**Repository runner:** `testbeds/budget-ios/run-p0-02-verification.sh`.

**Preflight manifest:** `testbeds/budget-ios/evidence/runs/20260831T111836Z-p0-02-preflight-01/manifest.json`; SHA-256 `c970c585416e333270c74a3940a1ea4324ea4d1f2c2b3fc475271fe9c36d59fc`.

**Canonical run ID:** `20260831T111930Z-96022`.

**Versioned evidence:**

- manifest: `testbeds/budget-ios/evidence/runs/20260831T111930Z-96022/manifest.json`;
- report: `testbeds/budget-ios/evidence/runs/20260831T111930Z-96022/report.md`;
- proof-record: `testbeds/budget-ios/evidence/runs/20260831T111930Z-96022/proof-record.json`.

**Fingerprint checkpoint:** `PASS` перед продвижением в `proved`. Runner SHA-256: `64bb678fb1cb3f39207e09731da02170642167e36db5e0e65acd188cdfe67cec`; все текущие входы G1/G3 совпали с manifest; manifest SHA-256 в proof-record — `aec0e777cacfbf738aedcca41ff7de94cc4e48534e531edcd68fba968d4d44d5`; report SHA-256 — `21d7d583e49757559bc022ab7dfe2a14517a68f144b406b496c78605edd43574`.

**G1:** `PASS` — `xcodebuild` завершился `BUILD SUCCEEDED`; установка и запуск в iPhone 17 Pro Simulator завершились с кодом `0`.

**G3:** `PASS` — `BudgetCoreChecks` скомпилирован и выполнен с кодом `0`; подтверждены включение обеих границ периода, исключение операции C вне периода и изменение состава истории.

**Fixture coverage:** полный автоматический fixture G3 A/B/C.

**Prove-result:** обязательные G1 и G3 имеют воспроизводимое evidence; U-002 закрыт; P0-02 переведён в `proved`; `accepted` не выставлялся без отдельного человеческого принятия.

**Control-pilot:** product reconciliation `pass`; process reconciliation `pass` с классификацией `process-incomplete` из-за U-003; historical `p0-02-automatic.md` не перезаписан; новый report/proof-record создан в отдельном run-каталоге.

**Состояние продукта:** U-003 остаётся `open` как tooling/process gap; он не блокирует `proved`. P0-03 не запускался и не изменялся.

**Freeze counter:** `2/3` для v0.3; предыдущий process-only цикл учитывается как первый существенный цикл заморозки, исторический v0.2 `3/3` не переносится.

## Test Automation Addendum — scope invalidation P0-02 перед реализацией

**Время:** `2026-08-31T18:31:04Z`.

**Причина:** человечески согласованный Test Automation Addendum добавляет XCTest/Swift Testing, XCUITest/XCUIAutomation, изолированное test storage/reset, launch arguments, accessibility identifiers и Xcode result bundle. Это расширяет evidence scope P0-02.

**Pre-change provenance checkpoint:** `PASS` для исторического run `20260831T111930Z-96022`; все текущие G1/G3 fingerprints совпали с прежним manifest; manifest/report/proof hash-связи действительны.

**Scope invalidation event:** `INV-P0-02-UI-AUTO-20260831T183104Z`. Событие означает смену обязательного evidence scope до первого изменения файлов, а не content mismatch текущих файлов.

**Статусная корректировка:** P0-02 `proved` → `evidence-pending`; U-002 `closed` → `open`. Исторический manifest/report/proof-record сохраняется без перезаписи.

**Ограничение:** новый XCTest/XCUITest test target, persistence/test seams и runner ещё не изменялись; новый canonical proof ещё не выполнялся. G1—G5 и продуктовая цель не меняются; U-003 остаётся отдельным process/tooling gap; P0-03 не запускается.

## Test Automation Addendum — canonical XCTest/XCUITest proof

**Время:** `2026-08-31T18:57:29Z`; canonical run `20260831T185729Z-1879`.

**Outcome status:** `proved`.

**Cycle closure:** `process-incomplete` из-за U-003; это отдельный process/tooling gap и не блокирует продуктовую доказанность.

**Applicable gates:** G1, G3. Продуктовые критерии G1—G5 не изменялись.

**Canonical command:** `./testbeds/budget-ios/run-p0-02-verification.sh`.

**Versioned artifacts:**

- `testbeds/budget-ios/evidence/runs/20260831T185729Z-1879/manifest.json`;
- `testbeds/budget-ios/evidence/runs/20260831T185729Z-1879/report.md`;
- `testbeds/budget-ios/evidence/runs/20260831T185729Z-1879/proof-record.json`;
- `testbeds/budget-ios/evidence/runs/20260831T185729Z-1879/BudgetApp-P0-02.xcresult/`;
- `testbeds/budget-ios/evidence/runs/20260831T185729Z-1879/BudgetApp-P0-02.xcresult.files.sha256`.

**Фактические результаты:**

- G1: `PASS` — `xcodebuild test` завершился с кодом `0` и создал result bundle в iPhone 17 Pro iOS Simulator;
- XCTest: `PASS` — 2 unit tests, включая проверку period boundaries и изоляции/reset test store;
- XCUITest: `PASS` — 1 UI test с assertions по полному A/B/C, выбранному периоду и возврату к полному периоду;
- G3: `PASS` — legacy `BudgetCoreChecks.swift` также скомпилирован и выполнен с кодом `0`; файл сохранён;
- screenshot attachments: `PASS` — экспортированы три требуемых состояния: `p0-02-all-operations`, `p0-02-selected-period`, `p0-02-period-changed`;
- Computer Use: `0` запусков; автоматическое UI-доказательство признано полным без Computer Use.

**Provenance:** deterministic digest manifest содержит 54 внутренних файла `.xcresult`; независимый SHA-256 read-back совпал с digest в proof-record. Hash-связи manifest/report/proof-record и единый `run_id` подтверждены. Исторический run `20260831T111930Z-96022` сохранён, failed/superseded attempt `20260831T185618Z-98990` не перезаписан.

**Метрики:** critical UI checks via XCUITest `1/1`; Computer Use `0`; длительность `xcodebuild test` `25 s`; стоимость внешнего платного ресурса `N/A`.

**Итог prove-result:** U-002 закрыт, P0-02 переведён в `proved`; `accepted` не выставлялся без отдельного human acceptance. P0-03 не запускался и не активировался.

## Invalidation event — P0-02 после начала P0-03

**Время:** 2026-08-31, после fingerprint checkpoint исторического run `20260831T185729Z-1879`.

**Причина:** реализация выбранного P0-03 затронула общий P0-02 scope (`ContentView.swift`, `BudgetOperation.swift`, `BudgetAppTests/BudgetOperationTests.swift`, `BudgetAppUITests/BudgetAppUITests.swift`). Pre-change SHA-256 checkpoint был выполнен; после drift исторический proof сохранён, но не распространяется на текущее состояние.

**Последствие:** P0-02 временно reopened в `evidence-pending`; обязательный следующий ход — новый canonical G1/G3 proof текущего worktree. U-003 не выбран: он остаётся неблокирующим process/tooling gap.

## Существенный цикл 1 — P0-03 — статистика за период и по категориям

**Outcome status:** `proved`.

**Cycle closure:** `process-incomplete` — продуктовые gates закрыты; ad-hoc runner verifier был заблокирован terminal approval-механизмом до выполнения, а project-skill resolution остаётся `file-only`. Эти process/tooling observations не подменяются продуктовым gap и не блокируют P0-03.

**Выбранное поведение:** для выбранного периода показываются доходы, расходы, разница и разбивка по встроенным категориям; расчёт выполняется в копейках и форматируется в рублях.

**Каноническое доказательство:** `testbeds/budget-ios/evidence/runs/20260831T195326Z-76199/` — manifest, report, proof-record, `.xcresult` и deterministic `.xcresult` files manifest.

**Результаты:** G1=`PASS`, G4=`PASS`, `xcodebuild_test=0`, длительность 18 s, screenshot attachment `p0-03-selected-period-statistics` — 1, export status 0. Fixture: доход 1000 ₽ / `Продукты`, расход 300 ₽ / `Транспорт`, расход 200 ₽ вне периода. Unit и UI P0-03 checks прошли.

**Проверка provenance:** manifest содержит текущие SHA-256 runner/app/test scopes; proof-record связывает manifest/report и содержит тот же run_id. После запуска evidence-relevant files не менялись.

**Итог:** P0-03 имеет достаточные воспроизводимые evidence для `proved`; `accepted` не выставлялся. Следующий независимый ход — action selection для P0-04.

## Существенный цикл 2 — P0-04 — изменение, удаление и пересчёт итогов

**Outcome status:** `proved`.

**Cycle closure:** `process-incomplete` — продуктовые G1/G4 закрыты; runner был создан через kernel write-path с первым невалидным read-back и затем корректно авторен/проверен, а runtime-разрешение проектных навыков остаётся `file-only`. Эти process/tooling observations не блокируют продуктовый proof.

**Выбранное действие:** продолжить P0-04 после read-back состояния и реализовать минимальный mutation contract: заменить операцию по стабильному `id`, удалить операцию по `id`, пересчитать историю и статистику.

**Рассмотренные действия:** выбрать U-003 — отклонено как неблокирующий tooling gap; перейти к P0-05 — отклонено до закрытия текущего обязательного P0-04; реализовать и доказать P0-04 — выбрано как ближайший утверждённый outcome.

**Реализация:** `BudgetOperationMutator.replace/delete`; SwiftUI-кнопки «Изменить»/«Удалить», сохранение изменений с сохранением исходного `UUID`, обновление store и derived statistics.

**Fixture G4:** доход A `1000 ₽` / `Продукты`; расход B `300 ₽` / `Транспорт`; расход C `200 ₽` вне выбранного периода.

**Автоматические проверки:**

- `PASS` — unit test `testP004ChangingAndDeletingOperationsRecalculatesStatistics`: 1000/300/700 → 1000/400/600 → 0/400/−400; актуальные category breakdown проверены литеральными ожиданиями;
- `PASS` — focused XCUITest `testP004ChangingAndDeletingRecalculatesSelectedPeriodStatistics`: все три состояния, история после изменения и удаления, исчезновение старой суммы и доходной категории;
- `PASS` — полный `xcodebuild ... test`: `EXIT=0`;
- `PASS` — canonical `./testbeds/budget-ios/run-p0-04-verification.sh`: `EXIT=0`, G1=`PASS`, G4=`PASS`, `xcodebuild_test=0`;
- `PASS` — три reviewable screenshot attachments: `p0-04-initial-statistics`, `p0-04-after-change`, `p0-04-after-delete`; export status `0`.

**Canonical provenance:** `testbeds/budget-ios/evidence/runs/20260901T095803Z-34925/` содержит manifest, report, proof-record, `.xcresult` и deterministic `.xcresult.files.sha256`; `run_id` совпадает, manifest/report SHA-256 зафиксированы в proof-record, `.xcresult` digest `3b348621d72eaf5d5c9bb9593bce0f3a7fda33cb7c9a53054f66a9d12f84e3c4`.

**Upstream invalidation/recovery:** P0-04 затронул общий scope P0-02/P0-03, поэтому исторические runs `20260901T095113Z-27573` и `20260901T095257Z-29509` были выполнены до canonical P0-04, прочитаны и подтвердили G1/G3 и G1/G4 PASS; старые runs сохранены, новые каталоги не перезаписывались.

**Process deviations/recovery:** первые четыре focused UI attempts завершались `EXIT=65` до product proof: сначала неверный viewport, затем ненадёжный `TextField.value`/режим ввода; после read-back и исправления bordered hit-target последний focused UI run прошёл. Первый kernel write-path не дал read-back runner; файл был повторно создан через проверенный write path и перечитан. Один canonical вызов получил `EXIT=126` из-за отсутствия executable-бита; после `chmod +x` canonical run прошёл. Эти попытки не считались product evidence.

**Итог:** обязательные воспроизводимые доказательства P0-04 собраны; outcome переведён в `proved`, `accepted` не выставлялся. Следующий независимый outcome — P0-05.

## Существенный цикл 3 — P0-05 — сохранение данных после перезапуска

**Outcome status:** `proved`.

**Cycle closure:** `process-incomplete` — продуктовые G1/G5 закрыты; загруженные project skills доступны только в file-only режиме после compression boundary. Tooling gap не блокирует product proof.

**Выбранное действие:** реализовать и доказать persistence round-trip через новый `BudgetOperationStore` и реальный XCUITest terminate→launch без reset.

**Рассмотренные действия:** выбрать U-003 — отклонено как неблокирующий process/tooling gap; остановить прогон — оснований не было, поскольку обязательный G5 был доступен локально; реализовать и доказать P0-05 — выбрано как последний утверждённый proposed outcome.

**Реализация:** fixture seed выполняется только при пустом store, поэтому второй launch не перезаписывает данные; unit round-trip сохраняет A/B/C и выбранно-периодные totals; UI test после terminate→launch проверяет историю, selected-period totals и category breakdown.

**Автоматические проверки:**

- `PASS` — unit test `testP005OperationsAndStatisticsSurviveApplicationRestart`: новый store instance восстановил 1000/300/200 и статистику выбранного периода 1000/300/700;
- `PASS` — focused XCUITest `testP005OperationsAndStatisticsSurviveApplicationRestart`: terminate→launch без `--ui-test-reset`, все три операции и итоговые показатели восстановлены;
- `PASS` — полный `xcodebuild ... test`: `EXIT=0`;
- `PASS` — canonical `./testbeds/budget-ios/run-p0-05-verification.sh`: `EXIT=0`, G1=`PASS`, G5=`PASS`, `xcodebuild_test=0`;
- `PASS` — screenshot attachment `p0-05-after-restart`; export status `0`.

**Canonical provenance:** `testbeds/budget-ios/evidence/runs/20260901T100916Z-49036/` содержит manifest, report, proof-record, `.xcresult` и deterministic `.xcresult.files.sha256`; `run_id` совпадает, manifest/report SHA-256 зафиксированы в proof-record, `.xcresult` digest `fe04edfa2e58fe92c4c2e5689ae487f6920f7e2a194c15560e52a632cf9e73d7`.

**Process deviations/recovery:** первый focused UI run завершился `EXIT=65`, но read-back simulator sandbox подтвердил сохранённый JSON; причина была в отсутствии scroll после второго launch, исправлен только test navigation, повторный focused run и canonical run прошли. Первый P0-05 runner был механически сгенерирован с остаточными P0-04 test/gate labels; read-back выявил drift, runner исправлен до запуска canonical proof. Неуспешные попытки не считались product evidence.

**Human intervention:** новых человеческих изменений outcome, scope, rule или exception не было; `accepted` не выставлялся.

**Итог:** обязательные воспроизводимые доказательства последнего P0-05 собраны; outcome переведён в `proved`. Все утверждённые P0 имеют product evidence, U-003 остаётся отдельным process/tooling gap.

## Существенный цикл 4 — восстановление canonical provenance после UI-test drift

**Outcome status:** P0-02=`proved`; P0-03=`proved`; P0-04=`proved`; P0-05=`proved`.

**Cycle closure:** `process-incomplete` — текущие product proofs PASS; две предыдущие остановки autonomous run произошли по лимиту tool-вызовов, а runtime project skills остаются `file-only`. Ни один из этих process/tooling фактов не является обязательным product evidence gap.

**Причина восстановления:** после proof `20260901T100916Z-49036` был изменён общий `BudgetAppUITests.swift` для стабилизации P0-04 вводом через triple-tap. Это invalidated ровно четыре текущих canonical proof records: P0-02 `20260901T102301Z-65131`, P0-03 `20260901T102442Z-66878`, P0-04 `20260901T102516Z-67785`, P0-05 `20260901T102600Z-68980`.

**Lifecycle control:** перед повторными запусками P0-02—P0-05 были открыты в `evidence-pending`; intent, G1—G5 и evidence scopes не менялись. После успешного read-back статусы восстановлены в `proved`.

**Повторные canonical runs:**

- P0-02: `20260901T102301Z-65131`, G1/G3=`PASS`, `xcodebuild_test=0`, 8 attachments;
- P0-03: `20260901T102442Z-66878`, G1/G4=`PASS`, `xcodebuild_test=0`, 1 attachment;
- P0-04: `20260901T102516Z-67785`, G1/G4=`PASS`, `xcodebuild_test=0`, 3 attachments;
- P0-05: `20260901T102600Z-68980`, G1/G5=`PASS`, `xcodebuild_test=0`, 1 attachment.

Каждый новый каталог содержит manifest, report, proof-record, `.xcresult` и deterministic digest manifest; run IDs, manifest/report SHA-256 и gate-specific current fingerprints перечитаны. Исторические proofs не перезаписывались.

**Additional regression check:** свежий полный suite после triple-tap stabilization — `EXIT=0`; он использован только как regression check и не заменял canonical provenance.

**Итог:** четыре invalidated proofs восстановлены четырьмя новыми canonical runs; все утверждённые P0 имеют текущие воспроизводимые product evidence. `accepted` для P0-02—P0-05 не выставлялся; P0-01 остаётся ранее принятым человеком.
