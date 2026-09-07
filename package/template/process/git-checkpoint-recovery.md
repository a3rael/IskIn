# Git checkpoint и recovery

Этот документ — единственная каноническая точка шаблона для durable checkpoint и восстановления между сессиями. Он дополняет `process/operating-model.md`, `process/autonomy-policy.md`, `process/action-selection.md` и `process/evidence-provenance.md`; остальные документы не дублируют его полный контракт.

## Recovery preflight

Новая сессия сначала запускает глобальный `iskin-control-pilot`, который вызывает `iskin-understand-state`. Transcript Hermes — только вспомогательный источник. Сессия читает Git branch, `HEAD`, status и diff, затем `product-memory/`, evidence, `telemetry/`, process policy и фактическую версию/revision skill bundle.

Она восстанавливает active outcome, lifecycle, последний завершённый шаг, evidence, authority boundaries и next action. Каждый факт помечается как подтверждённый или требующий проверки.

Recovery отдельно проверяет approval state по существующим durable-источникам:

- полный approval package: отсутствует | неполный | подготовлен | утверждён;
- отдельный прямой вопрос с обеими частями: присутствует | отсутствует;
- durable approval event: присутствует | отсутствует | противоречив;
- `implementation_authorized`: `true` | не подтверждён.

Approval нельзя выводить из transcript, заполненного intent, outcome status, выбранного варианта или существующего diff. Должны быть проверены `package_ref`, фактически заданный `question`, фактический `human_response`, `actor` и `implementation_authorized: true` в записи `product-memory/decisions.md`.

## Pre-approval checkpoint

Registry `product-memory/approval-packages.md` указывает на отдельный канонический файл `product-memory/approval-packages/<package_id>.md`. Каждый package-файл имеет уникальный `package_id`, полный набор обязательных разделов и `package_paths`. Пакет должен существовать в durable state, а не только в transcript или dirty tree.

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

Для проверки drift recovery получает `package_paths` из revision checkpoint и проверяет, что содержимое каждого package_path байтово совпадает с checkpoint. После изменения любого package_path прежний approval недействителен. Требуются новый package ID, новый checkpoint и новый human approval; история не переписывается.

## Clean tree

При clean tree `HEAD` — last stable checkpoint. Из проектных источников должны восстанавливаться active outcome, lifecycle, актуальное evidence и next action. Актуальное evidence не повторяется без evidence-significant причины.

## Dirty tree

При dirty tree предполагается возможное прерывание (interruption) между checkpoint. Изменения сохраняются. Сначала определяется их фактическое состояние, выполняются read-back и проверка возможных side effects. Сессия различает завершённые и незавершённые действия и продолжает работу, перепроверяет её или эскалирует вопрос на основании фактов и полномочий.

Слепые reset, delete, stage и commit запрещены. Нельзя автоматически откатывать или удалять незавершённые изменения.

Если dirty tree содержит продуктовые изменения без подтверждённого approval event, recovery классифицирует состояние как `process-blocked`. Hermes не продолжает реализацию, не создаёт product proof или checkpoint-коммит и не удаляет, не откатывает и не stage-ит изменения. Он сохраняет наблюдаемые факты и эскалирует границу полномочий человеку.

## Checkpoint commit

Hermes может создать локальный checkpoint commit только после одного цельного verified transition, если:

- применимые обязательные проверки прошли;
- product memory, lifecycle, evidence и telemetry согласованы;
- записанные данные перечитаны;
- staged scope точен и не содержит посторонних пользовательских изменений;
- `git diff --cached --check` проходит;
- результат внешнего действия не остаётся неизвестным.

Commit фиксирует согласованные product files, outcome/lifecycle, evidence/provenance, telemetry, next action и authority boundaries. Количество коммитов не является метрикой успеха. Remote, push, tag, merge и publication требуют отдельного human decision.

## Skill bundle compatibility

Фактический skill bundle revision фиксируется в evidence или telemetry. Textual skill change alone не invalidates evidence. Incompatible изменение обязательного process, state или provenance contract требует остановки или явной миграции.

Automatic update global skills во время цикла не выполняется. Версия skills не заменяет проверку применимости, evidence scope или process contract.

## Граница шаблона

Шаблон предполагает заранее доступный global runtime bundle `iskin-*`; project-local skills отсутствуют намеренно. Если global skills недоступны или структура ИскИн не подтверждена, сессия сообщает конкретный blocker и не изменяет продукт.
