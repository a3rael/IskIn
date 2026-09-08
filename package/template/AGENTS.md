# ИскИн в установленном проекте

Это короткая точка входа для Hermes Agent и Hermes Desktop Project. Навыки ИскИн v0.4 загружаются из глобального runtime; `runtime/skills/` — их канонический источник, а project-local copies отсутствуют намеренно.

## Вход в проект и новая сессия

1. Начни с глобального `iskin-control-pilot`.
2. Выполни recovery preflight через `iskin-understand-state`.
3. Если `HEAD` отсутствует, ожидай `BOOTSTRAP_REQUIRED`: discovery и approval preparation запрещены. Вызови `python3 .iskin/policy_gate.py --action stage_bootstrap_baseline`, stage-ь только возвращённый exact `allowed_paths` через scoped `git add -- <paths>`, перечитай staged scope и `git diff --cached --check`, затем вызови `--action bootstrap_checkpoint`. Gate сам не staging/commit-ит. Только при exit `0` создай локальный технический initial commit; при запрете верни blocker. После commit повтори gate и только затем переходи к discovery.
4. Каноническое состояние читай из Git, `product-memory/`, evidence и `telemetry/`; transcript Hermes используй только как вспомогательный источник.
5. При отсутствии global skills ИскИн или структуры проекта сообщи конкретный blocker до изменения продукта; вне структуры ИскИн навык неприменим.

## Канонические источники

- Виды состояния и lifecycle: `process/operating-model.md`.
- Полномочия и human gates: `process/autonomy-policy.md`.
- Выбор следующего действия: `process/action-selection.md`.
- Product gates и evidence: `process/quality-gates.md`, `process/evidence-provenance.md`.
- Git checkpoint и recovery: `process/git-checkpoint-recovery.md`.
- Bootstrap baseline: immutable `.iskin/bootstrap-manifest.json` and generated `.iskin/installation-manifest.json`; process fixtures listed by that baseline are not product evidence during the initial commit only.
- Pre-approval package: registry `product-memory/approval-packages.md`, immutable specification `product-memory/approval-packages/<package_id>.md` and companion index `<package_id>.json`; lifecycle events: `product-memory/lifecycle-events/<event_id>.json`; approval event: `product-memory/approval-events/<event_id>.json`; `product-memory/decisions.md` is a human-readable reference.
- Определения telemetry: `telemetry/metrics.md`; фактические циклы: `telemetry/run-log.md`.

## Git и полномочия

Git — обязательная инфраструктура. Локальный checkpoint commit создаётся только после законченного проверенного перехода и согласованного read-back состояния. Remote, push, tag, merge и публикация требуют отдельного human decision. Полный контракт находится в `process/git-checkpoint-recovery.md`.

Не выполняй установку или доверие project-local skills для v0.4: global runtime bundle должен быть установлен заранее. Не изменяй продукт при неподтверждённой применимости, неизвестном external result или несогласованном dirty tree.
