# Approval package records

<!-- Каждый полный пакет хранится отдельным файлом product-memory/approval-packages/<package_id>.md. -->
<!-- Один файл пакета фиксируется pre-approval checkpoint и после checkpoint не редактируется. -->
<!-- Этот README задаёт схему package-файла; фактические записи не создаются в исходном template. -->
<!-- Структура package-файла: -->
<!-- - package_id: AP-<UTC timestamp>-<slug> -->
<!-- - package_status: prepared -->
<!-- - package_paths: -->
<!--   - product-memory/approval-packages/<package_id>.md -->
<!--   - product-memory/intent.md -->
<!--   - product-memory/outcomes.md -->
<!--   - product-memory/uncertainties.md -->
<!-- - checkpoint_sha: не записывать в этот пакет; SHA появляется только в последующем approval event. -->
<!-- ### intent и ценность -->
<!-- ### граница MVP: входит / не входит -->
<!-- ### outcomes и наблюдаемое поведение -->
<!-- ### обязательные gates и evidence -->
<!-- ### существенные uncertainties, риски, зависимости и ограничения -->
<!-- Не включай в package_paths продуктовый код, product evidence, proof-record или evidence/runs. -->
