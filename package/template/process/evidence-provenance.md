# Provenance доказательств

## Назначение

Provenance связывает доказательство с конкретными версиями входов, командой, окружением и артефактами. Это процедурный и проверяемый контракт; один текстовый статус не считается техническим enforcement.

## Run-scoped артефакты

Каждый канонический запуск получает новый каталог:

```text
<evidence-root>/runs/<run-id>/
├── manifest.json
├── report.md
└── proof-record.json
```

Исторические каталоги не перезаписываются. Повторное использование `run_id` или существующего файла — ошибка.

## Manifest до запуска

До продуктового действия создаётся immutable `manifest.json` со следующими полями:

```text
schema_version
run_id
outcome
created_at_utc
canonical_command
repository_runner
runner_sha256
environment
scopes:
  <gate-id>:
    inputs: [{path, sha256}]
```

Scope перечисляется отдельно для каждого гейта. Нельзя заменять его неопределённой фразой «все влияющие файлы».

## Report и proof-record

После запуска создаются новые versioned `report.md` и `proof-record.json`. Они должны содержать один и тот же `run_id`. Proof-record связывает manifest и report их SHA-256, gate results, overall result и durable artifacts.

Report после создания не изменяется. Исправление выполняется новым run с новым `run_id`.

## Fingerprint checkpoints

Checkpoint обязателен:

1. перед переводом outcome в `proved`;
2. перед началом следующего независимого outcome;
3. перед изменением файла в scope уже доказанного результата.

Checkpoint сравнивает текущие SHA-256 со scope из manifest. При mismatch:

- сохраняется историческое доказательство;
- создаётся `invalidation_event` с expected и observed fingerprint;
- outcome возвращается в `evidence-pending` или `blocked`;
- следующий независимый outcome не начинается при открытом обязательном product gap;
- новый proof выполняется новым run.

## Human intervention

Решение человека, меняющее status, scope, действие, правило или исключение, записывается как structured `intervention_event` с actor, временем, причиной, target, предыдущим и новым состоянием, consequence и ссылкой на решение.
