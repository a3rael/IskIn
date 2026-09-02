# Test Automation Addendum

**Статус:** согласовано человеком 2026-08-31; реализация выполняется отдельным change-scope.

## 1. Границы решения

- Продуктовые критерии G1—G5 не изменяются.
- P0-02 после фактического изменения evidence scope возвращается в `evidence-pending` до нового канонического запуска.
- Историческое доказательство P0-02 сохраняется и не перезаписывается.
- `BudgetCoreChecks.swift` сохраняется до успешного переоформления P0-02 новым XCTest/XCUITest-контуром. Его отдельный вывод из употребления возможен только отдельным согласованным изменением.

## 2. Слои автоматизации

- XCTest или Swift Testing — основной слой проверки доменной логики и граничных случаев.
- XCUITest/XCUIAutomation в iOS Simulator — основной слой критических UI-сценариев, включая сценарий P0-02.
- Computer Use не является основным регулярным regression-слоем.

## 3. Изоляция данных UI-тестов

Каждый XCUITest запускается с test launch arguments:

- `--ui-test-mode` — выбрать тестовое локальное хранилище;
- `--ui-test-reset` — удалить тестовое хранилище перед запуском;
- `--ui-test-fixture-p0-02` — загрузить детерминированный fixture для сценария P0-02.

`BudgetAppApp` создаёт `BudgetOperationStore` и выполняет reset до создания `ContentView`. Тестовое хранилище использует отдельный файл `ui-test-operations.json`; обычное пользовательское хранилище `operations.json` не читается и не изменяется. Тест не зависит от операций, оставшихся от предыдущего запуска.

## 4. Accessibility identifiers

Hermes самостоятельно выбирает и документирует конкретные identifiers. Обязательное правило именования:

```text
budget.<screen>.<control>
```

Текущий набор включает identifiers для типа, суммы, категории, даты и кнопки добавления операции, а также фильтра и границ периода истории. Изменение identifier считается изменением UI-test scope и требует нового proof.

## 5. Reviewable UI evidence

Ручная приёмка G1/G3 по умолчанию опирается на reviewable-артефакты автоматического XCUITest:

- фактический результат теста;
- выполненные assertions;
- screenshot attachments критических состояний;
- Xcode result bundle `.xcresult` либо versioned summary с доступными ссылками и выдержками.

XCUITest обязан создавать screenshot attachments как минимум для следующих критических состояний P0-02:

1. история с полным набором операций A/B/C;
2. история после выбора периода, включающего A/B и исключающего C;
3. история после изменения фильтра/периода.

Каждый attachment должен быть связан с соответствующим тестовым шагом или assertion и сохраняться в `.xcresult` либо отражаться в versioned summary. Отсутствие обязательного attachment — evidence gap; успешное завершение теста само по себе его не компенсирует.

Computer Use запускается только как исключение, если автоматических reviewable-артефактов недостаточно для конкретного визуального, исследовательского или диагностического вопроса. Отсутствие Computer Use само по себе не делает автоматическое UI-доказательство неполным.

## 6. Каноническое доказательство и provenance

Канонический запуск выполняется через:

```text
./testbeds/budget-ios/run-p0-02-verification.sh
```

Он обязан включать:

- `xcodebuild test` в iOS Simulator;
- Xcode result bundle `BudgetApp-P0-02.xcresult`;
- versioned `manifest.json`;
- versioned `report.md`/summary;
- versioned `proof-record.json`;
- deterministic digest manifest для внутренних файлов `.xcresult`.

Digest `.xcresult` вычисляется без зависимости от порядка файловой системы: строится отсортированный по относительному пути manifest всех внутренних файлов, для каждого файла вычисляется SHA-256, а digest вычисляется от канонической последовательности `relative_path + SHA-256`. Сам каталог не хэшируется как непрозрачное значение.

`proof-record.json` должен подтверждать результат `xcodebuild test`, assertions и наличие обязательных screenshot attachments либо явно фиксировать недостающий attachment как evidence gap. Временные логи не являются доказательством.

## 7. Метрики

Для каждого канонического запуска фиксируются:

- доля критических UI-проверок через XCUITest;
- число запусков Computer Use и причина каждого исключения;
- длительность `xcodebuild test`, XCTest и XCUITest;
- стоимость проверки, если для запуска используется платный внешний ресурс;
- количество обязательных screenshot attachments и evidence gaps.

Нулевой знаменатель отражается как `N/A`, а не как 100%.

## 8. Allowlist реализации

После согласования допускаются только необходимые изменения:

- `testbeds/budget-ios/BudgetApp.xcodeproj/project.pbxproj` и shared scheme;
- `testbeds/budget-ios/BudgetAppApp.swift`;
- `testbeds/budget-ios/ContentView.swift`;
- новый persistence-файл `BudgetOperationStore.swift`;
- новые XCTest/Swift Testing и XCUITest исходники;
- `testbeds/budget-ios/run-p0-02-verification.sh`;
- versioned process/product evidence и telemetry records.

Не изменяются продуктовые критерии G1—G5, product goal и P0-03. Коммиты и push выполняются только отдельным явным разрешением.
