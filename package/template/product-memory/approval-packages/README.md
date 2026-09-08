# Approval package records

<!-- Каждый полный пакет хранится отдельным файлом product-memory/approval-packages/<package_id>.md. -->
<!-- Рядом находится <package_id>.json с machine-readable index schema_version: 1. -->
<!-- Оба файла фиксируются одним pre-approval checkpoint и после approval не редактируются. -->
<!-- package_paths approval event содержат только immutable package content и index, не registry и projections. -->
<!-- Index fields: schema_version, package_id, revision, immutable_content[{path, sha256}], outcome_ids, gate_ids, superseded_package. -->
<!-- package-файл содержит intent и ценность, границу MVP, outcomes, обязательные gates/evidence и uncertainties. -->
<!-- package fields: intent и ценность; граница MVP; outcomes и наблюдаемое поведение; обязательные gates и evidence; существенные uncertainties, риски, зависимости и ограничения. -->
<!-- package_paths: immutable_content paths only; checkpoint_sha: не записывать в этот пакет. -->
<!-- checkpoint_sha не записывается в package или index; он появляется только в approval event. -->
<!-- Lifecycle status changes use product-memory/lifecycle-events/<event_id>.json and do not revise this package. -->
