# Контур provenance доказательств v0.3

## Назначение и границы

Process Stabilization v0.3 — отдельное процессное изменение после ретроспективы v0.2. Оно привязывает продуктовое доказательство к конкретным версиям входных файлов и отчёта, не меняя продуктовую цель, критерии G1—G5, Swift-код или порядок продуктовых outcomes.

Этот документ задаёт процедурный контракт. Его соблюдение подтверждается manifest, proof-record, fingerprint-проверками и записями telemetry; один текстовый статус не считается техническим enforcement.

Исторические артефакты v0.2 не переписываются. Новый запуск получает отдельный `run_id` и собственный каталог:

```text
testbeds/budget-ios/evidence/runs/<run_id>/manifest.json
testbeds/budget-ios/evidence/runs/<run_id>/report.md
testbeds/budget-ios/evidence/runs/<run_id>/proof-record.json
```

`testbeds/budget-ios/evidence/p0-02-automatic.md` остаётся историческим артефактом и не является путём вывода для будущего runner.

## Состояние заморозки

После человеческого согласования v0.3 freeze counter сбрасывается в `0/3`. Три последовательных существенных цикла после этого согласования проходят по этому контракту без изменения правил. Процессное изменение, статические проверки и process-only drift-фикстура не являются существенным продуктовым циклом и не увеличивают счётчик.

Любое исключение из контракта регистрируется как structured `intervention_event` и не скрывается в свободном тексте.

## 1. Предстартовый gate-specific manifest

До канонического запуска агент обязан:

1. выбрать один outcome и перечислить применимые продуктовые гейты;
2. определить точный scope каждого гейта;
3. получить SHA-256 каждого входного файла, включая repository runner;
4. записать команду, runner, environment и уникальный `run_id`;
5. создать новый manifest до вызова команды запуска.

Минимальные поля manifest:

```text
schema_version: 1
run_id: уникальная строка одного запуска
outcome: P0-02
created_at_utc: время создания
canonical_command: сохранённая команда
repository_runner: путь runner
runner_sha256: SHA-256 runner
environment: версии инструментов и идентификатор target
scopes:
  G1: список {path, sha256}
  G3: список {path, sha256}
```

Manifest immutable: после создания его нельзя редактировать или перезаписывать. Если каталог или manifest для `run_id` уже существует, запуск останавливается до продуктового действия; выбирается новый `run_id`. Запись выполняется только в новый путь, предпочтительно через временный файл в том же каталоге и атомарное перемещение.

### Точный scope P0-02

Scope перечисляется отдельно по gate и не заменяется фразой «все влияющие файлы».

| Gate | Входы manifest | Граница |
|---|---|---|
| G1 | `testbeds/budget-ios/run-p0-02-verification.sh`; `testbeds/budget-ios/BudgetApp.xcodeproj/project.pbxproj`; `testbeds/budget-ios/BudgetAppApp.swift`; `testbeds/budget-ios/ContentView.swift`; `testbeds/budget-ios/BudgetOperation.swift` | Сборка, установка и запуск приложения через Xcode. `BudgetCoreChecks.swift` сюда не входит: он не компилируется в Xcode-target приложения. |
| G3 | `testbeds/budget-ios/run-p0-02-verification.sh`; `testbeds/budget-ios/BudgetCoreChecks.swift`; `testbeds/budget-ios/BudgetOperation.swift`; `testbeds/budget-ios/ContentView.swift` | Автоматическая проверка истории, границ периода и изменения состава результата. Xcode project и стартовый файл приложения сюда не добавляются как входы G3. |

Если один файл входит в несколько gate scopes, он хэшируется в каждом scope отдельно. Это не отменяет gate-specific границы.

## 2. Версионная пара report и proof-record

После выполнения команда создаёт только новые файлы в каталоге своего `run_id`:

- `report.md` с `report_version: 1`, фактическими G1/G3 statuses, expected/observed, environment и ссылками на артефакты;
- `proof-record.json` с `proof_record_version: 1`, ссылкой на manifest, SHA-256 manifest и отчёта, фактическим результатом, gate statuses и ссылками на durable artifacts.

Proof-record не создаётся до завершения report. После записи report его SHA-256 фиксируется в proof-record; report после этого не изменяется. Дубликат любого целевого пути — ошибка, а не разрешение на перезапись.

`run_id` обязан присутствовать в manifest, report и proof-record и совпадать во всех трёх файлах. Для одного run нельзя создавать второй report поверх первого; исправление выполняется новым run с новым `run_id`, а предыдущая запись сохраняется.

Временные логи могут оставаться в системном временном каталоге и не считаются durable evidence. В proof-record явно указывается, какие артефакты долговечны, а какие являются временными.

## 3. Обязательные fingerprint checkpoints

Не пересчитывать scope перед каждой телеметрийной записью. Fingerprint checkpoint обязателен только:

1. непосредственно перед переводом outcome в `proved`;
2. перед началом следующего независимого outcome;
3. перед изменением любого файла, входящего в scope уже доказанного результата.

Checkpoint сравнивает текущие SHA-256 всех файлов соответствующего gate scope с manifest, на котором основано доказательство. Совпадение необходимо для продолжения действия. Отсутствующий, добавленный, изменённый или удалённый файл считается drift.

Если drift обнаружен:

- создаётся отдельное `invalidation_event` с `event_id`, `run_id`, `outcome`, gate, изменённым path, ожидаемым и фактическим SHA-256, временем и выбранным действием;
- исторический proof сохраняется как доказательство прежней версии;
- текущий outcome переводится из `proved` в `evidence-pending` (либо в `blocked`, если обязательную проверку невозможно выполнить);
- следующий независимый outcome не начинается, пока открыт обязательный product evidence gap, если только human override не оформлен отдельным intervention event;
- новый proof требует нового canonical run и нового `run_id`.

До изменения scope-файла доказанного результата сначала выполняется checkpoint и регистрируется решение о последствиях. Молчаливое редактирование запрещено.

## 4. Structured intervention event

Каждое человеческое решение, меняющее статус, scope, выбранное действие, правило или исключение, записывается как отдельное событие. Минимальная форма:

```text
intervention_event:
  event_id: INT-уникальный-идентификатор
  actor: human
  occurred_at: ISO-8601
  reason: evidence | status | blocker | tooling | scope | override
  target: outcome, gate, file или process rule
  decision: принятое решение
  previous_state: состояние до решения
  new_state: состояние после решения
  consequence: влияние на доказательство, freeze counter и следующий шаг
  approval_reference: product-memory/decisions.md#...
```

Обычный выбор агентом следующего действия не является intervention. Если человек только согласовал v0.3, это одно process-level событие; оно не создаёт product evidence и не увеличивает freeze counter.

## 5. Freeze и критерии успеха v0.3

До начала каждого из трёх существенных циклов записываются: manifest preflight, выбранное действие, применимые gate scopes, expected evidence и текущий counter. После цикла control-pilot проверяет report/proof-record, fingerprint и отсутствие перезаписи.

v0.3 считается стабильной после `3/3`, если одновременно:

- каждый canonical proof имеет gate-specific manifest с SHA-256 и уникальным `run_id`;
- report и proof-record образуют версионную пару и не перезаписывают историю;
- все три checkpoint применялись там, где они требовались;
- каждый drift дал durable invalidation event и корректную статусную коррекцию;
- intervention events позволяют посчитать и объяснить все человеческие изменения процесса;
- обязательные product evidence gaps не обходились молча и P0-03 не стартовал вне правила блокировки;
- process validity и product validity остаются раздельными.

До `3/3` v0.3 считается наблюдаемым процессным экспериментом, а не доказанной стабильностью.
