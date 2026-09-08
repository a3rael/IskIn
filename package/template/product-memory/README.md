# Product memory

После создания sandbox эти файлы изначально пусты: заполняй их только фактами конкретного продукта и принятыми решениями.

- `intent.md` — текущая читаемая projection утверждённого intent;
- `outcomes.md` — текущая lifecycle projection и ссылки на гейты;
- `uncertainties.md` — текущие открытые вопросы и риски;
- `approval-packages.md` — registry package ID и package revision;
- `approval-packages/<package_id>.md` — полный immutable human-readable specification;
- `approval-packages/<package_id>.json` — immutable machine index с revision, SHA-256 содержимого, outcome IDs, gate IDs и superseded package;
- `lifecycle-events/<event_id>.json` — append-only machine-readable lifecycle events;
- `evidence.md` — текущая projection доказательств;
- `decisions.md` — human decisions, включая approval и acceptance references;
- `telemetry/run-log.md` — append-only наблюдения циклов.

Approval package содержит только specification: intent и ценность, MVP boundary, outcome definitions, обязательные gates/evidence и uncertainties. `intent.md`, `outcomes.md` и `uncertainties.md` не входят в immutable package paths: их lifecycle metadata может изменяться без новой approval revision. Gate сверяет projections с последним lifecycle event по машинным HTML-комментариям и не пытается семантически парсить Markdown.

Immutable package paths и их hashes не изменяются после approval. Изменение specification требует новой package revision, нового checkpoint и human approval. Lifecycle transition выполняется через `lifecycle_checkpoint`; сам gate остаётся read-only.

Не помещай сюда правила универсального процесса: они находятся в `process/`.
