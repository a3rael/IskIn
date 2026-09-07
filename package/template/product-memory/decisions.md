# Решения

<!-- Добавляй сюда только решения человека или заранее утверждённого правила, меняющие intent, status, scope, action, policy или exception. -->

<!-- Для каждого решения укажи вопрос, варианты, принятое решение, основание, последствия и ссылку на затронутый outcome. -->

<!-- Durable approval event создаётся отдельным append-only JSON-файлом product-memory/approval-events/<event_id>.json только после фактического показа пакета и в следующем человеческом ходе. В этом файле оставь human-readable ссылки approval_event_id, approval_event_path, package_id и checkpoint_sha. Отдельный ответ на discovery-вопрос, generic «продолжай» или разрешение технического действия approval не создают. После точного stage event и этой записи запускается --action approval_checkpoint; это технический commit без нового human gate. -->
