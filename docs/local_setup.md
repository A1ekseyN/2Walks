# Локальный запуск 2Walks

Шпаргалка по запуску игры на ноутбуке (Mac). Все команды выполняются из корня репозитория.

---

## Подготовка окружения (один раз)

```bash
# Активировать виртуальное окружение
source .venv/bin/activate

# Установить зависимости (если ещё не установлены)
pip install -r requirements.txt

# Положить service account для Google Sheets
# credentials/2walks_service_account.json — gitignored, нужно скопировать вручную

# Один раз — миграция листов в Google Sheets (rename Sheet1 → game_state, create steps_log)
python migrate_sheets.py
```

После этого `.venv` остаётся активной до закрытия терминала. В новых терминалах — снова `source .venv/bin/activate`.

---

## CLI (основной интерфейс)

```bash
python game.py
```

Команды в главном меню (русская раскладка автоматически мапится на латиницу):

| Ввод | Действие |
|---|---|
| `1`–`8` | Перейти в локацию (Home / Gym / Shop / Work / Adventure / Garage / Auto-dialer / Bank) |
| `+` | Ручной ввод количества шагов |
| `+1234` | Inline-ввод шагов (без подменю) |
| `i` | Инвентарь |
| `e` | Экипировка |
| `c` | Характеристики |
| `u` | Распределение очков навыков (после level up) |
| `s` | Сохранить (CSV + JSON + Sheets + steps_log) |
| `l` | Загрузить из Google Sheets |
| `q` | Сохранить и выйти |
| `Ctrl+C` / `Ctrl+D` | Выход **без сохранения** |

---

## Web интерфейс (read-only dashboard)

### Запуск только на ноутбуке (только `localhost`)

```bash
uvicorn web.main:app --reload
```

Открыть в браузере на самом ноутбуке: <http://127.0.0.1:8008/>.

### Запуск с доступом с телефона (домашняя Wi-Fi)

```bash
uvicorn web.main:app --reload --host 0.0.0.0 --port 8008
```

`--host 0.0.0.0` означает "слушать все сетевые интерфейсы", включая Wi-Fi.

**Узнать локальный IP ноутбука:**

```bash
ipconfig getifaddr en0
```

Например, выведет `192.168.0.201`. Это IP ноутбука в твоей домашней сети.

**Открыть с iPhone** (тот же Wi-Fi, что у ноутбука):

```
http://192.168.0.201:8008
```

> ⚠️ macOS firewall может попросить разрешить Python принимать входящие соединения — нажми **Allow**.

> ⚠️ В таком виде сервер открыт для всех устройств в Wi-Fi сети **без авторизации**. ОК для домашней сети, **не ОК** для публичной (кафе, аэропорт). Auth — задача 4.55.

### Endpoints

**GET (read-only):**
- `GET /` — dashboard (статус, активные сессии, инвентарь, экипировка). При заходе/F5 подтягивает свежий state из Sheets.
- `GET /healthz` — `{"status": "ok", "state_loaded": true, "version": "..."}`.
- `GET /status` — HTML-фрагмент того же контента, что dashboard (без `<html>` обёртки). Используется HTMX swap при mutation. Авто-полинг отключён в 0.2.0j; цифры обновляются при F5 / submit формы. Таймеры активных сессий идут на JS без серверных запросов.

**POST mutations** — каждое действие имеет **пару endpoint'ов**: `/web/*` (Form-data, возвращает HTML-фрагмент для HTMX swap) и `/api/*` (JSON через Pydantic, возвращает `{ok, ...}` или `{ok: false, error}` со статусами 422 / 409 / 503):

| Endpoint | Body | Назначение |
|---|---|---|
| `POST /api/steps` / `POST /web/steps` | `{steps: int}` | Ввод шагов (max-merge, > текущего today). |
| `POST /api/work/start` / `POST /web/work/start` | `{work_type, hours}` | Начать смену (1-8 ч, 4 вакансии). |
| `POST /api/work/add_hours` / `POST /web/work/add_hours` | `{hours}` | Добавить часы к активной смене. |
| `POST /api/gym/start` / `POST /web/gym/start` | `{skill_name}` | Прокачка Gym-навыка. |
| `POST /api/level/allocate` / `POST /web/level/allocate` | `{skill}` | Распределить очко уровня (после level-up). |
| `POST /api/adventure/start` / `POST /web/adventure/start` | `{adv_name}` | Стартовать прогулку (4.48.3, 0.2.4s). Auto-finalize при таймере, drop-banner. |
| `POST /api/inventory/sell` / `POST /web/inventory/sell` | `{index}` | **Продать предмет из инвентаря (4.48.6, 0.2.4u).** Trader skill applied к цене. |
| `POST /api/equipment/wear` / `POST /web/equipment/wear` | `{inventory_index, slot_attr?}` | **Надеть equipment (4.48.6, 0.2.4u).** `slot_attr` обязателен для ring (`finger_01`/`finger_02`), опционален для остальных (auto-pick из item_type). Auto-swap при занятом слоте. |
| `POST /api/equipment/unwear` / `POST /web/equipment/unwear` | `{slot_attr}` | **Снять equipment (4.48.6, 0.2.4u).** 422 если `inventory_full` — сначала продай предмет. |
| `POST /api/loadout/optimize` / `POST /web/loadout/optimize` | `{characteristic}` | **Auto-Optimizer loadout (4.63.3, 0.2.4v).** Web ещё имеет `/web/loadout/preview` для двухэтапного UX (preview → apply). |
| `POST /api/preset/save` / `POST /web/preset/save` | `{name}` | **Save current equipment как preset (4.63.3, 0.2.4v).** |
| `POST /api/preset/load` / `POST /web/preset/load` | `{name}` | **Apply preset (4.63.3, 0.2.4v).** Web ещё имеет `/web/preset/preview_load` для preview. |
| `POST /api/preset/delete` / `POST /web/preset/delete` | `{name}` | **Удалить preset (4.63.3, 0.2.4v).** |
| `POST /api/bank/{deposit,withdraw,take_loan,repay_loan}` / `POST /web/bank/*` | `{amount: int, gt=0}` | **Bank: amount-based операции (4.48.9, 0.2.4w).** Skill-gated (Banking Interest Rate / Loan Capacity). |
| `POST /api/bank/{deposit_all,withdraw_all,repay_all}` / `POST /web/bank/*` | `{}` (без body) | **Bank: «всё»-операции (4.48.9, 0.2.4w).** Перенос всего кошелька / снятие всего депозита / погашение всего долга. |
| `POST /api/drop/sell_existing` / `POST /web/drop/sell_existing` | `{index}` | Pending drop resolve: продать item инвентаря + положить находку. |
| `POST /api/drop/sell_new` / `POST /web/drop/sell_new` | `{}` | Pending drop resolve: продать находку. |
| `POST /web/drop/skip` | `{}` (Form only) | Pending drop resolve: отложить. |

**Concurrent safety (4.54, 0.2.4p):** все mutation endpoint'ы проходят через `_persist_and_handle_stale()` — на STALE отвечают 409 (api) или HTML-фрагмент с auto-reload script (web). См. раздел «Concurrent CLI ↔ web» ниже.

**Пример curl для /api/steps:**

```bash
curl -X POST http://127.0.0.1:8008/api/steps \
  -H "Content-Type: application/json" \
  -d '{"steps": 12500}'
```

**Пример curl для /api/adventure/start:**

```bash
curl -X POST http://127.0.0.1:8008/api/adventure/start \
  -H "Content-Type: application/json" \
  -d '{"adv_name": "walk_easy"}'
```

**Пример curl для /api/equipment/wear (ring → finger_02):**

```bash
curl -X POST http://127.0.0.1:8008/api/equipment/wear \
  -H "Content-Type: application/json" \
  -d '{"inventory_index": 0, "slot_attr": "finger_02"}'
```

**Ввод через web-форму:** на dashboard'е кликни на блок `🏃 Steps` — раскроется форма с input. Введи актуальное число шагов с браслета, нажми "Применить".

### Layout dashboard'а (collapsible blocks)

В постоянно видимой Stats-секции — только текущие цифры (Steps + form, Energy, Money, Level + progress). Под ней — `⏱ Активные сессии` блок (показывается только если что-то активно). Дальше collapsible-блоки действий и просмотра, свёрнутые по умолчанию:

- **🏭 Работа** — стартовать смену (вакансия + часы) или добавить часы к активной (4.48.5).
- **🗺 Приключение** — 7 прогулок с прогрессивной разблокировкой, drop probabilities и стартом (4.48.3, 0.2.4s). Locked прогулки — greyed-out с unlock hint.
- **🏋 Спортзал** — прокачка Gym-навыков (4.48.4).
- **🏦 Банк** — депозиты + кредиты (4.48.9, 0.2.4w). Auto-accrue процентов на каждом render. Summary inline: active deposit/loan суммы или 🔒 при skill=0. Деп+Кред sub-blocks с inline формами; critical ops (take_loan, *_all) с `hx-confirm`. Take_loan confirm включает текущую rate-инфо.
- **📈 Бонусы** — детализация Steps/Energy bonuses + Total used.
- **🧥 Экипировка (N/7)** — список по слотам + ненулевые бонусы в summary. На каждом занятом слоте — кнопка «🗑 Снять» (disabled с tooltip если `inventory_full`, чтобы предмет не потерялся). 4.48.6 (0.2.4u).
- **🎯 Loadout** — Auto-Optimizer (выбор одной из 4 characteristics → Preview banner с diff и bonus before/after → Apply/Cancel) + Presets management (save current / preview load / load / delete). Двухэтапный preview-flow с защитой от stale state. 4.63.3 (0.2.4v) — закрывает зонтичную 4.63.
- **🎒 Инвентарь (N/cap)** — отсортированный список предметов. **Sort dropdown** сверху (По типу / По grade / По цене / По бонусу) — server-side reorder через `<select onchange>`. На каждой строке — кнопка «💰 Продать (price$)» (с trader skill applied). Для equipment items дополнительно «🧥 Надеть» (auto-pick slot) или 2 кнопки «На палец 1» / «На палец 2» для ring (явный выбор). Auto-swap при занятом слоте — `hx-confirm` показывает что заменит. 4.48.6 (0.2.4u).

При active `pending_drop` (рюкзак полон в момент дропа) — баннер сверху с 3 опциями resolve (4.50.2). После авто-финализации приключения с дропом — «🎁 Находка» banner (4.48.3) переживает F5, исчезает после любого mutation.

После submit формы блоки сбрасываются в свёрнутое состояние (HTMX swap перерисовывает фрагмент).

### Cross-channel input

Шаги можно вводить параллельно через CLI (`+N`), web-форму или `POST /api/steps`. Все три источника пишут в `steps_log` лист в Sheets. При следующем старте CLI или F5 на dashboard'е — `apply_steps_log_max_merge()` (задача 4.15) подтянет максимум за сегодня. То есть:

1. CLI стартанул в 10:00 с `today=872` (из game_state snapshot).
2. Через web в 10:30 ввёл `1500` — записалось в steps_log, в памяти uvicorn state.steps.today = 1500.
3. CLI exit + restart в 11:00 → `init_game_state()` загрузит game_state (872) + max-merge из steps_log (1500) → `today=1500`.

Тот же сценарий для F5 в браузере — `try_reload_state()` тоже применяет max-merge.

CLI и web — **отдельные процессы**, у каждого свой `game.state`. С версии 0.2.4p (задача 4.54) одновременная работа защищена через optimistic concurrency — см. раздел ниже.

---

## Production: web 24/7 на Ubuntu-сервере

С 18.05.2026 (задача 4.48.0.1) web развёрнут на домашнем Ubuntu-сервере и работает 24/7 через systemd. Локальный `uvicorn --reload` на MacBook'е больше не нужен для обычной игры — открываешь URL с iPhone / MacBook / любого устройства в той же Wi-Fi сети.

### URL для доступа

- По IP: <http://192.168.0.155:8008/>
- По mDNS hostname: <http://aleksey-H61M-DS2H.local:8008/> (резолвится автоматически на macOS / iOS через Bonjour, удобный fallback если IP сменится)

Bookmark оба URL'а в Safari на iPhone + браузере MacBook'а.

### Управление сервисом (на сервере через SSH)

```bash
ssh aleksey@192.168.0.155

# Статус.
sudo systemctl status 2walks

# Логи реал-тайм (Ctrl+C для выхода).
sudo journalctl -u 2walks -f

# Последние 50 строк логов.
sudo journalctl -u 2walks -n 50 --no-pager

# Restart (например, после правки конфига или ручного git pull).
sudo systemctl restart 2walks

# Stop / start (если нужно временно освободить порт для тестов).
sudo systemctl stop 2walks
sudo systemctl start 2walks
```

### Workflow обновлений (с MacBook'а в одну команду)

Из корня проекта — обёртка в `Makefile`:

```bash
make deploy                                      # git pull + pip install + restart + is-active
make deploy HOST=aleksey@aleksey-H61M-DS2H.local # через mDNS, если IP недоступен
make status                                      # systemctl status юнита
make logs                                        # journalctl -n 50 (FOLLOW=-f для live-хвоста)
```

`make deploy` разворачивается в ту же ssh-команду (флаг `-t` обязателен — выделяет TTY, иначе `sudo` не сможет запросить пароль: «a terminal is required»):

```bash
ssh -t aleksey@192.168.0.155 "cd ~/2Walks && git pull && .venv/bin/pip install -r requirements.txt && sudo systemctl restart 2walks && systemctl is-active 2walks"
```

`sudo` попросит пароль один раз. Если в обновлении не было новых зависимостей — `pip install` отрабатывает за секунду (все packages already satisfied). Downtime ~2-3 секунды, для single-user'а невидимо.

### Опциональные алиасы на MacBook'е

Чтобы не печатать длинную команду — добавь в `~/.zshrc`:

```bash
alias 2walks-deploy='ssh -t aleksey@192.168.0.155 "cd ~/2Walks && git pull && .venv/bin/pip install -r requirements.txt && sudo systemctl restart 2walks && sudo systemctl status 2walks"'
alias 2walks-logs='ssh aleksey@192.168.0.155 "sudo journalctl -u 2walks -n 50 --no-pager"'
alias 2walks-status='ssh aleksey@192.168.0.155 "sudo systemctl status 2walks --no-pager"'
```

После `source ~/.zshrc` доступны: `2walks-deploy` / `2walks-logs` / `2walks-status`.

### Локальный uvicorn vs сервер

Локальный `uvicorn --reload` на MacBook'е остаётся полезным для:

- Разработки новых фич (hot reload на изменение файлов)
- Smoke-теста перед `git push` (увидеть свои изменения вживую до того как они уедут на сервер через `2walks-deploy`)

Для обычной игры — production-сервер. Если запустишь оба одновременно (локальный uvicorn + production), они будут конкурировать за один state в Sheets — STALE prompt'ы будут срабатывать чаще (но защита 4.54 сработает). Лучше выбрать один в каждый момент.

### Smoke-тестирование без загрязнения прода — `DRY_RUN` (4.54.0.3)

⚠️ **Никогда не дёргай live mutation-endpoint'ы (`POST /api/work/start`, `/api/steps`, …) против боевого state без `DRY_RUN`** — они пишут в реальные Sheets (`steps_log` / `game_state`) под твоим user_id, и наутро max-merge подтянет мусор (реальный инцидент 03.05.2026). То же касается ручных `python -c` смоков, мутирующих `game.state`.

**Решение — флаг `DRY_RUN`** (env-переменная, читается в `settings.dry_run`): все записи (Sheets `game_state` / `steps_log` / `history` + локальные `state.json` / `history.jsonl`) становятся **no-op**, а чтение работает как обычно → смокаешь поверх RAM-копии реального state, прод не трогается. На старте печатается `⚠️ DRY_RUN: запись отключена …`.

```bash
# Web-смок в песочнице
DRY_RUN=1 uvicorn web.main:app --reload --port 8008
# → дёргай любые endpoint'ы: ответы честные, в Sheets/state.json НИЧЕГО не пишется

# Ручной python-смок в песочнице
DRY_RUN=1 python -c "import characteristics; characteristics.init_game_state(); ..."
```

NB: `DRY_RUN` отключает и реальный Sheets round-trip — для проверки самой персистентности (что save_safe корректно ловит STALE и т.п.) используются unit-тесты с mock'ом gspread (`tests/test_sheets_repo.py`), а изолированный реальный Sheet (отдельный spreadsheet) — отложенный вариант B до появления CI.

### CLI ↔ production-web concurrency

Тот же дизайн что и для локального case (см. раздел «Concurrent CLI ↔ web — sync через optimistic timestamp» ниже). Сервер записывает `last_modified` в Sheets при mutation; CLI на MacBook'е на следующем `s` получает STALE-prompt с diff'ом если сервер успел сохранить позже. Reload (`r`) → re-init из Sheets → синхронизация.

### Если что-то сломалось

| Симптом | Куда смотреть |
|---|---|
| URL не открывается с MacBook/iPhone | `ssh aleksey@192.168.0.155 "sudo systemctl status 2walks"` — Active: failed? Лог `journalctl -u 2walks -n 50` покажет причину |
| Web показывает «Cloud sync failed» | Sheets temporarily unavailable. Через минуту обычно восстанавливается. Проверь интернет на сервере: `ssh ... "curl -I https://google.com"` |
| systemd сервис в `failed` | `journalctl -u 2walks -n 50 --no-pager` → чаще всего: credentials изменились / Sheets API revoked / диск переполнен. Fix → `sudo systemctl restart 2walks` |
| После `git pull` web не подхватил изменения | Забыли `sudo systemctl restart 2walks`. uvicorn запущен БЕЗ `--reload` (намеренно, для стабильности production) |
| Сервер перезагрузился — web недоступен | systemd unit `enabled` → auto-start должен сработать. Если нет: `ssh ... "sudo systemctl start 2walks"`. Сверить enable: `sudo systemctl is-enabled 2walks` → ожидаем `enabled` |

---

## Concurrent CLI ↔ web — sync через optimistic timestamp

С 0.2.4p (задача 4.54) можно безопасно держать оба процесса запущенными одновременно. Раньше последний `s` в CLI мог затереть прогресс web'а (или наоборот) — теперь каждый save проверяет «не обновил ли кто-то Sheets с момента моего load'а» и при конфликте даёт игроку выбрать что делать.

### Как это работает

1. `state.last_modified: float` — каждый save в Sheets ставит свежий `time.time()` в специальную ячейку `game_state` листа.
2. На load (`init_game_state` в CLI, `try_reload_state` в web) делается `take_snapshot()` — deep-copy текущего state'а в RAM-only поле `state.last_loaded_snapshot`.
3. На save помимо записи `GameStateRepo.save_safe()` сначала зовёт `load_meta()` — лёгкий запрос только `last_modified` ячейки. Если в Sheets значение newer чем `state.last_modified` (другой процесс успел записать первым) → возвращается `"STALE"` без записи.

### Что увидишь при STALE

**В CLI** (после `s` / `q`):
```
============================================================
⚠️  STALE — состояние на Sheets изменилось извне (web сервер / другой CLI).
============================================================
  💰 Wallet: 1,133.20 → 1,733.20 (+600.00, зарплата от смены)
  🏋 Energy_Optimization_Gym: 3 → 4
============================================================

[r] Reload — потерять свои несохранённые изменения, подтянуть свежее
[f] Force  — перезаписать сервер (потеряешь изменения выше)
[c] Cancel — продолжить без save, prompt появится снова
>>> 
```

- **`r` Reload** — перезагружает state из Sheets через `init_game_state()`. Свои несохранённые изменения теряются. Безопасный default.
- **`f` Force** — требует второго подтверждения (`yes`). Перезаписывает Sheets своими данными — изменения с сервера выше исчезнут. Используй когда уверен что серверная версия неправильная.
- **`c` Cancel** — продолжить без save, prompt всплывёт снова при следующем save attempt. Полезно если хочешь сначала посмотреть что в CLI и подумать.

**В web** (после любой формы — Steps / Work / Gym / Drop):
- Появится красный баннер «⚠️ Состояние обновлено извне: 💰 +600 / 🏭 смена окончена. Перезагружаю...»
- Через 2 сек страница автоматически перезагружается (full reload).
- Никаких выборов в web нет — только auto-reload (легко нажать «Force» случайно). Если нужен Force — переключись на CLI.

### Логирование

Каждый STALE-event пишется в `history.jsonl`:
```json
{"type": "sync_conflict", "source": "cli", "diff": "💰 +600 / 🏋 +1 skill", "choice": "reload"}
```

Если STALE'ы случаются часто — это сигнал что workflow требует адаптации (например, держишь обе вкладки слишком активно). Посмотри `grep '"sync_conflict"' history.jsonl | wc -l` за день.

### Когда STALE НЕ срабатывает

- **Steps_log writes** (`+N` в CLI / `POST /api/steps` / web-форма) не bumpят `last_modified` — это append-only лог, max-merge на load сам разрешает конфликты.
- **Один процесс на одну Sheets** — если CLI и web на разных машинах с разными credentials, защита работает (та же Sheets API).
- **Multi-tab в одном браузере** — общий uvicorn process, общий state в RAM, конфликта нет.

### Почему по-прежнему не игнорировать F5

Финализаторы web (закрытие смены / повышение скилла / day rollover) мутируют state и зовут save. Если CLI открыт с устаревшим snapshot'ом — на первом же `s` получит STALE. Это не баг, а правильное поведение, но F5 в web после CLI-save (или Reload в CLI после активной web-сессии) экономит один цикл «STALE → Reload → редо».

---

## Тесты

```bash
.venv/bin/pytest tests/
```

Все тесты не зависят от Google Sheets — `import characteristics` ничего не качает (после задачи 1.2). Тестовый прогон ~1 секунда.

---

## Утилиты

```bash
# Показать текущее содержимое game_state листа из Sheets (debug)
python google_sheets_db.py

# Monte-Carlo симуляция drop-механики (10k × 6 сложностей)
python drop_test_montecarlo.py

# Миграция Google Sheets — idempotent, безопасно запускать повторно
python migrate_sheets.py
```

---

## Проблемы и решения

**`zsh: command not found: uvicorn`** — venv не активирована. Либо:
```bash
source .venv/bin/activate
uvicorn web.main:app --reload
```

либо вызывать напрямую:
```bash
.venv/bin/uvicorn web.main:app --reload
```

**Не открывается с iPhone** — проверь:
1. iPhone в той же Wi-Fi сети, что ноутбук.
2. uvicorn запущен с `--host 0.0.0.0`.
3. macOS firewall разрешил Python (System Settings → Network → Firewall → Allow incoming connections for Python).
4. URL в браузере iPhone — `http://<IP_ноутбука>:8008`, не `https://`.

**Отвалилась `game.state`** — после `init_game_state()` падает с ошибкой Sheets — проверь что `credentials/2walks_service_account.json` на месте. Без него фолбэк на CSV (`characteristic.csv`) — игра запустится, но без облака.
