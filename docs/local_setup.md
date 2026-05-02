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

### Cross-channel input

Шаги можно вводить параллельно через CLI (`+N`), web-форму или `POST /api/steps`. Все три источника пишут в `steps_log` лист в Sheets. При следующем старте CLI или F5 на dashboard'е — `apply_steps_log_max_merge()` (задача 4.15) подтянет максимум за сегодня. То есть:

1. CLI стартанул в 10:00 с `today=872` (из game_state snapshot).
2. Через web в 10:30 ввёл `1500` — записалось в steps_log, в памяти uvicorn state.steps.today = 1500.
3. CLI exit + restart в 11:00 → `init_game_state()` загрузит game_state (872) + max-merge из steps_log (1500) → `today=1500`.

Тот же сценарий для F5 в браузере — `try_reload_state()` тоже применяет max-merge.

CLI и web — **отдельные процессы**, у каждого свой `game.state`. В MVP запускаем **что-то одно за раз**: иначе при `s` (сохранение) последний из них перезапишет данные в Sheets.

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
