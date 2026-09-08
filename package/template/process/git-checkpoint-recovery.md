# Git checkpoint и recovery

Этот документ — единственная каноническая точка шаблона для durable checkpoint и восстановления между сессиями. Он дополняет `process/operating-model.md`, `process/autonomy-policy.md`, `process/action-selection.md` и `process/evidence-provenance.md`; остальные документы не дублируют его полный контракт.

## Recovery preflight

Новая сессия сначала запускает глобальный `iskin-control-pilot`, который вызывает `iskin-understand-state`. Transcript Hermes — только вспомогательный источник. Сессия читает Git branch, `HEAD`, status и diff, затем `product-memory/`, evidence, `telemetry/`, process policy и фактическую версию/revision skill bundle.

До интерпретации этих источников запускается read-only gate из `.iskin/policy_gate.py`:

```text
python3 .iskin/policy_gate.py --action read_only_recovery
```

JSON gate является детерминированным prerequisite. Non-zero exit или `PROCESS_BLOCKED` останавливает orchestration: не вызываются `change-product` и `prove-result`, не запускаются продуктовые проверки, не записывается telemetry и не создаётся retroactive package/checkpoint. Gate ничего не изменяет; он не доказывает факт показа пакета человеку.

## Bootstrap checkpoint до первого commit

После установки с `--init-git` repository имеет Git metadata, но `HEAD` ещё отсутствует. В этом состоянии gate возвращает `BOOTSTRAP_REQUIRED` с reason `INITIAL_BASELINE_UNCOMMITTED`: discovery и подготовка approval запрещены. Gate проверяет immutable `.iskin/bootstrap-manifest.json`, generated `.iskin/installation-manifest.json`, происхождение и SHA-256 каждого baseline-файла, exact inventory, пустые product memory/telemetry и отсутствие approval packages/events/product code/evidence. Read-only action `stage_bootstrap_baseline` при пустом index возвращает точный `allowed_paths`; gate не выполняет `git add`.

Process fixtures считаются baseline только потому, что их путь и содержимое перечислены в проверенном bootstrap manifest. Отдельное исключение по имени `proof-record.json` запрещено. Изменённый или отсутствующий baseline, дополнительный файл или изменённая installation metadata дают fail-closed результат и не разрешают commit.

Orchestrator сначала запускает `--action stage_bootstrap_baseline`, выполняет только scoped `git add -- <allowed_paths>`, перечитывает JSON, staged scope, остаток и `git diff --cached --check`, затем запускает `--action bootstrap_checkpoint`. Этот action разрешён только при exact staged scope и отсутствии остатка; он возвращает `BOOTSTRAP_REQUIRED` и не staging-ит/не commit-ит. При любом расхождении commit не создаётся. После успешного technical initial commit gate запускается повторно: lifecycle переходит в discovery, а product actions, обычный checkpoint и approval checkpoint остаются запрещены до обычного approval flow.

Bootstrap commit является проверенной нижней временной границей product lifecycle. Gate принимает только единственный root commit с exact subject `chore: bootstrap iskin project baseline`, exact scope всех путей bootstrap manifest и совпадающими baseline hashes. Для проверки product code/evidence до pre-approval checkpoint анализируются только commits после этого verified bootstrap commit и до checkpoint; история до bootstrap не классифицируется как product activity. Отсутствующий, неоднозначный, не-root, изменённый по scope/hash или произвольно выбранный bootstrap commit даёт fail-closed результат. Immutable baseline drift после bootstrap запрещён даже если файл позднее восстановлен.

Она восстанавливает active outcome, lifecycle, последний завершённый шаг, evidence, authority boundaries и next action. Каждый факт помечается как подтверждённый или требующий проверки.

Recovery отдельно проверяет approval state по существующим durable-источникам:

- полный approval package: отсутствует | неполный | подготовлен | утверждён;
- отдельный прямой вопрос с обеими частями: присутствует | отсутствует;
- durable approval event: присутствует | отсутствует | противоречив;
- `implementation_authorized`: `true` | не подтверждён.

Approval нельзя выводить из transcript, заполненного intent, outcome status, выбранного варианта или существующего diff. Машинная проверка выполняется по append-only `product-memory/approval-events/<event_id>.json`; human-readable запись в `product-memory/decisions.md` остаётся согласованным журналом ссылок. Должны быть проверены `package_id`, `checkpoint_sha`, event ID/path, фактически заданные `approval_question` и `human_response`, `actor` и `implementation_authorized: true`. Orphaned event, запись без event или несовпадение ID/SHA блокируют процесс.

## Pre-approval checkpoint

Registry `product-memory/approval-packages.md` указывает на отдельный канонический файл `product-memory/approval-packages/<package_id>.md` и его machine-readable companion `<package_id>.json`. Индекс содержит schema version, revision, immutable content paths с SHA-256, outcome IDs, gate IDs и superseded package. Каждый package-файл имеет уникальный `package_id` и полный набор обязательных разделов; mutable projections не входят в `package_paths`. Пакет должен существовать в durable state, а не только в transcript или dirty tree.

Pre-approval checkpoint — отдельный локальный commit между подготовкой пакета и его показом человеку. До показа человеку он фиксирует immutable revision пакета. `checkpoint_sha` не записывается в этот пакет и не может быть известен внутри создаваемого commit; SHA появляется только в последующем approval event.

Допустимый pre-approval checkpoint содержит только process/product description и durable discovery state: approval package и перечисленные в нём описательные `product-memory/` файлы, без реализации. Он не содержит продуктового кода. Он не содержит product evidence, proof-record или `evidence/runs/`. Этот checkpoint с продуктовым кодом непригоден для approval.

Если пакет существует только в dirty tree, implementation blocked. Если до попытки pre-approval checkpoint уже обнаружены product code, product evidence или иное последствие реализации, checkpoint задним числом не создаётся: recovery возвращает `process-blocked`, сохраняет состояние и не легитимизирует уже сделанные изменения.

После успешного commit Hermes показывает человеку весь пакет, package ID и checkpoint SHA в одном сообщении. Только затем задаётся прямой вопрос, а ответ принимается в следующем человеческом ходе. Approval event обязан содержать:

```text
package_displayed_in_previous_agent_turn: true
package_id: <package ID>
checkpoint_sha: <40-hex checkpoint SHA>
approval_question: <фактически заданный вопрос>
human_response: <фактический ответ человека>
actor: <actor>
implementation_authorized: true
```

Фраза «авторизую полный пакет» без подтверждённого показа не является approval. Generic «продолжай» и разрешение отдельного технического действия не являются lifecycle approval.

Для проверки immutable drift recovery получает package paths из machine event и companion index и проверяет, что содержимое каждого package_path (immutable package path) байтово совпадает с checkpoint. Projections (`intent.md`, `outcomes.md`, `uncertainties.md`, `evidence.md`, telemetry) не являются package paths: их обычное lifecycle-обновление не требует новой approval revision. После изменения любого immutable package path прежний approval недействителен. Требуются новый package ID/revision, новый checkpoint и новый human approval; история event-файлов не переписывается.

Lifecycle state хранится append-only событиями `product-memory/lifecycle-events/<event_id>.json`. Для каждого события проверяются schema version, package checkpoint, outcome membership, `from_status`/`to_status`, Git parent, projection markers и evidence/proof references. Обычный переход выполняется через `--action lifecycle_checkpoint`; старые events не редактируются и не удаляются. `proved` требует актуального canonical evidence/provenance, `accepted` — отдельной human decision reference.

## Clean tree

При clean tree `HEAD` — last stable checkpoint. Из проектных источников должны восстанавливаться active outcome, lifecycle, актуальное evidence и next action. Актуальное evidence не повторяется без evidence-significant причины.

## Dirty tree

При dirty tree предполагается возможное прерывание (interruption) между checkpoint. Изменения сохраняются. Сначала определяется их фактическое состояние, выполняются read-back и проверка возможных side effects. Сессия различает завершённые и незавершённые действия и продолжает работу, перепроверяет её или эскалирует вопрос на основании фактов и полномочий.

Слепые reset, delete, stage и commit запрещены. Нельзя автоматически откатывать или удалять незавершённые изменения.

Если dirty tree содержит продуктовые изменения без подтверждённого approval event, recovery классифицирует состояние как `process-blocked`. Hermes не продолжает реализацию, не создаёт product proof или checkpoint-коммит и не удаляет, не откатывает и не stage-ит изменения. Он сохраняет наблюдаемые факты и эскалирует границу полномочий человеку.

После ответа человека event и ссылки в `decisions.md` точно stage-ятся, затем вызывается `python3 .iskin/policy_gate.py --action approval_checkpoint`. Gate разрешает этот технический commit только при exact staged scope, отсутствии staged/unstaged посторонних изменений, package drift и product code/evidence; перед commit проходит `git diff --cached --check`. После approval checkpoint повторный `--action change_product` разрешает implementation без нового human gate. Обычное изменение lifecycle status выполняется новым event через `--action lifecycle_checkpoint`; этот scope может содержать только event, projections, telemetry и относящиеся evidence/proof paths. Перед product checkpoint вызывается `--action checkpoint`, перед canonical proof — `--action prove_result`. Exit `0` означает разрешение только запрошенного действия. Любой другой exit означает запрет.

Если `.iskin/policy_gate.py` отсутствует или project использует неподдерживаемую schema, состояние классифицируется как `PROCESS_BLOCKED` с reason `UNSUPPORTED_PROJECT_STATE`. Это только read-only диагностика: без миграции, product checks, telemetry writes, retroactive package/checkpoint, implementation, proof или commit.

## Checkpoint commit

Hermes может создать локальный checkpoint commit только после одного цельного verified transition, если:

- применимые обязательные проверки прошли;
- product memory, lifecycle, evidence и telemetry согласованы;
- записанные данные перечитаны;
- staged scope точен и не содержит посторонних пользовательских изменений;
- `git diff --cached --check` проходит;
- результат внешнего действия не остаётся неизвестным.

Локальный checkpoint commit фиксирует согласованный verified transition. Для lifecycle-only transition сначала создаётся новый append-only event, обновляются projections и выполняется `--action lifecycle_checkpoint`; immutable package не меняется. Product code допускается только отдельным product checkpoint после действующего approval и не может быть скрыт внутри lifecycle-only scope. Количество коммитов не является метрикой успеха. Remote, push, tag, merge и publication требуют отдельного human decision.

## Skill bundle compatibility

Фактический skill bundle revision фиксируется в evidence или telemetry. Textual skill change alone не invalidates evidence. Incompatible изменение обязательного process, state или provenance contract требует остановки или явной миграции.

Automatic update global skills во время цикла не выполняется. Версия skills не заменяет проверку применимости, evidence scope или process contract.

## Граница шаблона

Шаблон предполагает заранее доступный global runtime bundle `iskin-*`; project-local skills отсутствуют намеренно. Если global skills недоступны или структура ИскИн не подтверждена, сессия сообщает конкретный blocker и не изменяет продукт.
