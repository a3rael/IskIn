# Quality gates и каноническое evidence

## Общий контракт

Каждый outcome должен иметь описание наблюдаемого поведения и применимых гейтов. Для каждого гейта фиксируются:

```text
gate_id:
criterion:
check:
applicable_fixture:
canonical_command:
repository_runner:
durable_artifact_or_link:
expected:
observed:
environment:
run_status: pass | fail | partial | not-run | blocked
```

Продукт сам определяет конкретные `gate_id`, criteria, fixtures и scopes. Шаблон не задаёт доменные гейты.

## Канонический запуск

Каноническим считается только запуск, для которого одновременно существуют:

- команда;
- способ выполнить её из репозитория;
- gate-specific evidence scope;
- долговечный артефакт или стабильная ссылка;
- фактические expected/observed и run status.

Временный вывод, одноразовый скрипт или mock-проверка без durable evidence классифицируются как `ad-hoc` и не переводят outcome в `proved`.

## Acceptance boundary

`proved` допускается как самостоятельный вывод Hermes только после прохождения всех заранее утверждённых обязательных product gates, создания канонического evidence и proof-record и успешного обязательного fingerprint checkpoint, подтвердившего актуальность scope. Этот вывод не требует отдельного human acceptance.

`accepted` выставляется человеком или по заранее утверждённому правилу; Hermes не выставляет этот статус без такого разрешения. При неполном, неактуальном или противоречивом evidence outcome остаётся `evidence-pending`, `reopened` или `blocked` по фактическому состоянию.

Отсутствие runtime-доступа к проектному навыку фиксируется как process state. Оно не заменяет продуктовый gate и не отменяет product proof, если проверка была выполнена другим воспроизводимым способом.

## Challenge

Challenge подключается по риску, слабому покрытию, конфликту evidence, регрессии или высокой цене ошибки. Он работает на чтение и возвращает контрпример, evidence gap или границы проверки. Мнение без воспроизводимого результата не меняет статус outcome.
