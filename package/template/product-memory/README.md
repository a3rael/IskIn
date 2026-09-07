# Product memory

После создания sandbox эти файлы изначально пусты: заполняй их только фактами конкретного продукта и принятыми решениями.

- `intent.md` — зачем нужен продуктовый результат;
- `outcomes.md` — lifecycle и ссылки на гейты;
- `uncertainties.md` — открытые вопросы и риски;
- `approval-packages.md` — полные пакеты, их package ID и package paths до human approval;
- `evidence.md` — фактические проверки и артефакты;
- `decisions.md` — human decisions и последствия; approval-записи содержат ссылки на event ID/path, package ID и checkpoint SHA.
- `approval-events/<event_id>.json` — создаваемые в ходе работы append-only machine-readable approval events; каталог отсутствует в исходном template и не является immutable installation core.

Не помещай сюда правила универсального процесса: они находятся в `process/`.

`approval-packages.md` — registry, а `approval-packages/<package_id>.md` — канонический durable state конкретного pre-approval package. Package-файл фиксируется отдельным checkpoint commit до показа человеку; machine-readable checkpoint SHA и approval event записываются только после показа и ответа человека в `approval-events/<event_id>.json`, а human-readable record сохраняется в `decisions.md`. Пакет не содержит продуктовый код или product evidence.
