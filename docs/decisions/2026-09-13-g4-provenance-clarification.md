# Фактологическое уточнение: G4 provenance gap

**Дата уточнения:** 2026-09-13
**Тип:** добавочное уточнение исторической записи
**Исторический запуск:** `g4-read-002`
**Экспериментальный проект:** `/Users/rukavisnikovila/workspace/projects/iskin-v0.4-full-cycle-6`

## Что подтверждено

Исторический запуск `g4-read-002` завершился со статусом `pass`. Его отчёт зафиксировал read-only чтение двух объектов из настроенного списка Reminders; мутация и вызов Telegram API не выполнялись.

В manifest этого запуска для `bot/reminders.py` записан SHA-256:

```text
896c260b5a0a6e7c475d2cc1672a4ef354963020c27c14a68a17735a16282515
```

При документальной read-only проверке 2026-09-13 текущий `/Users/rukavisnikovila/workspace/projects/iskin-v0.4-full-cycle-6/bot/reminders.py` имеет SHA-256:

```text
6a3f5e8f87953000d708268991a6e41d168c06bce1e5b359c268943af8737595
```

## Вывод

Исторический G4 result нельзя считать актуальным для текущего `bot/reminders.py` без нового запуска. Это известный G4 provenance gap: fingerprint входа в manifest не совпадает с fingerprint текущего файла.

Причина gap установлена именно как несовпадение scope/fingerprint. Следующие факты не являются его причиной и должны рассматриваться отдельно:

- redaction: raw JSON и личные поля намеренно не сохранялись;
- отсутствие lifecycle closure: O1 не получил полной durable-записи жизненного цикла, сопоставимой с O3;
- граница сценария: G4 был отдельным read-only probe и не доказывал весь Telegram command surface.

Эта запись дополняет историческую документацию и не переписывает исторический report, manifest, proof-record или принятое human decision.

## Источники

- `evidence/runs/g4-read-002/manifest.json` — исторический fingerprint и scope;
- `evidence/runs/g4-read-002/report.md` — исторический `pass` и фактическая граница чтения;
- текущий `bot/reminders.py` в экспериментальном проекте — read-only fingerprint на дату уточнения;
- `docs/releases/v0.4.0-experimental-prerelease.md` — release-level вывод и план.
