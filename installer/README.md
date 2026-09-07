# Установщик

Канонический standalone-исходник установщика ИскИн v0.3 находится в `installer/install-iskin.py`. Контракт находится в `docs/installation/README.md` и решении `docs/decisions/2026-09-02-v0.3-safe-installation.md`.

Установщик реализует проверяемое локальное размещение официального пакета: новая или пустая папка либо папка только с `.git` → полная проверка версии, SHA-256 и структуры → staging → перенос без перезаписи → metadata → read-back отчёт.

Он не создаёт commit, remote или push, не устанавливает зависимости, не меняет глобальные настройки, не обновляет и не удаляет pre-existing содержимое. При ошибке он пытается удалить только созданные им пути; неполный rollback явно отражается в результате вместе с оставшимися путями.

## Read-only прототип

`verify_release.py` проверяет release локально и не имеет аргумента целевого проекта. `install-iskin.py` использует ту же каноническую реализацию проверки и добавляет локальную установку. Архив не распаковывается напрямую: содержимое ZIP читается через стандартную библиотеку Python и сначала попадает в безопасный staging.

Интерфейс:

```text
python3 installer/verify_release.py \\
  --archive /path/to/iskin-v0.3.0.zip \\
  --release-version 0.3.0 \\
  --expected-sha256 <64 hex characters> \\
  [--report /path/to/report.json]
```

`install-iskin.py` и `SHA256SUMS` должны находиться рядом с архивом. При наличии `--report` JSON-отчёт записывается только в явно указанный путь; родительский каталог должен существовать.

## Интерфейс установщика

```text
python3 install-iskin.py \\
  --archive /path/to/iskin-v0.3.0.zip \\
  --release-version 0.3.0 \\
  --expected-sha256 <64 lowercase hex characters> \\
  --target-path /path/to/project \\
  [--init-git]
```

`--init-git` по умолчанию выключен. При его явном указании установщик может выполнить `git init`, но не создаёт commit, remote, branch ref, tag и не выполняет push. Target должен быть новой, пустой или `.git`-only папкой; сам target и `.git` не могут быть симлинками.

После успешной установки package с project-local skills установщик печатает точную ручную последовательность:

```text
cd <project-root>
hermes skills trust
```

Установщик не запускает `hermes skills trust` сам. Эта команда изменяет доверенное runtime-состояние Hermes; после неё требуется полный перезапуск Hermes Desktop и новая сессия. Наличие файла навыка или успешный `hermes skills list` не заменяют runtime-проверку загрузки по имени. Полный сценарий находится в `docs/integration/hermes-desktop.md`. Для package без project-local skills действует отдельный global-runtime режим ниже.

## Режимы package v0.4

Для package без project-local skills v0.4 установщик не печатает `hermes skills trust`. Он сообщает, что проект использует global runtime ИскИн, global bundle должен быть установлен отдельно, а фактическую доступность нужно проверить в новой сессии Hermes. Installer не вызывает Hermes, не меняет profile, configuration, trust или gateway и не устанавливает global skills.

Режим выбирается по точному составу проверенного manifest: наличие файла под `.hermes/skills/` или `.agents/skills/` сохраняет прежний ручной trust handoff. Похожий путь вне этих каталогов режим не включает. Полный decision: `docs/decisions/2026-09-06-v0.4-installer-runtime-mode.md`.

## Локальный generator release-комплекта

Development-only generator находится в `build_release.py` и использует только `package/template/`, canonical `install-iskin.py` и явно переданную версию:

```text
python3 installer/build_release.py \\
  --release-version 0.3.0 \\
  --output-dir /path/to/output
```

Он создаёт ровно `iskin-v0.3.0.zip`, `install-iskin.py` и `SHA256SUMS`. Комплект сначала собирается в sibling staging, проверяется этим же read-only validator-ом и устанавливается только во временный probe-проект. Для ZIP используются `ZIP_STORED`, фиксированный timestamp `1980-01-01 00:00:00`, отсортированные записи без directory entries, пустые extra fields/comment и фиксированные обычные file attributes. После успешного read-back результаты публикуются без перезаписи; при ошибке staging удаляется.

Одинаковые исходники и версия дают одинаковые байты всех трёх файлов. Generator не создаёт постоянные release-файлы в репозитории, не означает стабильный release и не выполняет tag, push или GitHub Release автоматически.

## Schema `package-manifest.json` v1

Manifest имеет ровно следующие поля верхнего уровня:

```text
schema_version
release_version
root
template_root
files
```

`schema_version` равен целому числу `1`. `release_version` совпадает с аргументом валидатора, именем архива, `VERSION` и версией в `root`; `root` имеет вид `iskin-v<release_version>`, а `template_root` для v0.3 равен `template`.

`files` — отсортированный лексикографически полный allowlist обычных файлов шаблона. Пути относительны `template_root` и используют только безопасную `/`-форму. Каждая запись содержит ровно `path` и строчный `sha256` длиной 64 знака. `VERSION`, `package-manifest.json`, каталоги и неизвестные поля запрещены. Каноническое human decision: `docs/decisions/2026-09-02-v0.3-package-manifest-v1.md`.

## Installation manifest v1

После успешной установки создаются `.iskin/version` и `.iskin/installation-manifest.json`. Последний имеет ровно такие поля:

```text
schema_version
release_version
archive_sha256
files
```

`schema_version` равен целому числу `1`; `release_version` и `archive_sha256` соответствуют проверенному release. `files` — отсортированный полный список immutable installation core-файлов, кроме самого installation manifest, включая `.iskin/version`; каждая запись содержит только `path` и строчный `sha256`. Устанавливаемые `product-memory/` и `telemetry/` являются mutable project state и намеренно не входят в этот последующий integrity allowlist. Пути относительны target и не содержат опасных компонентов. Дата, абсолютный путь компьютера и другие недетерминированные данные не записываются.

Exit codes:

- `0` — release полностью прошёл проверку;
- `2` — ошибка параметров или формата ожидаемой версии/digest;
- `3` — ошибка release-файлов или SHA-256 архива/установщика;
- `4` — ошибка имени, структуры ZIP, allowlist, опасного пути, симлинка, дубликата или Budget/toolchain-specific пути;
- `5` — ошибка `VERSION`, manifest или SHA-256 файла шаблона;
- `6` — недопустимая целевая папка или target/.git-симлинк;
- `7` — обычная ошибка установки после успешной проверки release.

Read-only режим `verify_release.py` не устанавливает пакет. Канонический `install-iskin.py` устанавливает только в допустимый локальный target, выполняет rollback обычных обнаруженных ошибок и явно сообщает о неполном rollback с оставшимися путями. Внезапное выключение, `SIGKILL` и аварийное завершение ОС во время записи остаются ограничением v0.3.
