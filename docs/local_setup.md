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

- `GET /` — dashboard (статус, активные сессии, инвентарь, экипировка). При заходе/F5 подтягивает свежий state из Sheets.
- `GET /healthz` — `{"status": "ok", "state_loaded": true, "version": "..."}`.
- `GET /status` — HTML-фрагмент того же контента, что dashboard (без `<html>` обёртки). Используется будущими action endpoints / кнопкой Refresh. Авто-полинг отключён в 0.2.0j; цифры обновляются при F5 / submit формы. Таймеры активных сессий идут на JS без серверных запросов.
- `POST /api/steps` (JSON) — ввод шагов через API. Body: `{"steps": int, "ts"?: float, "source"?: str}`. Применяет max-merge: значение должно быть строго больше текущего `state.steps.today`. Возвращает `{ok, applied, steps_today, steps_can_use, logged}` или 422/503 при ошибке.
- `POST /web/steps` (form-data) — то же, но для HTMX-формы на dashboard'е. Возвращает HTML-фрагмент.

**Пример curl для /api/steps:**

```bash
curl -X POST http://127.0.0.1:8008/api/steps \
  -H "Content-Type: application/json" \
  -d '{"steps": 12500}'
```

**Ввод через web-форму:** на dashboard'е кликни на блок `🏃 Steps` — раскроется форма с input. Введи актуальное число шагов с браслета, нажми "Применить".

### Layout dashboard'а (collapsible blocks)

В постоянно видимой Stats-секции — только текущие цифры (Steps + form, Energy, Money, Level + progress). Три блока ниже свернуты по умолчанию — кликни на заголовок чтобы раскрыть:
- **📈 Бонусы** — детализация бонусов Steps (stamina/equipment/daily/level + всего и процент) и Energy, плюс `Total used` за всё время.
- **🧥 Экипировка (N/7)** — заголовок показывает количество надетых из 7 слотов и ненулевые бонусы (стандартный Pico.css collapsible). Внутри — список по слотам.
- **🎒 Инвентарь (N)** — заголовок показывает количество предметов. Внутри — отсортированный список.

После submit формы шагов блоки сбрасываются в свёрнутое состояние (HTMX swap перерисовывает фрагмент).

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

```bash
ssh aleksey@192.168.0.155 "cd ~/2Walks && git pull && .venv/bin/pip install -r requirements.txt && sudo systemctl restart 2walks && sudo systemctl status 2walks"
```

`sudo` попросит пароль один раз. Если в обновлении не было новых зависимостей — `pip install` отрабатывает за секунду (все packages already satisfied). Downtime ~2-3 секунды, для single-user'а невидимо.

### Опциональные алиасы на MacBook'е

Чтобы не печатать длинную команду — добавь в `~/.zshrc`:

```bash
alias 2walks-deploy='ssh aleksey@192.168.0.155 "cd ~/2Walks && git pull && .venv/bin/pip install -r requirements.txt && sudo systemctl restart 2walks && sudo systemctl status 2walks"'
alias 2walks-logs='ssh aleksey@192.168.0.155 "sudo journalctl -u 2walks -n 50 --no-pager"'
alias 2walks-status='ssh aleksey@192.168.0.155 "sudo systemctl status 2walks --no-pager"'
```

После `source ~/.zshrc` доступны: `2walks-deploy` / `2walks-logs` / `2walks-status`.

### Локальный uvicorn vs сервер

Локальный `uvicorn --reload` на MacBook'е остаётся полезным для:

- Разработки новых фич (hot reload на изменение файлов)
- Smoke-теста перед `git push` (увидеть свои изменения вживую до того как они уедут на сервер через `2walks-deploy`)

Для обычной игры — production-сервер. Если запустишь оба одновременно (локальный uvicorn + production), они будут конкурировать за один state в Sheets — STALE prompt'ы будут срабатывать чаще (но защита 4.54 сработает). Лучше выбрать один в каждый момент.

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
