# TASKS

Живой список задач по проекту 2Walks. Создан на основе аудита кодовой базы.
Приоритеты выставлены по соотношению "эффект / стоимость". Чем выше в блоке — тем раньше стоит браться.

Легенда:
- **Impact**: L (низкий) / M (средний) / H (высокий) — насколько сильно задача улучшит проект
- **Effort**: S (часы) / M (1-2 дня) / L (неделя+) — оценка трудозатрат
- **Status**: `todo` / `in-progress` / `done` / `blocked`

---

## 1. Архитектура и рефакторинг

### 1.1. Обернуть `char_characteristic` в класс `GameState` `[H / L / done (30.04.2026)]`

Корневая архитектурная задача — заменили module-level dict `char_characteristic` на типизированный `GameState` dataclass с nested подклассами. После завершения геймплейные функции принимают `state: GameState` явным параметром, тесты возможны без HTTP-импортов, веб-интерфейс (4.48) разблокирован.

**Зафиксированные технические решения (на которые опирается актуальная архитектура):**
- **dataclass** (stdlib), не Pydantic. Конвертация в Pydantic — отдельной задачей позже для FastAPI.
- **Nested структура** — связанные поля сгруппированы в подклассы: `StepsState`, `CharLevel`, `GymSkills`, `TrainingSession`, `WorkSession`, `AdventureSession`, `Equipment`.
- **Переименование полей** — кривые имена (`lvl_up_skill_stamina`, `working_end`, `adventure_walk_15k_counter`) сделаны осмысленными в коде. На границе load/save — explicit mapping в legacy save format (`from_dict` / `to_dict`).
- **CSV / JSON / Sheets save format не менялся** — `to_dict()` возвращает тот же flat dict с прежними ключами; старые сейвы продолжают работать.
- **Items как dict пока** — задача 1.6 (Items as dataclass) делается отдельно.
- **Helper функции** для не-тривиальных мутаций — в `actions.py` (`try_spend`, `start_work`, `start_training`, `start_adventure`).
- **Имя файла** — `state.py` в корне.
- **Тесты** — pytest, 156 проходящих юнит-тестов покрывают все мигрированные модули + round-trip сейва.

**Реализация по фазам:** 6 фаз, см. changelog `0.2.0..0.2.0b` (29-30.04.2026). Версия игры после Phase 5: `0.2.0b`.

**Разблокировано:** 2.2.3 (синк стампа при тратах), 2.3 (Adventure не видит прокачку — закрыто неявно), 3.1 (pytest setup — закрыто), 3.2.1 (luck как параметр Drop_Item — закрыто неявно), 4.9 (мульти-сейв), 4.33 (Reincarnation), 4.46 (Story Mode), 4.48 (Web Interface — все подзадачи).

---

### 1.2. Убрать побочные эффекты из module-level кода `[H / M / done (01.05.2026)]`

**Сделано:**
- **drop.py:** module-level `luck_chr` (фиксировался при импорте, не учитывал прокачку удачи) → функция `current_luck(state)`, вызываемая в момент дропа. Сделано в Phase 4 commit 4 (1.1).
- **gym.py:** 8 stale module-level f-строк `lvl_up_*` / `description_*` → функции `format_lvl_up_info(state, skill)` и `display_skill_description(skill, state)`, вычисляемые в момент рендера меню. Сделано в Phase 4 commit 3 (1.1).
- **equipment_bonus.py:** module-level `equipment_list` (захватывал ссылки на dict экипировки при импорте) → функция `_equipment_slots(state)`. Сделано в Phase 3 (1.1).
- **skill_bonus.py:** module-level `stamina_skill_bonus = stamina_skill_bonus_def()` (считал бонус один раз при импорте на ещё не прогретом state) → удалён, был мёртвым импортом. Сделано в Phase 3 (1.1).
- **inventory.py:** module-level `Wear_Equipped_Items.equipped_items` (захватывал слоты при импорте) → метод `_slots(state)`, вызываемый при создании экземпляра. Сделано в Phase 4 commit 2 (1.1).
- **characteristics.py:** последний и самый большой источник — `import characteristics` ходил в Google Sheets при загрузке (`load_data_from_google_sheet_or_csv()` на module-level). Закрыто 01.05.2026:
  - Module-level `game_state = ...` заменён на container `game = _GameContainer()` с атрибутом `state: Optional[GameState] = None`.
  - Загрузка вынесена в `init_game_state()` функцию (idempotent), которую CLI вызывает в начале `__main__`. FastAPI (когда появится) — в startup hook.
  - Дубликат date-check (`date_check_steps_today_used()` через save.txt при импорте) удалён — единая точка проверки дня живёт в `functions.save_game_date_last_enter()` на первом тике main loop.
  - Все callers (`game.py`, `level.py:__main__`, `drop_test_montecarlo.py:__main__`, `save_characteristic`) переключены с `from characteristics import game_state` на `from characteristics import game; game.state.<field>`.
  - Полное удаление `save.txt` остаётся в задаче **2.1**.

**Эффект:**
- Импорт `characteristics` больше не делает сетевых вызовов. Тесты теперь стартуют ~1 сек вместо ~5 сек (×5 ускорение).
- FastAPI (4.48) разблокирован: uvicorn `--reload` не перезагружает Sheets каждый раз; startup hook чисто инициализирует state; можно сделать выбор сейва "при логине".
- Архитектурный путь к multi-user (4.53) — расширить container до `game.states[user_id]`.

**Тесты:** `tests/test_characteristics.py` — 7 тестов (контейнер, idempotent init, live reference через container, energy_max bonus helper).

---

### 1.3. Разделить `functions.py` и `characteristics.py` по смыслу (зонтичная) `[M / M / partial (4 из 6 подзадач сделано: 1.3.1/2/2.1/3 done; 1.3.4 + 1.3.5 отложены)]`

Обе изначально «помойки» — смешанная функциональность в одном файле. `functions.py` (~298 строк) содержит: timestamp helpers, energy regen, UI status_bar, day rollover, steps logic, formulas. `characteristics.py` (был ~509 строк, после 1.3.1+1.3.2 — ~215 строк): state container + save/load.

**Декомпозиция (07.05.2026, обсуждение):**
Разбито на 5 подзадач разного размера. Делать инкрементально, по необходимости — полный architectural reorganization откладываем.

**Текущий статус (07.05.2026, после 0.2.3f):**
- ✅ 1.3.1 (мёртвый код удалён, 0.2.3d).
- ✅ 1.3.2 (skill_training_table вынесена, 0.2.3e).
- ✅ 1.3.2.1 (audit чист, 0.2.3f).
- 🟡 1.3.3 — отложено до работы над 1.4.x (save/load переписывается в 1.4.3).
- 🟡 1.3.4 — отложено (см. ниже).
- 🟡 1.3.5 — отложено (overhead > польза при текущем размере проекта).

Зонтичная задача считается **80%-выполненной**. Остаток — bonusный рефакторинг, делать по факту реальной потребности.

#### 1.3.1. Удалить мёртвый код `[L / XS / done (0.2.3d, 07.05.2026)]`

**Что было удалено:** module-level переменные в `characteristics.py:441-468` — 20 unused `energy`, `energy_max`, `stamina`, `mechanics`, `it_technologies`, и 13 *_walking + 2 resistance_* переменных. Все = 0 / 50 на module level, дубликаты с реальными полями `state.gym.*` или `state.energy*`. **Grep подтвердил:** ни одна не импортируется в проекте. Удалены 29 строк (467 → 438). 530 tests pass без изменений, mypy 0 issues. Функция `steps_today_update_manual_nocodeapi_old()` уже была удалена ранее (упоминание в исходной 1.3 устарело).

#### 1.3.2. Вынести `skill_training_table` в `skill_training_data.py` `[L / S / done (0.2.3e, 07.05.2026)]`

**Реализация (07.05.2026):**

1. Создан новый файл `skill_training_data.py` (~230 строк) с:
   - `skill_training_table` — dict 1..30 уровни (steps / energy / money / time).
   - `get_skill_training(level)` — экстраполяция по формуле для уровней > 30.
   - `get_energy_training_data(level)` — wrapper для Daily Bonus.
2. Удалён блок 165-390 из `characteristics.py` (~225 строк). characteristics.py: 438 → 215 строк.
3. Импортёры обновлены **hard break** (без backwards-compat shim'а):
   - `gym.py:8` — `from skill_training_data import skill_training_table, get_energy_training_data`.
   - `web/main.py:35` — `from skill_training_data import skill_training_table`.
4. Добавлен `tests/test_skill_training_data.py` — 10 новых тестов: структура таблицы (1..30 уровни / 4 ключа / level 1 baseline / level 30 baseline / монотонный рост steps), `get_skill_training` (table identity для 1..30, формула для > 30, конкретные значения для lvl 31, lvl 50), `get_energy_training_data` (table delegation, fallback на extrapolation).

**Тесты:** All 540 pass (530 + 10), mypy 0 issues.

#### 1.3.2.1. Audit follow-up: проверить отсутствие stale ссылок на skill_training_table из characteristics `[L / XS / done (0.2.3f, 07.05.2026)]`

**Реализация (07.05.2026):**

Прогон 3 grep-запросов по проекту:
1. `from characteristics import.*skill_training` — 0 результатов в коде (одна находка в `characteristics.py` — комментарий «больше не работает», намеренный).
2. `characteristics\.skill_training_table` (attribute access) — 0 результатов.
3. `skill_training_table.*characteristics` — 2 устаревших упоминания в `docs/game_console.md` (lines 137, 304). Оба исправлены: указание на `skill_training_data.py` вместо `characteristics.py`.

**Изменения:** только `docs/game_console.md` (2 fix'а). Код не трогался — он уже корректен после 1.3.2.

**Можно ли повторно запускать аудит:** да — простой grep, тривиальная routine task. Если в будущем при copy-paste из старого кода всплывёт stale import — снова сделать audit за минуту.

#### 1.3.3. Вынести save/load в `persistence.py` `[M / M / done (20.05.2026, 0.2.4y; combined с 1.4.2)]`

Move `save_characteristic`, `load_characteristic`, `load_data_from_google_sheet_or_csv` из characteristics.py в новый `persistence.py`. Связано с 1.4.x (унификация форматов) — лучше делать вместе либо после.

**Реализовано (20.05.2026, 0.2.4y, combined с 1.4.2):**
- Создан `persistence.py` (~330 строк) — 4 функции вынесены из characteristics.py + unified parser + `_DATETIME_FMT` / `_DATETIME_KEYS` constants.
- `characteristics.py` сокращён 366 → ~125 строк — оставлены только container (`_GameContainer` / `game`) + lifecycle (`init_game_state` + `apply_steps_log_max_merge`).
- Hard break — все импортёры переписаны: game.py / web/sync.py / gym.py / work.py / 3 test файла (`test_characteristics` / `test_sync_e2e` / `test_web_main` monkeypatch fixture).
- Удалён stale `DATE_KEYS` constant (6-keys list был неиспользуемым; реально работает только `_DATETIME_KEYS` 3-keys).
- Lazy imports внутри функций разрешают circular: characteristics.init_game_state → persistence.load_data_from_google_sheet_or_csv → google_sheets_db._rows_to_state_dict → persistence._parse_value (lazy внутри метода).
- 29 новых тестов для `_parse_value` (см. 1.4.2). 1020 passed total, mypy 0 issues (67 source files).

#### 1.3.4. Вынести UI helpers (status_bar, char_info, format_steps) `[L / S / todo (отложено — польза маргинальная)]`

Move 5–7 UI/display функций из functions.py в `ui_helpers.py` или похожее. functions.py остаётся helper-файлом для game logic (energy_time_charge, save_game_date_last_enter, steps_today_set), но без UI слоя. Польза средняя — функционально не критично.

**Решение (07.05.2026, после обсуждения):** **отложено.** Аргументы против немедленной реализации:

1. functions.py 298 строк — нормальный размер, не «мега-помойка». Все функции логически связаны (orchestrate state + display).
2. Польза чисто организационная, функционально ничего не меняется.
3. Тестируемость не улучшится — тесты уже есть и работают независимо от расположения функций.
4. Риск циклических импортов — `status_bar` тянет `CharLevel` (level.py), `equipment_bonus`, `skill_bonus`, `format_timedelta`, `compute_energy_max`. Эти deps переедут в `ui_helpers.py`, может вылезти цикл при импорте из других модулей.
5. **Реальной боли по навигации нет** — все функции легко находятся через grep / IDE Go to Definition.
6. Single-developer проект — organizational layering приносит мало пользы.

**Когда возвращаться:**
- Если functions.py разрастётся до **500+ строк**.
- Если появится реальная боль (новый dependency-loop, потерянная навигация).
- Параллельно с 1.3.5 (полный package layout) — если когда-нибудь до него дойдём.

#### 1.3.5. Полный package layout (game/persistence/ui/tables/api/) `[L / L / todo (отложено)]`

Архитектурный рефакторинг с разделением на пакеты. **Не делаем сейчас** — overhead > польза при текущем размере проекта (~3500 LoC, ~30 файлов). Возвращаемся когда проект вырастет до ~10k+ LoC.

**Статус (07.05.2026):** отложено. Возобновить при существенном росте проекта или если станет реально мешать навигации в коде.

---

### 1.4. Единый формат сохранения (зонтичная) `[M / M / done — все 3 фазы (1.4.1 / 1.4.2 / 1.4.3) закрыты; 1.4.3.1 Legacy cleanup + 1.4.3.2 ISO-8601 — опциональные follow-up'ы]`

Сейчас параллельные форматы сохранения: `characteristic.csv` (ast.literal_eval), Google Sheets (гибридный парсинг), и был `characteristic.txt` (JSON, удалён в 1.4.1). Каждое новое поле требует поддержки в нескольких местах — отсюда баги с датами и типами (например 5.6.1 для adventure end_ts).

**Phasing (07.05.2026, обсуждение):** Разбито на три фазы по нарастающей сложности.

#### 1.4.1. Удалить `characteristic.txt` (write-only zombie) `[L / XS / done (0.2.3c, 07.05.2026)]`

**Проблема:** `characteristic.txt` — JSON-копия state, которая писалась на каждый `save_characteristic()`, но **никогда не читалась** нигде в проекте (ни load_characteristic, ни load_data_from_google_sheet_or_csv, ни тесты, ни web). Третий, дубликатный, никогда не используемый источник.

**Решение (07.05.2026):**
- Удалён блок `with open('characteristic.txt', ...) ... json.dump(...)` из `save_characteristic()` (~5 строк).
- Удалён helper `json_serial(obj)` — он использовался только для default-callback в `json.dump` для .txt; больше не нужен.
- Удалён файл `characteristic.txt` из git.
- `import json` оставлен — используется в CSV serialization для dict/list values.
- CLAUDE.md / changelog обновлены: «3 формата» → «2 формата».

**Не сломалось:**
- Sheets save/load — primary, без изменений.
- CSV save/load — offline fallback, без изменений.
- 530 tests pass, mypy 0 issues.

#### 1.4.2. Унификация парсеров CSV ↔ Sheets `[M / S / done (20.05.2026, 0.2.4y; combined с 1.3.3)]`

**Реализовано (20.05.2026, 0.2.4y, combined с 1.3.3):**
- Unified parser `persistence._parse_value(value, key=None) -> Any` — priority chain: non-string passthrough → empty→None → json.loads → ast.literal_eval → manual int/float/bool detection → datetime для DATE_KEYS → plain string fallback.
- `load_characteristic()` (в persistence.py) использует `_parse_value` для каждой CSV-ячейки. Раньше — inline ~15 строк type-detection.
- `google_sheets_db._rows_to_state_dict()` сократился с ~40 строк до 8 — делегирует в `_parse_value`. Раньше — дублированная hybrid-парсинг логика.
- Format сейвов 100% backwards-compat — никаких изменений в записи / структуре Sheets/CSV.
- 29 тестов для всех edge cases.

После 1.4.1 у нас 2 формата с РАЗНЫМ парсингом:
- CSV: `ast.literal_eval` для nested dict/list, плюс explicit conversion в `from_dict`.
- Sheets: hybrid `_rows_to_state_dict` пробует `json.loads` → `ast.literal_eval` → manual int/float/bool/None/datetime detection.

**Цель:** один общий helper `_parse_value(v) -> Any`, который принимает строку из любого источника и возвращает Python-значение по тому же набору правил. Удаляет дубликат логики между `characteristics.py:load_characteristic` и `google_sheets_db.py:_rows_to_state_dict`.

**Скоуп (~50 строк):**
1. Helper `_parse_value(v: str) -> Any` в `state.py` (или новый `serialization.py`).
2. `load_characteristic` использует его для каждой ячейки CSV.
3. `_rows_to_state_dict` использует его для Value-колонки Sheets.
4. Тесты на единый набор edge cases (datetime / dict / list / int / float / bool / None / empty).

**НЕ меняет формат сейвов** — backwards-compat 100%.

#### 1.4.3. JSON-blob в Sheets (single-cell) + state.json offline primary `[M / M / done (20.05.2026, 0.2.5)]`

**⚠️ Breaking change в формате сохранения — миграция через auto-detect.**

**Реализация (20.05.2026, 0.2.5, Variant B per design discussion):**

1. **Sheets layout** — `game_state` лист теперь хранит ОДНУ строку с 2 ячейками:
   - **A1** = `last_modified` (float) — для fast `load_meta` через `acell('A1')` без scan rows.
   - **B1** = JSON-blob всего state через `state.to_dict()` + `json.dumps(default=_json_blob_default)`.

2. **Auto-detect + auto-migration** (защищает pre-existing сейвы):
   - `GameStateRepo.load` сначала читает `ws.get_all_values()`; если first row = `['Key', 'Value']` → fallback на legacy `_rows_to_state_dict` с migration notice; иначе blob parser.
   - `GameStateRepo.load_meta` сначала пробует `acell('A1')` (fast-path 1 read), если cell не parsable как float (legacy header или error) → fallback на старый scan rows.
   - Первый save переписывает в новый формат — clean migration без отдельного script'а.

3. **Offline format** — `characteristic.csv` (плоский Key/Value) → `state.json` (полный JSON-blob, indent=2):
   - `save_characteristic` пишет state.json вместо CSV.
   - `load_state_json` (новый) — primary reader; конвертирует `_DATETIME_KEYS` обратно из str через strptime.
   - `_load_local_fallback` (новый orchestrator) — state.json первым, при отсутствии файла → legacy `load_characteristic` (CSV reader).

4. **Backup script** — `scripts/backup_sheets_before_migration.py` (one-shot) экспортит текущий game_state в `backup_before_1.4.3_YYYYMMDD_HHMMSS.json` ДО deploy. Safety net на случай если auto-migration сломается.

5. **Datetime serialization** — `_json_default` / `_json_blob_default` конвертируют datetime в legacy strftime формат (`_DATETIME_FMT = '%Y-%m-%d %H:%M:%S.%f'`). Round-trip через `_DATETIME_KEYS` → strptime. Переход на ISO-8601 намеренно отложен в 1.4.3.2.

6. **.gitignore** — добавлены `state.json` + `backup_before_*.json`. `characteristic.csv` оставлен (удалится в 1.4.3.1).

**Что НЕ делалось в этой задаче:**
- **Phase 3 (ISO-8601 datetime)** — вынесено в 1.4.3.2 для минимизации blast radius миграции.
- **Удаление legacy parser'ов** (Key/Value + CSV reader/writer) — вынесено в 1.4.3.1 после bake-test'а.
- **Deploy на production server (192.168.0.155)** — отдельный шаг.

**Тесты:** 23 новых (14 в test_sheets_repo + 9 в test_persistence), 7 existing обновлены под новый формат (mock'и `_mock_worksheet(meta=...)` для acell fast-path). 1045 passed total, mypy 0 issues (68 source files).

**Variant trade-off (зафиксировано):** выбран **B** (last_modified в A1 + blob в B1) — сохраняет 4.54.2 fast-path для optimistic concurrency. Альтернативы: A (single cell pure blob, теряет fast-path), C (dual-write transitional, 2× quota), D (auto-detect single-cell без отдельного last_modified). **CSV** удалён полностью — `Перевести на единый файл state.json` per user choice (вместо `Оставить плоский Key/Value`).

##### 1.4.3.1. Legacy cleanup — удалить Key/Value parser + CSV reader `[L / S / todo (запланировано через 1-2 недели после bake-test 1.4.3 / 0.2.5)]`

После того как все пользователи 2Walks (на момент 1.4.3 — один игрок) пожили на новой схеме 1-2 недели без рассинхронов / потерянных сейвов:

1. Удалить из `google_sheets_db.py`: `_state_dict_to_rows`, `_rows_to_state_dict`, `_is_legacy_kv_layout`, fallback ветку в `load`, legacy fallback scan в `load_meta`.
2. Удалить из `persistence.py`: `load_characteristic` (CSV reader), `CHARACTERISTIC_CSV_PATH` constant, fallback в `_load_local_fallback`.
3. Удалить из `.gitignore` строку `characteristic.csv`.
4. Локально удалить файл `characteristic.csv` (если ещё есть).
5. Тесты на legacy layout удалить (или оставить как regression «должно сломаться чтобы напомнить»).
6. Update CLAUDE.md и changelog.

**Не делать раньше времени** — auto-detect cost (~0 ms на новом формате) ничтожен; преимущество только в чистоте кода.

##### 1.4.3.2. Datetime → ISO-8601 в state.py `[L / S / todo (опциональная упрощалка)]`

Перевести `to_dict` / `from_dict` с legacy strftime (`_DATETIME_FMT = '%Y-%m-%d %H:%M:%S.%f'`) на нативный ISO-8601 (`datetime.isoformat()` / `datetime.fromisoformat()`).

Преимущества: убирает custom `_DATETIME_FMT` constant + custom default-функцию в `json.dumps`. Native `datetime.isoformat()` поддерживается без default-callback'а в json.dump (через объект proxy конвертера или вручную); fromisoformat принимает свой output.

**Зависимость:** делать **после** 1.4.3.1 (когда legacy CSV/Key-Value parser'ы удалены — иначе придётся поддерживать два datetime формата параллельно).

**Blast radius:** новые сейвы будут содержать ISO-формат, старые legacy сейвы (если пользователь восстанавливает из backup) перестанут парситься. Мелкая, но breaking change в формате сейва.

---

### 1.5. Заменить рекурсивные меню на циклы `[M / M / done (0.2.1h)]`

**Переоценка Effort с S на M** — первоначальная оценка опиралась на "везде одинаковый шаблон". Анализ (24.04.2026) показал ~15 реальных мест в 6 файлах, плюс решение по UX и длинные меню (`adventure_menu`, `gym_menu`) делают задачу больше, чем казалось.

#### Классификация рекурсивных вызовов

Анализ после закрытия 2.5 выделил три разные категории:

**Категория A — ретрай при ошибке** (то, что реально решает 1.5):
пользователь ввёл ерунду → функция меню вызывает саму себя → каждая попытка добавляет стек-фрейм. Теоретически — `RecursionError` после ~1000 невалидных вводов подряд. Практически — маловероятно, так что задача скорее про **идиоматичность и чистоту трейсбэков**, чем про реальный баг.

**Категория B — навигация между меню**: меню → подменю → возврат в родителя через прямой вызов функции. Не ошибка, но тоже строит стек. Убрать без структурной переработки (возврат кодов, стейт-машина) не получится — это уровень **1.1 GameState**. **Отложено до 1.1.**

**Категория C — `get_access_token()`** в `get_token_fitnes_api.py`: была рекурсия ограничена одной глубиной. Файл целиком удалён в задаче **4.16** (2026-04-27) — пункт более не актуален.

#### Ключевое UX-решение

Наивный `while True: ... continue` на невалиде покажет только `>>> ` без самого меню — регрессия относительно текущего поведения. Правильно: держать print-блок меню **внутри** цикла, чтобы каждый reprompt перерисовывал опции. Для длинных меню (`adventure_menu` ~45 строк, `gym_menu` ~30 строк) — вынести рендеринг в helper-функцию, чтобы while не раздувался.

#### Что НЕ входит в скоуп 1.5

- **Категория B (навигация).** Места: `equipment.py:54,152,157`, `adventure.py:115`, `shop.py:32,35,86,88`, `inventory.py:15,86,92`. Откладываются до 1.1.
- **`get_token_fitnes_api.py`** — файл удалён в 4.16 (2026-04-27), пункт не актуален.
- **Helper-функция `prompt_choice()` / `prompt_int()`.** Её место — в новом UI-модуле после 1.3 (раздел `functions.py`). Сейчас внутренняя кухня — инлайн `while True` в каждом меню.

#### Подзадачи (по файлам, в порядке возрастания сложности)

##### 1.5.1. `work.py` — work_choice, ask_hours `[L / S / done (0.2.1h)]`

Ретраи (3 места):
- `work.py:54` — `work_choice` else → self
- `work.py:96` — `ask_hours` часы вне 1..max_available_hours → self
- `work.py:99` — `ask_hours` `except ValueError` → self

Стратегия: `work_choice` обернуть в `while True`, print-блок меню внутрь, каждая валидная ветка — `break`. В `ask_hours` — два retry-места слить в один цикл с `try/except ValueError: continue` внутри.

Учесть: `work.py:113` (`add_working_hours` else → `self.work_choice()`) — это категория B (навигация), не трогаем.

##### 1.5.2. `equipment.py` — equipment_change, change_item_in_slot `[L / S / done (0.2.1h)]`

Ретраи (3 места):
- `equipment.py:97` — `equipment_change` else → self
- `equipment.py:166` — `change_item_in_slot` else → self (unused index)
- `equipment.py:169` — `change_item_in_slot` `except ValueError` → self

Стратегия: `equipment_change` — короткое меню на 6 пунктов, обернуть одним `while True`. `change_item_in_slot` — int-input с ValueError; два retry-места слить в один loop.

Учесть: `equipment.py:152,157` (после действия `Equipment.equipment_view(self=None)`) — категория B, не трогаем.

##### 1.5.3. `inventory.py` — inventory_menu, sold_item `[L / S / done (0.2.1h)]`

Ретраи (5 мест):
- `inventory.py:19` — `inventory_menu` else → self
- `inventory.py:88, 90, 94` — `sold_item` ветки "0"/else/за границей индекса → self
- `inventory.py:96` — `sold_item` `except ValueError` → self

Стратегия: `inventory_menu` — простой while. `sold_item` сложнее — два уровня input'а (выбор предмета + подтверждение продажи). Возможно стоит выделить подтверждение в отдельную функцию `_confirm_sale(item)`, чтобы не вкладывать циклы.

Учесть: `inventory.py:15,86,92` — переходы между `inventory_menu` ↔ `sold_item` — категория B, не трогаем.

##### 1.5.4. `shop.py` — shop_menu + подменю `[L / S / done (0.2.1h)]`

Ретраи:
- `shop.py:43` — `shop_menu` else → self
- плюс ~6 аналогичных мест в `shop_menu_food_and_water`, `clothes_head`, `clothes_jacket`, `clothes_pants`, `clothes_gloves`, `clothes_shoes`, `shop_menu_clothes` — каждая функция на else или после неудачной покупки вызывает себя.

Стратегия: основной `shop_menu` + `shop_menu_food_and_water` в while. Clothes-функции — заглушки, минимальная правка в том же стиле (пока Shop не переписан в 4.7, но при рерайте это перезапишется).

Учесть: `shop.py:32,35,86,88` — вызовы `Shop.shop_menu(self)` после действия — категория B, не трогаем.

##### 1.5.5. `adventure.py` — adventure_menu + adventure_choice + adventure_choice_confirmation `[M / S / done (0.2.1h)]`

Ретраи (2 места):
- `adventure.py:132` — `adventure_choice` else → `adventure_menu()`
- `adventure.py:151` — `adventure_choice_confirmation` else → self

Особенность: `adventure_menu` — 45 строк рендеринга, `adventure_choice` — маленький диспетчер. Сейчас на невалиде `adventure_choice` → `adventure_menu` → `adventure_choice` — это **ping-pong рекурсия через 2 функции**.

Два варианта реализации:
- **Вариант 1 (слияние):** объединить `adventure_menu` + `adventure_choice` в одну функцию с `while True` внутри. Просто, но функция становится большой.
- **Вариант 2 (helper):** вынести рендеринг в `_render_adventure_menu()`, `adventure_choice` превращается в `while True: _render_adventure_menu(); ask = input(); dispatch`. Сложнее правка, но чище.

Решение принимается при реализации. Склоняюсь к **варианту 2**.

Учесть: `adventure.py:147,149` (после `check_requirements` / `adventure_choice_confirmation` → `adventure_menu`) — категория B, не трогаем.

##### 1.5.6. `gym.py` — gym_menu `[M / S / done (0.2.1h)]`

Ретраи (4 места):
- `gym.py:142, 144, 146, 149` — различные else/except в `gym_menu` → self

Особенность: `gym_menu` ~60 строк, включая рендеринг таблицы скиллов + диспетчер + запуск тренировки. Нужен helper для рендеринга, иначе `while True` станет огромным.

Попутно: в 147 строке есть `except Exception as error:` — широкий перехват, который стоит сузить (формально это скоуп 2.5, но пропущен, т.к. 2.5 искала только голые `except:`, а здесь `Exception`). Можно закрыть этим же коммитом — отдельной правкой не стоит.

Учесть: есть ещё `gym.py:251` (`Skill_Training.check_requirements` → `gym_menu()` при нехватке ресурсов) — это категория B, не трогаем.

---

**Порядок выполнения:** 1.5.1 → 1.5.2 → 1.5.3 → 1.5.4 → 1.5.5 → 1.5.6. Каждая подзадача — самостоятельное изменение, свой мини-смоук-тест (меню открыть, ввести ерунду, Ctrl+C). Коммитить можно либо после каждой, либо пакетом по 2-3.

**Сделано (04.05.2026, версия 0.2.1h):** все 6 подзадач закрыты одним batch-коммитом. Pattern: каждая функция-меню обёрнута в `while True`, с `continue` на ошибке/невалиде и `return` на успехе. Длинные меню (gym, adventure) получили helper-функции `_render_<menu>` для рендеринга, чтобы тело loop'а не раздувалось. В gym.py попутно: (1) узкий `except ValueError` вместо `except Exception` (раньше маскировал баги); (2) удалён рекурсивный вызов `gym_menu(self._state)` из `Skill_Training.check_requirements` — внешний loop сам перерисует через `continue`. В shop.py 4 stub-функции для одежды слиты в общий `_clothes_stub(label, header)` (DRY). Добавлены 2 regression-теста: `test_gym_menu_recovers_from_invalid_input_without_recursion`, `test_work_choice_recovers_from_invalid_input_without_recursion`. All 357 tests pass. Существующие тесты не сломаны (использовали monkeypatch input — продолжают работать с while-loop'ами).

---

### 1.6. Items как dataclass, не как dict со списками-обёртками `[M / M / todo (отложено — большой объём, низкий приоритет)]`

Сейчас `item['grade'][0]`, `item['bonus'][0]` везде. Одна забытая `[0]` = баг в UI или продаже.

```python
@dataclass
class Item:
    item_type: str           # ring | necklace | helmet | ...
    grade: str               # c-grade | b-grade | ...
    characteristic: str      # stamina | luck | ...
    bonus: int
    quality: float
    price: int
    # опционально на будущее для мульти-эффектов:
    extra_effects: list[Effect] = field(default_factory=list)
```

Миграция старого инвентаря — одна функция `migrate_item(dict) -> Item`.

**Статус (08.05.2026):** отложено. Аргументы за откладывание:

1. **Большой объём, малая пользовательская польза.** ~200+ строк изменений (64 ссылки `item['key'][0]` в 5 файлах + ~30 тестов + state.py + save/load + migration). ~2 часа работы с риском ошибок миграции и breaking save format.
2. **Тех-долг, игрок не увидит.** UI не улучшается. Тесты уже есть и работают.
3. **Лучше делать вместе с 4.7 (Дописать Shop).** Shop будет добавлять новые items — refactor станет нативной частью, а не отдельной нагрузкой.
4. **Сейчас более impactful — фичи для игрока:** 4.2 (Отчёт «пока тебя не было»), 4.3 (Стрик-счётчик), 4.49.2.2 (Auto-repay), 4.34 (Прогресс-бар adventures).

**Возобновить когда:**
- Делается **4.7** (Дописать Shop) — естественно объединить refactor с расширением Shop.
- Появится реальный баг из-за забытой `[0]`.
- Нужны новые типы items (бустеры / расходники из 4.40) с разными полями — `extra_effects` понадобится тогда.

**Альтернатива на потом (XS):** мини-подзадача `1.6.1` — добавить TypedDict для items (~30 мин). Даст IDE-подсказки + mypy типизацию, не решая основную проблему list-обёрток. Если откладываемая 1.6 затянется — можно сделать как промежуточный шаг.

---

### 1.7. Единый словарь команд вместо `if x == 's' or x == 'ы'` `[L / S / done]`

**Сделано:** 60-строчный if-elif в `game.py` заменён на `COMMANDS.get(temp_number, unknown_command)()`. Внутри `location_selection()`:
- `COMMANDS` — единый dict с Latin-ключами.
- `LAYOUT_RU_TO_EN` — авто-маппинг русских дублей (одна точка правды для раскладки).
- Helper `enter_location(loc, enter_fn, can_reopen=False, call_map_on_switch=True)` — инкапсулирует все варианты смены локации (с/без `location_change_map`, с возможностью повторного захода).
- Вспомогательные функции: `save_game_local_and_cloud`, `save_and_exit`, `load_from_cloud`, `unknown_command`.

**Попутно:** исправлен скрытый баг в команде `l` (Load from Cloud). Было: `char_characteristic = load_...()` — локальное присваивание, другие модули видели старый dict. Стало: `char_characteristic.update(load_...())` — мутация существующего объекта, все импортёры видят новые данные.

**Добавлено:** сообщение "Неизвестная команда. Попробуй ещё раз." вместо молчаливого fallthrough при невалидном вводе.

---

## 2. Баги (из `bugs.txt` + аудит)

### 2.1. "Новый день — можно использовать вчерашние шаги, если не сохранить" `[H / S / done (02.05.2026)]`

**Сделано в 0.2.0k:**
- Запись в `save.txt` удалена из `functions.save_game_date_last_enter()` — единственный источник правды для day rollover теперь `state.date_last_enter` (сравнение с `datetime.now().date()`).
- Файл `save.txt` удалён из репозитория (`git rm`).
- Добавлен в `.gitignore` — защита от случайного коммита, если кто-то запустит старую версию кода.
- Тесты: `test_save_game_date_last_enter_new_day_resets` обновлён (assert'ы про save_file удалены), добавлен `test_save_game_date_last_enter_does_not_create_save_txt`.
- Документация (CLAUDE.md, docs/game_console.md) обновлена.

**Эффект:** day rollover работает идентично, артефакт legacy полностью убран. У игроков, у кого save.txt уже лежит — файл становится осиротевшим (не читается, не пишется), не мешает.

**Историческая справка:**
- Было: `save.txt` писался в `save_game_date_last_enter()` и читался в `api.steps_today_update()` (модуль `api.py` удалён в 4.16). Гонка через `save.txt` ушла после удаления Fitness API.
- В 1.2 (0.2.0c): дубликат проверки даты при импорте `characteristics.py` (через `date_check_steps_today_used()`) удалён.
- В 2.1 (0.2.0k): убрана последняя запись в `save.txt`, файл удалён.

---

### 2.2. Регенерация энергии — накопленные проблемы в `energy_time_charge` `[M / S / done (02.05.2026)]`

Все три подзадачи закрыты: 2.2.1 (косметика + строгое `>=`) и 2.2.2 (sync стампа при `energy >= energy_max` в `energy_time_charge`) — в 0.2.0a; 2.2.3 (sync стампа при тратах через `actions.try_spend` если перед тратой был на max) — в 0.2.0l (02.05.2026).


Функция `energy_time_charge()` в `functions.py:18-39` тикается на каждом возврате в главное меню и регенерирует энергию по формуле "1 единица каждые `interval = speed_skill_equipment_and_level_bonus(60)` секунд". В ней накопилось 5 разных по природе проблем, которые удобно править подзадачами — большинство мелкие и изолированные, одна требует изменений в других файлах.

#### Разобранные проблемы

1. **`round()` поверх `//` — мёртвый код.** `(a - b) // c` — это floor-деление, уже возвращает целое. `round()` здесь ничего не делает. Исторический комментарий в коде "Ошибка в округлении 1.6" ссылается на поведение `round(1.6) = 2`, но 1.6 в этой формуле никогда не появляется (floor уже усекает дробную часть). Убираем для читаемости.

2. **Строгое `>` вместо `>=`.** `functions.py:24`: `if elapsed > interval`. Ровно на 60-й секунде энергия не начисляется. Аналог фикса 2.7 в `level.py`.

3. **Неатомарные вызовы `timestamp_now()`.** В одном блоке функция вызывается 3-4 раза с микросекундными разрывами. Как следствие, debug-print в `functions.py:32-33` печатает значения **уже после** обновления стампа и показывает "Добавлено energy: 0" вместо реального прироста. Фикс — снапшотить `now = timestamp_now()` в локальную переменную и использовать её везде.

4. **"Бесплатная энергия после максимума" (баг из `bugs.txt`).** Сценарий: энергия достигла максимума в `t=0` (стамп остался где-то в прошлом). Игрок не в меню 10 минут. В `t=50` тратит 10 энергии через Gym (места трат не двигают стамп). В `t=600` заходит в меню — функция видит `elapsed = 630` и начисляет 10 единиц. Игрок получает обратно всё, что потратил.

   Разделяется на два фикса:
   - **4a (частичный):** при тике с `energy >= energy_max` форсированно двигать стамп к `now`. Решает частый кейс, когда игрок периодически возвращается в меню при полной энергии. Правка только внутри `energy_time_charge()`.
   - **4b (полный):** при трате энергии в Gym/Work/Adventure синкать стамп. Требует правок в `gym.py`, `work.py`, `adventure.py` — везде, где стоит `char_characteristic['energy'] -= ...`. Это расширение скоупа.

5. **Пост-клин `if energy > energy_max` после сложения.** Страховка в `functions.py:35-36` на случай, если в строке 28 переплюнули максимум. Не баг, но читаемее через `min(energy + points, energy_max)` в одном месте.

#### Подзадачи

##### 2.2.1. Косметическая чистка `energy_time_charge` `[L / S / done]`

**Сделано:** функция переписана целиком (`functions.py:18-52`). Убран мёртвый `round()`, добавлен снапшот `now`, `>` заменено на `>=`, клэмп сведён в `min(...)`. Debug-принт теперь показывает реальный прирост и "До следующей +1: N sec." вместо misleading выводов. Старые `# Bug:` комментарии удалены.

##### 2.2.2. Частичный фикс "бесплатной энергии" — sync стампа при максимуме `[M / S / done]`

**Сделано:** в начале `energy_time_charge()` добавлена ветка `if energy >= energy_max: char_characteristic['energy_time_stamp'] = now; return`. Также закрыт кейс излишка (если `energy > energy_max` — клэмпим вниз; раньше это делалось пост-фактум, теперь в одном месте с sync стампа).

Для полного закрытия бага из `bugs.txt` нужна 2.2.3 (sync стампа в местах трат).

##### 2.2.3. Полный фикс "бесплатной энергии" — sync стампа при тратах `[M / S / done (02.05.2026)]`

**Сделано в 0.2.0l** (Variant B — sync только если был на max):

```python
# actions.py:try_spend
if energy:
    was_full = state.energy >= state.energy_max
    state.energy -= energy
    if was_full:
        state.energy_time_stamp = datetime.now().timestamp()
```

**Семантика:** если перед тратой энергия была на максимуме → стамп обновляется к `now` (закрывает эксплоит "копил время на full → потратил → следующий тик начислил накопленное"). Если перед тратой энергия НЕ была на максимуме → стамп не двигается (не штрафуем за частичный прогресс к +1, регенерация продолжается с прежней точки).

**Тесты:**
- `tests/test_actions.py` — 4 unit-теста (was-full → reset; not-full → keep; zero-energy → no-op; failed-spend → no mutation).
- `tests/test_functions.py:test_no_free_energy_after_spend_from_max` — conformance-тест на сам баг из `bugs.txt`: full energy за 1000 сек назад → try_spend(10) → energy_time_charge → energy=40 (не 50, как был бы баг).

**Минор edge case:** игрок может частично прокачать до +1 (например, 49/50 → ждёт 60 сек → +1 → опять 50/50 → тратит 1) и теоретически "поймать" момент, когда стамп не сбросится. На практике маловероятно и значимый эксплоит не дает.

---

### 2.3. Adventure-класс не видит прокачку во время сессии `[M / S / done (30.04.2026)]`

**Сделано в рамках 1.1 (Phase 4 commit 3):**
- `Adventure.__init__` теперь принимает `state: GameState` и пересоздаётся в каждой итерации главного цикла (`game.py`) — так что `self.adventures` строится с актуальной прокачкой.
- Заодно зафиксирован сопутствующий bug: `apply_move_optimization_adventure` мутировал словарь `adventure_data_table` in-place при каждом конструировании Adventure — значения сходились к 0 со временем. Теперь `Adventure.__init__` копирует записи через `dict(...)` перед применением.
- Drop-сторона: `drop.py:luck_chr` (тоже фиксировался при импорте) заменён на `current_luck(state)` — Luck из Gym видна на следующем дропе без рестарта.

---

### 2.4. При прокачке Daily-бонуса обнуляется, если шаги < 10k `[M / S / done (02.05.2026)]`

**Сделано в 0.2.0m:** в `save_game_date_last_enter()` перед вызовом `today_steps_to_yesterday_steps()` добавлен `_max_merge_today_from_log(state, last_date)` — поднимает `state.steps.today` до максимума записей в `steps_log` за уходящий день. Это закрывает кейс "stale state.steps.today на момент rollover": если игрок ввёл шаги через web/API (записалось в `steps_log`), но `game_state` snapshot в Sheets не успел обновиться (CLI не сохранялся), при следующем запуске rollover не сбросит бонус незаслуженно.

**Семантика:**
- В логе за вчера ≥10k → `state.steps.today` поднимается → `yesterday >= 10k` → `daily_bonus += 1`.
- В логе за вчера <10k или лога нет → `state.steps.today` не меняется → `yesterday < 10k` → `daily_bonus = 0` (корректное наказание за непройденный день).
- Sheets недоступен → silent-fail, max-merge пропускается.

**Тесты в `test_functions.py`:** 4 новых — daily_bonus_increments_when_log_has_10k_yesterday, _resets_when_yesterday_no_log, _resets_when_log_yesterday_under_10k, _max_merge_silent_fail_on_sheets_error.

**Историческая справка:** в эпоху Fitness API баг возникал из-за гонки "API не успел ответить — yesterday получил 0". После 4.16 (удаление Fitness API) и 4.14/4.15 (steps_log) сценарий сместился: теперь это защита от "ввод через web без сохранения CLI". Streak Freeze (4.36) — отдельная feature, эта задача только базовое корректное поведение rollover'а.

---

### 2.5. Голые `except:` глотают `KeyboardInterrupt` и ошибки программиста `[M / S / done]`

**Сделано (24.04.2026):** закрыты 19 из 20 мест (20-е — `functions.py:282` — оставлено для задачи 5.3, т.к. вся функция `steps_today_update_manual_nocodeapi_old()` помечена к удалению).

Разбивка по паттернам:
- **14 мест** с `input()` + только строковым сравнением — `try/except` удалён целиком. `input()` на валидной строке не падает, а `else:`-ветка уже обрабатывает невалидный ввод. Файлы: `work.py:56,119`, `equipment.py:99,159`, `adventure.py:134`, `shop.py` (7 мест: `shop_menu`, `shop_menu_food_and_water`, `clothes_head`, `clothes_jacket`, `clothes_pants`, `clothes_gloves`, `clothes_shoes`, `shop_menu_clothes`), `inventory.py:92`.
- **3 места** с `int(input(...))` — сужено до `except ValueError:`. Файлы: `work.py:101`, `equipment.py:174`, `inventory.py:98`.
- **1 место** с доступом к полю словаря — сужено до `except (KeyError, IndexError, TypeError):`. `inventory.py:84`.
- **1 место** в `game.py:124` (главное меню) — `try/except` удалён; `COMMANDS.get(..., unknown_command)` уже обрабатывает любую строку.

**Бонус:** в `game.py:157-161` добавлена обёртка `try/except (KeyboardInterrupt, EOFError):` вокруг `game()` на верхнем уровне — `Ctrl+C`/`Ctrl+D` теперь выходят с сообщением "Выход без сохранения. Пока!" без трейсбэка. Версия на экране обновлена с `0.1.0` до `0.1.1a`.

**Побочный эффект:** рекурсия в меню никуда не делась (задача 1.5 её решит). Но Ctrl+C больше не уходит в бесконечный цикл перезапроса.

---

### 2.6. При входе в меню работы (когда уже работаешь) обнуляется ЗП `[L / S / done (косвенно через 0.2.0a, подтверждено в 0.2.1h)]`

**Не воспроизводится в текущей версии.** Запись в `bugs.txt` актуальна для версий до 0.2.0a (Phase 4 GameState rollout, апрель 2026). Тогда хранение salary было через словарь `char_characteristic`, и при загрузке из CSV/Sheets с неполным форматом `salary` мог остаться как 0. После миграции на `state.gym` / `state.work` dataclass и через `state.from_dict` (с явным `int(d.get('work_salary', 0))`) — поле корректно парсится, а `Work.check_requirements` всегда задаёт `salary` из `work_requirements[work_type]['salary']` при старте/продлении смены.

**Воспроизведение 04.05.2026 показало:** при стартe смены Watchman 1 час → state.work.salary=2, state.work.hours=1. Меню `add_working_hours` корректно показывает `Место работы: Watchman, в час - 2 $ (💰: + 2 $)` — это `salary × hours = 2 × 1 = 2 $`, как и должно быть. То что игроку показалось "обнулением" — на самом деле произведение `salary × hours` где hours=1.

**Закрыто без code changes.** bugs.txt отмечен `[FIXED 0.2.0a, task 2.6]`.

---

### 2.7. Расчёт уровня использует строгое `>` вместо `>=` `[L / S / done]`

**Сделано:** `level.py:54` — `>` заменён на `>=`. Теперь ровно 10 000 потраченных шагов даёт уровень 1, 20 000 — уровень 2 и т.д. Попутно синхронизирована `docs/levels.md` (кодовый блок и формулировка "не меньше" вместо "строго больше").

---

### 2.8. `walk_20k` всегда дропает `None` `[H / S / done]`

**Сделано (24.04.2026):** в `drop.py:76-92` добавлена ветка `elif hard == 'walk_20k':` по аналогии с walk_15k/walk_25k. Пул дропа — `a-grade / s-grade / s+grade` (соответствует описанию меню в `adventure.py:100`). Структура rolls идентична соседним веткам: `luck_chr`-модифицированный global gate → три grade-roll'а → возврат минимального, прошедшего свой порог. Ручное тестирование перенесено на момент после 3.2.1, т.к. механика дропа всё равно подвергается рефакторингу.

---

### 2.9. `steps_can_use` показывает вчерашнее значение в первый момент нового дня `[M / S / done]`

**Найдено 2026-04-27** при первом запуске игры после удаления Fitness API (задача 4.16). Symptom: на новый день, до первого ввода шагов через `+`, в `status_bar` отображалось `Steps 🏃: 0 / 11,476` — где 11,476 это **вчерашний** `steps_can_use`, не имеющий отношения к сегодняшним фактическим шагам.

**Диагноз:** `save_game_date_last_enter()` в `functions.py:96+` имел две ветки:
- "новый день": сбрасывал `steps_today=0`, `steps_today_used=0`, обновлял `date_last_enter` и `steps_yesterday`. **Не пересчитывал `steps_can_use`** — он оставался равен значению, загруженному из сейва (вчерашнему).
- "тот же день": пересчитывал `steps_can_use = steps_today - steps_today_used + bonuses`.

После сброса `steps_today=0` следующий тик уже попадал в ветку "тот же день" и пересчитывал корректно. Но **первый кадр** статус-бара после смены дня показывал stale-значение.

Это был **pre-existing bug**: при наличии Fitness API он маскировался тем, что `steps_today_update()` после сброса всё равно подтягивал актуальные шаги от API → `steps_can_use` хоть и не пересчитывался, но `steps_today` был ближе к правде. После 4.16 (только ручной ввод) баг стал виден явно: `steps_today` всегда 0 на старте дня, а stale `steps_can_use` бросался в глаза.

**Сделано (2026-04-27):** в `functions.py:save_game_date_last_enter()` расчёт `steps_can_use` вынесен за пределы `if/elif` — теперь выполняется один раз в конце функции, для обеих веток. Убрана мёртвая `else: print('Error...')` (любая строка либо равна, либо не равна — третьего не дано). Заодно убраны устаревшие комментарии про "API" в шапке функции.

**Данные не были повреждены:** `steps_today`, `steps_yesterday`, `steps_today_used` обновлялись корректно — проблема была только в кэше `steps_can_use`. Реальных шагов баг не съедал.

---

### 2.10. Функция `time()` не сворачивает часы в дни `[L / S / done (0.2.1t)]`

**Найдено 2026-04-27.** `functions_02.py:4-11` — функция форматирования времени, принимает `x` в минутах. При `x > 60` возвращает `"H час M мин"` без проверки порога 24h.

**Связанная задача (закрыта в 0.2.1i, 2026-05-05):** в `functions_02.py` добавлен новый helper `format_timedelta(td)` — он решает аналогичную проблему **для таймеров обратного отсчёта** (work shift / training / adventure countdown). Раньше CLI использовал `str(timedelta).split('.')[0]` (показывало `"1 day, 17:25:22"` после 24h в нечитаемом английском формате), web JS — Math.floor(seconds/3600) без учёта дней (показывало `"25:30:42"`). Теперь оба используют единый формат `Yг Mмес Wнед Dд H:MM:SS` (краткие русские суффиксы). Сама `time(x)` для отображения стоимости активности **не изменена** — её замена остаётся скоупом 2.10/2.11.

**Воспроизведение:** Gym → меню скиллов → Stamina lvl 19 показывает `🕑: 48 час 10 мин.` вместо ожидаемого `2 дн 0 час 10 мин.`.

**Места использования** (14 вызовов в 3 файлах, все принимают минуты):
- `gym.py` — 9 мест: меню всех 8 скиллов в `gym_menu()`, `get_lvl_up_info()`, два вызова в `start_skill_training()` (`gym.py:198, 274`).
- `work.py` — 3 места: почасовая ставка в `work_choice()` и `ask_hours()` (`work.py:29, 71`), общее время работы в `check_requirements()` (`work.py:153`).
- `adventure.py` — 2 места: меню приключений (`adventure.py:30`), подтверждение выбора (`adventure.py:203`).

**Фикс:** добавить в `time(x)` ветку для `x >= 1440` (24 часа в минутах). Логика отображения — обрезаем ведущие нулевые компоненты, сохраняя младшие:
- `x < 60` → `"X мин."`
- `60 <= x < 1440` → `"H час M мин."`
- `x >= 1440` → `"D дн H час M мин."` (всегда все три компонента, даже если `H == 0` или `M == 0`)

То есть **скрываем только ведущие нули** (если дней нет — не показываем "0 дн"), но **не скрываем средние/конечные** (внутри блока с днями всегда есть и часы, и минуты).

**Вне скоупа:** грамматика числительных — выделено в задачу **2.11**.

**Сделано (05.05.2026, 0.2.1t):** реализован вариант D (расширение `time(x)` с днями + цветами) с дополнительным расширением до месяцев и годов "на будущее" (на случай экстремальных значений). Полный набор уровней:
- `x ≤ 60` → `"X мин."`
- `60 < x < 1440` → `"H ч. M мин."` (как было до 0.2.1t)
- `1440 ≤ x < 43200` → `"D дн. H ч. M мин."` (новое — закрывает баг "48 час 10 мин." → "2 дн. 0 ч. 10 мин.")
- `43200 ≤ x < 525600` → `"MO мес. D дн. H ч. M мин."` (новое — для гипотетических уровней навыков)
- `x ≥ 525600` → `"Y г. MO мес. D дн. H ч. M мин."` (новое — экстремальные кейсы)

Логика "ведущие нули": если значение не превышает порог следующей единицы, она не показывается. Если есть — все младшие компоненты выводятся даже с нулями (например ровно 3 дня → `"3 дн. 0 ч. 0 мин."`). Новые константы `_MIN_PER_HOUR/DAY/MONTH/YEAR` в functions_02.py. Helper `_color(n)` для DRY обёртки числа в colorama LIGHTBLUE. Месяц = 30 дней, год = 365 дней (упрощённо, синхронизировано с `format_timedelta`). 12 новых тестов в test_functions_02.py: minutes only, hours+mins (включая граничные 60/1439), days exact + partial (включая пример skill_lvl 19 из TASKS), skill_lvl 30, just under month, months exact + partial, just under year, year exact, full year+months+days+hours+mins, проверка наличия colorama-кодов. Все 393 теста проходят (381 + 12).

---

### 2.11. Корректные формы числительных в `time()` `[L / M / done (минимальная правка, 0.2.1s)]`

Сейчас `time()` всегда выводит "час" / "мин." / (после 2.10) "дн", независимо от числа. По русской грамматике должно быть:
- 1 → "1 час", "1 минута", "1 день"
- 2-4 → "2 часа", "3 минуты", "4 дня"
- 5-20 → "5 часов", "6 минут", "7 дней"
- 21 → "21 час" (как 1)
- 22-24 → "22 часа" (как 2-4)
- и т.д. — паттерн повторяется на единицах десятка, кроме 11-14 (всегда множественное).

**Implementation:** helper `pluralize_ru(n, forms: tuple[str, str, str])` — стандартный pyшный паттерн:
```python
def pluralize_ru(n, forms):
    n = abs(n) % 100
    if 11 <= n <= 14:
        return forms[2]
    n %= 10
    if n == 1:
        return forms[0]
    if 2 <= n <= 4:
        return forms[1]
    return forms[2]
```

В `time()` использовать:
```python
hours_form = pluralize_ru(hours, ('час', 'часа', 'часов'))
min_form = pluralize_ru(min, ('минута', 'минуты', 'минут'))  # или сократить до 'мин.'
days_form = pluralize_ru(days, ('день', 'дня', 'дней'))
```

**Impact:** косметический. Фундаментально не ломает игровой опыт, просто корявые формы режут глаз.

**Effort:** S-M. Сама функция — 5 строк, но нужно подумать про сокращения (короткие "ч / мин." vs полные "часа / минуты"), про то, использовать ли pluralize в других местах (например, `working_hours` отображения), и проверить отсутствие регрессий.

**Сделано минимальным фиксом (05.05.2026, 0.2.1s):** выбран **вариант B** (сокращения, без pluralize). В `time(x)` несклоняемое полное слово `"час"` заменено на сокращение `"ч."` — теперь вывод единообразен для всех чисел: `"1 ч. 0 мин."`, `"2 ч. 30 мин."`, `"5 ч. 15 мин."`, `"21 ч. 45 мин."`. Точки сохранены (как у `"мин."` — единый стиль сокращений). Полный pluralize_ru с тремя формами (час/часа/часов) **не вводился** — добавляет сложность ради косметической задачи; если позже потребуется (например при подключении i18n) — отдельная задача. `format_timedelta` (countdown timers) уже был с краткими формами `г/мес/нед/д` без точек (как в варианте B), не трогался. Web JS `formatRemaining` (dashboard.html) использует те же сокращения — синхронизация с Python. Code changes: 1 строка в `functions_02.time()`. Existing 381 tests pass — никаких регрессий (тесты не проверяли точный текст "час" / "ч.", только формат "X N M N").

**Зависимость:** делать **после 2.10**, чтобы не правил `time()` дважды.

---

### 2.12. `status_bar()` показывает stale max_steps / total_bonus при смене дня `[M / S / done]`

**Найдено 2026-04-28.** Symptom: в первый запуск нового дня `status_bar` выводит некогерентный микс:

```
Steps 🏃: 0 / 2,296 (Bonus: Stamina + 0 / Equipment + 0 / Daily 0 / Level: 0. [🏃: 828, 56.40 %])
```

— `steps() = 0` (правильно после reset), но `max_steps = 2,296` и `total_bonus = 828` посчитаны с вчерашним `steps_today`.

**Диагноз:** `status_bar()` (`functions.py:54`) сначала пре-вычислял `total_bonus = total_bonus_steps()` и `max_steps = steps_today + total_bonus` на старом state, а потом в f-string первым слотом вызывал `steps()`, внутри которого `save_game_date_last_enter()` детектил новый день и сбрасывал `steps_today=0`. Из-за порядка evaluation Python (left-to-right в f-string), снапшоты `total_bonus` / `max_steps` остаются "до-reset", а индивидуальные `stamina_skill_bonus_def()`, `equipment_bonus_stamina_steps()` и т.д. вызываются после reset → возвращают 0. Результат — несогласованный вывод: max_steps из вчерашнего мира, бонусы по-нулям.

**Фикс 2.9** (steps_can_use в обеих ветках) этот случай не закрывал, потому что проблема не в логике `save_game_date_last_enter()`, а в том, что **`status_bar()` читает state до её вызова**.

**Сделано (2026-04-28):** в начало `status_bar()` добавлен явный вызов `save_game_date_last_enter()`. Теперь все последующие чтения (`total_bonus_steps()`, `steps_today`, individual bonus functions, `steps()`) работают с уже актуализированным состоянием. Вывод когерентен: `Steps 🏃: 0 / 0` после смены дня, до ввода `+`.

Корневая причина — module-level side effects + неявная зависимость функций от мутирующего глобального состояния. Полное решение придёт с задачами **1.1** (GameState) и **1.2** (убрать побочные эффекты импорта). Точечный фикс — defensive ordering.

### 2.13. Sheets locale corruption на float-полях `[H / S / done (0.2.3g, 07.05.2026)]`

**Найдено 2026-05-07.** Symptom: после прокачки Money_Saving (state.money стал дробным `2018.10`), web показывал `⚠️ Cloud sync failed at 14:03:13 — showing cached data` с ошибкой `float() argument must be a string or a real number, not 'tuple'`.

**Цепочка бага:**
1. С 0.2.2 `state.money: int → float` (для копеек после Bank operations).
2. После 4.20 (Money Saving, 0.2.3a) появились дробные значения (например `2018.10`).
3. `GameStateRepo.save` использовал `ws.update(rows)` без явного `value_input_option`. gspread default — `USER_ENTERED`, что заставляет Sheets интерпретировать значения по системной локали.
4. На локали с `,` как десятичным разделителем (ru-RU и т.п.) Sheets сохранял `2018.10` как `'2018,1'`.
5. На чтении `_rows_to_state_dict` пытался `json.loads('2018,1')` → fail → переходил к `ast.literal_eval('2018,1')` → возвращал **tuple `(2018, 1)`** (валидный Python literal!).
6. `from_dict` делал `float(d.get('money'))` → `float((2018, 1))` → `TypeError`.
7. Web падал на `try_reload_state`, показывал cached data + error message.

**Затронутые поля:** все float в `to_dict` — `money`, `bank_deposit_amount`, `bank_deposit_last_interest_ts`, `bank_loan_amount`, `bank_loan_last_interest_ts`, `steps_xp_bonus`, `timestamp_last_enter`, `energy_time_stamp` + `ts: float` в `steps_log`.

**Фикс (3 точки в `google_sheets_db.py`):**
1. `_state_dict_to_rows` — float-значения теперь конвертируются в строку через `repr()` (`'2018.1'` с точкой) перед отправкой gspread. Sheets хранит как text, без интерпретации.
2. `GameStateRepo.save` — добавлен `value_input_option=ValueInputOption.raw` (защита от парсинга по локали даже при будущих типах).
3. `StepsLogRepo.append` — переключён с `USER_ENTERED` на `RAW` (защита для `ts: float` в steps_log).

**Recovery текущей corrupted ячейки:** одна-shot скрипт прочитал `characteristic.csv` (где `money: 2018.1` сохранилось корректно, CSV не подвержен этой локали) и пересохранил state в Sheets с новым кодом. Sheets ячейка восстановлена.

**Тесты:** 1 тест в `test_sheets_repo.py` обновлён (`USER_ENTERED` → `RAW`). All 540 tests pass, mypy 0 issues.

**Урок:** при работе с external API (Sheets, любая БД с локалями) — НИКОГДА не полагаться на дефолтное поведение для числовых типов. Всегда сериализовать вручную в локалe-независимый формат (text с `.` или JSON) + явный input mode. Документация про это добавлена в CLAUDE.md (раздел Persistence layers).

---

## 3. Тесты

### 3.1. Настроить pytest + первые тесты `[H / M / done (30.04.2026)]`

**Сделано в рамках 1.1:**
- Pytest установлен (`requirements.txt`), сконфигурирован (`pytest.ini`).
- `tests/` содержит 14 файлов, **156 проходящих юнит-тестов** — покрывают все мигрированные модули.
- Закрыты пункты из исходного "минимального набора":
  - **save_roundtrip** — `tests/test_state.py` (11 тестов: round-trip default, with-data, datetime-fields, partial-dict, inventory, equipment).
  - **energy_charge_cap** — `tests/test_functions.py:test_energy_time_charge_clamps_to_max` + ещё 3 теста про регенерацию.
  - **level_up_allocates_skill_points** — `tests/test_level.py:test_update_level_grants_skill_points`.
- Не закрыто (мелкий полишинг):
  - `test_adventure_unlock` — counter unlocks (3+ counter открывает следующий walk). Сейчас проверяется через UI smoke в `test_adventure.py`, но прямой ассерт на разблокировку не написан.
  - `test_drop_deterministic` — детерминированный дроп с `random.seed(42)`. Сейчас в `test_drop.py` используется `monkeypatch.setattr('drop.randint', lambda a, b: ...)`, что эквивалентно по эффекту.

Импорт тестов всё ещё триггерит Google Sheets через `characteristics.py` (~2 сек). Это закроется задачей **1.2** (lazy initialization).

---

### 3.2. Починить `test_drop.py` + унифицировать симулятор с реальным `Drop_Item` (зонтичная) `[M / M / done (0.2.1f)]`

Первоначальная оценка "обернуть в `__main__`-guard, 10 минут" оказалась неполной. Анализ (24.04.2026) показал: симулятор — **старый fork** `drop.py` (другие проценты, другой набор типов предметов, другая структура rolls). Измерения им бесполезны для актуального баланса.

TASKS.md также писал про "`drop.py:167`" — **неточность**: функции `test_item_generation()` в `drop.py` нет, она только в `test_drop.py`.

Плюс параллельная проблема — **`drop_simulator.py`** (691 строка, не упоминалась в TASKS.md): тоже вызывает `random_thee_items_characteristics_item_stat()` на module-level (1 000 000 итераций). Никем не импортируется, по коду старая копия drop-логики без S/S+ грейдов — кандидат на удаление.

Плюс фундаментальная архитектурная проблема: `drop.py:14` вычисляет `luck_chr` при импорте → прокачка удачи в сессии не применяется до рестарта (перекрывается с задачами **2.3** и **1.2**) + невозможно параметризовать luck в симуляторе.

Разбивка на подзадачи ниже.

#### 3.2. Безопасность импортов + удаление dead-кода `[M / S / done]`

**Сделано (24.04.2026):**
- `test_drop.py` переименован в `drop_test_montecarlo.py` через `git mv` (история сохранена). Новое имя не попадает под pytest'овский паттерн `test_*.py` / `*_test.py`.
- Module-level вызовы в файле (`test_item_generation()` + `print(f"Luck: {luck_chr}")`, строки 167-168) обёрнуты в `if __name__ == "__main__":` — импорт файла больше не триггерит 60 000 итераций.
- `drop_simulator.py` удалён (691 строка старой копии drop-логики без S/S+ грейдов, никем не импортировался).
- `CLAUDE.md` обновлён: команда запуска симулятора, описание, module map (убрано упоминание `drop_simulator.py`).

Эффект: импорты безопасны, кодобаза чище на ~860 строк. Внутренняя копия `Drop_Item` в симуляторе пока сохраняется — это чинится в 3.2.2 после рефакторинга drop.py (3.2.1).

#### 3.2.1. `luck` как параметр `Drop_Item` (refactor drop.py) `[M / S / done (30.04.2026)]`

**Сделано в рамках 1.1 (Phase 4 commit 4):**
- Module-level `luck_chr = ...` в `drop.py` удалён.
- Вместо него — функция `current_luck(state)` (читает `state.gym.luck_skill + equipment_luck_bonus(state) + state.char_level.skill_luck`).
- Все методы `Drop_Item` принимают `state: GameState` и зовут `current_luck(state)` в момент дропа.
- Прокачка Luck в Gym теперь применяется на следующем дропе без рестарта.
- Закрыто часть задачи **2.3** (Adventure не видит прокачку), часть **1.2** (module-level side-effects).

**Тесты:** `tests/test_drop.py:12` (`current_luck` formula); ещё 11 тестов покрывают отдельные методы Drop_Item с явным state.

Подзадача **3.2.2** (симулятор на реальном Drop_Item) — теперь разблокирована и стала проще: `drop_test_montecarlo.py` уже использует ту же сигнатуру `state: GameState`, осталось только импортировать `Drop_Item` вместо локальной копии.

#### 3.2.2. Симулятор использует реальный `Drop_Item` `[L / S / done (0.2.1f)]`

**Сделано (04.05.2026):** `drop_test_montecarlo.py` переписан с использованием реального `Drop_Item` из `drop.py`:
- Удалена локальная fork-копия `Drop_Item` + `current_luck` + `drop_percent_*` constants (~110 строк).
- Импорт `from drop import Drop_Item`.
- Используется только `Drop_Item.one_item_random_grade(hard, state)` — без полного `item_collect` (вариант B). Это значит симулятор не печатает per-item и не аппендит в `state.inventory`.
- Добавлен `walk_20k` в список difficulties (было пропущено в старой fork-копии).
- Внешний цикл по `LUCK_VALUES = [0, 5, 10, 20, 30]` — `state.gym.luck_skill = luck_value` перед каждым прогоном.
- Прогон 5 luck × 7 difficulties × 10 000 итераций = 350 000 вызовов, время ~1.1 секунды на M1.
- Вывод — таблица `difficulty × grade` с процентами для каждого luck-значения.

**Эффект:** симулятор меряет **реальный** баланс игры. Данные пригодны для тюнинга `drop_percent_*` констант. Видна разница: walk_easy с luck=0 даёт 60% c-grade / 40% none; с luck=30 — 100% c-grade (никаких none). walk_30k остаётся самым тяжёлым (даже luck=30 даёт только 21.5% s+grade, 78.5% none).

**Примечание про inventory.append:** проблема не возникла — мы используем `one_item_random_grade` напрямую, не `item_collect`, поэтому `state.inventory` не мутируется в принципе.

---

## 4. Новые фичи (по убыванию "эффект / сложность")

### 4.1. Ручной ввод шагов из главного меню `[H / S / done]`

**Сделано:** команда `+` в главном меню запускает `steps_today_manual_entry()` из `functions.py:221`. Логика `max(текущее, введённое)` — случайный ввод меньшего значения не сбрасывает данные. Невалидный ввод (буквы, отрицательные числа) — тихая отмена без рекурсии. Файлы: `functions.py` (+ функция), `game.py` (+ импорт, пункт меню, обработчик).

После появления `steps_log` (4.14) функцию надо будет переписать на запись строки в Sheet с `source='manual'`.

---

### 4.2. Отчёт "пока тебя не было" при входе в игру `[H / S / done (21.05.2026, 0.2.5e)]`

**Реализация (21.05.2026, 0.2.5e, Variant B per design discussion — read Sheets `history`):**

1. **Новый модуль `report.py`** — pure helpers:
   - `INTERESTING_EVENT_TYPES` (frozenset) — 7 passive event types (work_done / skill_upgraded / adventure_done / drop / drop_auto_collected / drop_force_sold / level_up / new_day). Player actions (skill_alloc / bank_*) НЕ включены.
   - `build_away_report(since_ts)` — читает Sheets history через `HistoryLogRepo.since`, фильтрует interesting. Silent-fail если Sheets unavailable.
   - `format_report_cli(events, since_ts)` — colorama CLI block с рамкой.
   - `build_report_view(events, since_ts)` — pre-computed dict для web template.

2. **`HistoryLogRepo.since(ts)`** в `google_sheets_db.py` — full read через `get_values(value_render_option=UNFORMATTED)` (UNFORMATTED критично для precision — те же грабли что в 4.48.5.4 с last_modified).

3. **Runtime-only поля** в `state.GameState`: `startup_report: list[dict]` + `startup_report_since_ts: float` (НЕ сериализуются).

4. **`characteristics.py:init_game_state`** — capture `prior_ts = s.timestamp_last_enter` ДО перезаписи на `now`, потом после load + max-merge → `build_away_report(prior_ts)` → store в `s.startup_report`. Try/except — report не критичен.

5. **CLI** (`game.py:play()`) — перед main loop tick'ом если startup_report non-empty → print → clear.

6. **Web** (`_dashboard_context`) — context-key `away_report` через `_build_away_report_view(state)` (вызывает build_report_view + clear startup_report). Banner template в `_status_fragment.html` с azure border-left, header «🕒 Пока тебя не было», elapsed_label, items list.

**Тесты:** 38 новых — `test_report.py` (30: types coverage + format + helpers + build), `test_sheets_repo.py` (5: HistoryLogRepo.since edge cases), `test_web_main.py` (3: banner render / absent / cleared). 1095 passed total, mypy 0 issues (70 source files).

**Cost:** +1 Sheets API call (~500-700 ms) на init_game_state — для web one-time на uvicorn startup, для CLI один раз per session.

**Display trigger:** только если есть хотя бы 1 interesting event между prior_ts и now (per user choice). Пустой report не показывается — не загромождает UI при быстрых перезапусках.

---

### 4.3. Стрик-счётчик дней подряд `[H / S / rejected (13.05.2026 — daily_bonus уже выполняет роль streak-счётчика)]`

**Отклонено 13.05.2026** — функционал уже работает:

`state.steps.daily_bonus` инкрементируется в `functions.today_steps_to_yesterday_steps()` каждый день когда `yesterday >= 10000`, сбрасывается в 0 при пропуске. Это математически идентично streak-counter'у. Значение видно в `status_bar` строкой `Energy 🔋: ... (Bonus: ... / Daily 🔋: + N / ...)` — игрок может узнать свой стрик косвенно через это число.

**Что НЕ хватает (не критично):** семантической явности — игрок может не понимать что «Daily 🔋: +7» это именно «7 дней подряд». При желании можно мини-улучшить лейбл (добавить 🔥 emoji-маркер) — это 5 минут полировки, не отдельная задача.

**Если в будущем понадобится переоткрыть:**
- Реальный use case — 4.36 (Streak Freeze) или ачивки требующие decoupled-counter от daily_bonus (например если daily_bonus capнем для баланса).
- Longest streak record — фича для мотивации бить рекорд.
- Threat warning «до конца дня осталось 2,500 для стрика».

При этом нужна будет новая task: separate `state.streak` поле + migration из daily_bonus.

---

#### Legacy plan (для истории, не выполняется)

Счётчик "N дней подряд >= 10k шагов" (`state.steps.streak_days` — новое поле). В `status_bar` показать `🔥 7 дней подряд`. Это то, что реально мотивирует ходить каждый день.

**Без экспоненциальных бонусов** — задача 4.35 (Exponential Daily Bonus) отклонена 01.05.2026 как ломающая баланс. Стрик остаётся как чистый визуальный мотиватор. Если позже потребуется привязать к нему награду — мелкая (achievement / открытие предмета в Shop), точно не множитель к `steps_daily_bonus`.

**Связана с:** 4.36 (Streak Freeze — защита от случайного сброса).

---

### 4.4. Достижения (базовый список) `[merged into 4.62 — 15.05.2026]`

**Объединена с 4.44** в новую зонтичную **4.62 Triumphs / Достижения** (концепция Destiny 2 Triumphs). MVP-trophy-список из этой задачи (первый S+ drop, streaks 10k+, 100 приключений, 1М шагов, all adventures unlocked) переезжает в подзадачу **4.62.1 MVP catalog**. Хранение `achievements: list[str]` пересмотрено в **4.62.0 Infra** в пользу `state.triumphs: dict[str, dict]` (id → tier + unlocked_at). Номер 4.4 оставлен для traceability ссылок.

#### Legacy plan (для истории)

Счётчики уже есть в `char_characteristic` (adventure counters, steps_total_used). Добавить:
- первый S+ drop
- 5/10/30 дней подряд 10k+
- 100 приключений
- 1kk steps total
- все приключения разблокированы

Хранить в `achievements: list[str]` внутри GameState. Отдельное меню "Achievements".

---

### 4.5. Daily / weekly / monthly quests `[M / M / todo]`

Процедурно генерируемые задания на разных временных шкалах с фиксированным расписанием обновления:

| Тип | Период | Обновление |
|---|---|---|
| Daily | 1 день | каждый день в 00:00 |
| Weekly | 7 дней | каждый понедельник в 00:00 |
| Monthly | месяц | 1-го числа каждого месяца в 00:00 |

**Примеры:**
- Daily: "Пройди 2 walk_normal + одну тренировку Gym" → +50 $
- Weekly: "Пройди 50k шагов за неделю" → +500 $ или 1 предмет A-grade
- Monthly: "Прокачай 3 любых навыка" → 1 предмет S-grade или Streak Freeze

**Реализация:**
1. Поля `daily_quests: list[Quest]`, `weekly_quests: list[Quest]`, `monthly_quests: list[Quest]` в `char_characteristic`.
2. При старте каждого тика проверять, не прошло ли время обновления → если прошло, регенерить новые quests.
3. Quests генерируются процедурно из шаблонов с подбором сложности по уровню игрока.
4. Reward выдаётся при выполнении (счётчик за период), оставшиеся незавершённые quests **не переносятся**.
5. UI: пункт "Quests" в главном меню или отдельная локация.
6. Save в трёх форматах.

**Зависимость:** не блокирующая. Связана с 4.44 (Achievements / Goals — quests могут быть частью системы).

---

### 4.6. История действий (зонтичная: JSONL + Sheets sync) `[M / S / done (0.2.4, 08.05.2026)]`

Append-only лог значимых игровых событий. Даёт:
- Отладку багов («что было вечером»).
- Фундамент для 4.2 (Отчёт «пока тебя не было»), 4.3 (Стрик-счётчик), 4.4 (Достижения).
- Источник данных для графиков в Sheets (4.10).

**Дизайн (08.05.2026, обсуждение):**

#### События для логирования (вариант B — значимые)

| Категория | Типы событий |
|---|---|
| Сейв | `save`, `new_day` |
| Шаги | `steps_set` (с источника manual / web / api) |
| Работа | `work_start`, `work_done` |
| Спортзал | `skill_train_start`, `skill_upgraded` |
| Приключения | `adventure_start`, `adventure_done`, `drop` (если был) |
| Банк | `deposit`, `withdraw`, `take_loan`, `repay_loan` |
| Уровень | `level_up`, `skill_alloc` |
| Инвентарь | `item_bought`, `item_sold`, `item_equipped`, `item_unequipped` |

#### Архитектура хранения — local + Sheets sync

- **Local**: `history.jsonl` (рядом с `characteristic.csv`). Sync-on-event, append, никогда не fails.
- **Sheets**: отдельный лист `history`. Sync-on-event через `HistoryLogRepo.append()`. **Best-effort, fail-silent** — если Sheets недоступен, лог только локально, событие не теряется.
- Multi-device / dashboard / multi-user — через Sheets-копию.

#### Схема события (JSONL line)

```json
{
  "v": 1,
  "ts": 1746124425.5,
  "date": "2026-05-08",
  "time": "14:30:25",
  "user_id": "default",
  "game_version": "0.2.3g",
  "type": "work_done",
  "payload": {"salary": 40, "hours": 4, "vacancy": "watchman"}
}
```

- `v` — версия схемы события (защита на будущее, пока `1`).
- `ts` — Unix timestamp (float).
- `date` / `time` — для человеко-читаемой фильтрации (опционально, можно удалить если `ts` достаточно).
- `user_id` — для multi-user (4.53), пока `"default"`.
- `game_version` — текущая версия игры (`web/main.py:VERSION`). Полезно при отладке: понять, какие фичи были на момент события.
- `type` — discrete enum (`work_done`, `skill_upgraded`, etc.).
- `payload` — type-specific dict с произвольными полями.

#### Sheets layout (лист `history`)

| Column | Type | Note |
|---|---|---|
| `ts` | float | Unix timestamp |
| `datetime` | str | `"2026-05-08 14:30:25"` для UI |
| `user_id` | str | `"default"` пока single-user |
| `game_version` | str | `"0.2.3g"` |
| `event_type` | str | `"work_done"` |
| `payload_json` | str | `json.dumps(payload)` |

По аналогии с уже существующим `steps_log`. Создание листа — миграция через `migrate_sheets.py` (расширить).

#### Стиль вызова — explicit `log_event(...)`

В каждом mutation-сайте (work_check_done, skill_training_check_done, _take_loan, _repay_loan, etc.) явный вызов `history.log_event(type, **payload)`. Проще найти grep'ом, чем декораторы / event bus.

#### Реализация

1. Новый `history.py` с:
   - `log_event(event_type: str, **payload) -> None` — единая точка записи.
   - `_write_local(event_dict)` — append в `history.jsonl`.
   - `_write_sheets(event_dict)` — append через `HistoryLogRepo`. Try/except, log warning.
2. `google_sheets_db.HistoryLogRepo` (по аналогии с `StepsLogRepo`):
   - `append(event_dict)` → `ws.append_row([ts, datetime, user_id, game_version, event_type, payload_json], value_input_option=RAW)`.
   - `_ensure_sheet()` defensive (auto-create при отсутствии).
3. `migrate_sheets.py` расширить — добавить создание листа `history` если нет.
4. `.gitignore` — добавить `history.jsonl` (личные данные игрока).
5. Вызовы `log_event(...)` в ~15 mutation-сайтах.
6. Тесты — формат события, структура schema, sync mechanism (mock Sheets), fail-silent поведение.

#### Не делается в MVP (отдельные подзадачи ниже)

- Pruning / rotation лога (4.6.1).
- CLI команда «История» для просмотра последних N событий (4.6.2).
- Re-sync missed events на восстановление Sheets (4.6.3).

#### 4.6.1. Pruning / rotation `history.jsonl` `[L / S / todo]`

Когда `history.jsonl` начнёт расти заметно (десятки тысяч строк, медленный grep / большое потребление места) — нужна стратегия очистки. Варианты: rolling window (последние 90 дней), архивный лист `history_archive` в Sheets, compaction (агрегаты по дням). Решается при первой реальной потребности — аналогично `4.14.1` для steps_log.

#### 4.6.2. CLI команда отображения истории `[L / S / todo]`

Команда `h. История` в главном меню или подпункт в Меню (`m`). Показывает последние 20 событий из `history.jsonl` в человеко-читаемом виде:
```
[2026-05-08 14:30] 🏭 Watchman shift +40$ (4h)
[2026-05-08 14:25] 🏋 Stamina prokachana 18→19
[2026-05-08 14:20] 💳 Loan +500$ (rate 99%)
```

#### 4.6.3. Re-sync missed events после восстановления Sheets `[L / M / todo]`

Если Sheets был недоступен какое-то время — события записывались только локально. После восстановления — нужен механизм, который читает локальный лог и догоняет упущенные записи в Sheets. Можно реализовать через flag `synced_to_sheets: bool` в локальной записи или через отметку «last_synced_ts» где-то отдельно. Не блокирующее, делается когда станет реальной проблемой.

---

### 4.7. Shop (зонтичная — framework + каталог items) `[L / M / todo (M → L 21.05.2026 — нужен balance design прежде чем кодить)]`

**Объединена с 4.40** 14.05.2026 — Shop framework + расширенный каталог items под одну зонтичную, симметрично с 4.48 / 4.49 / 4.50. Раньше 4.7 была про инфру (заглушки в `shop.py`), 4.40 — про контент (каталог расходников/бустеров/etc). Концептуально это одна Shop-фича разбитая на этапы.

**Контекст:** `shop.py:280` (`shop_menu_equipment`) — заглушка. `shop.py:284` (`shop_menu_sell_items`) — тоже. Экономика сейчас однонаправленная: деньги идут только на Gym и шмотки из дропа. Магазин это сбалансировал бы.

**Связанные задачи (зависимости):**
- **4.58** Active buffs system — pre-requisite для 4.7.2 (бустеры). Вынесена в отдельную задачу 14.05.2026 как big-фича (state + display + tick + integration), независимая от Shop.
- 4.36 Streak Freeze, 4.26 Repair Kit, 4.37 Pets — связанные item-типы для 4.7.3 / 4.7.4.
- 1.6 Items as dataclass — желательная инфра-зависимость, но не блокер.

#### Подзадачи

##### 4.7.0. Framework: sell_items + equipment menu `[M / M / todo]`

Доделать заглушки в `shop.py`:
- `shop_menu_equipment` — выбор экипировки на покупку (помимо текущего clothes-стаба), preview / buy.
- `shop_menu_sell_items` — продажа предметов из инвентаря через Shop (альтернатива текущей `inventory.sold_item`).
- UI patterns (browse / preview / buy / sell) консистентно с inventory_menu и существующим shop UI.
- Тесты на новые UI flow.

##### 4.7.1. Каталог расходников (instant) `[M / S / todo (blocked by 4.7.0)]`

Простые items с мгновенным эффектом (не требуют active_buffs):
- Energy Drink (+50 эн).
- Vitamins (+10% к шагам сегодня — модификатор `state.steps.daily_bonus`).
- Energy Pack (+5 эн × 5 применений в инвентаре).

##### 4.7.2. Каталог бустеров (temporary buffs) `[M / M / todo (blocked by 4.7.0 + 4.58)]`

Items с временным эффектом (требуют active_buffs system из 4.58):
- Speed Boost (+50% Speed на 30 мин).
- Lucky Charm (+30% Luck на 1 час).
- Money Fever (×2 деньги на работе на 2 часа).
- XP Surge (+50% XP для Inspiration на 1 час).

##### 4.7.3. Стратегические items `[M / M / todo (blocked by 4.7.0)]`

- Streak Freeze (см. 4.36).
- Repair Kit (см. 4.26).
- Insurance — защита от потери дорогого предмета (требует обсуждения механики).

##### 4.7.4. Pet items `[L / S / todo (blocked by 4.7.0 + 4.37)]`

- Pet Egg, Pet Food. Зависят от 4.37 (Pets / Companion).

##### 4.7.5. Косметика (опционально) `[L / M / todo (blocked by 4.7.0)]`

Скины / визуалы. Опциональная фича для late-game.

**Реализация (общие принципы для всех подзадач):**
- Каждый item — структура: `name, category, price, effect, duration, description`.
- Save в трёх форматах (CSV / JSON / Sheets).
- Бустеры используют `active_buffs` из 4.58 — не дублировать timestamp / tick логику.

**Effort:** **M** — инкрементально по подзадачам. Каждая 4.7.X — отдельный коммит, можно делать по одной за итерацию.

---

### 4.8. Webhook-уведомления о крутых дропах `[L / S / todo (отложено 13.05.2026 — нет Telegram bot / Discord сервера для интеграции)]`

Функция `notify(event)` шлёт POST в Telegram/Discord webhook на S+ дроп, lvl up, новое достижение. URL в `.env`. 30 строк кода, сильно повышает вовлечённость.

**Отложено** до момента когда появится готовая внешняя инфраструктура для уведомлений (Telegram bot настроен через BotFather, или Discord-сервер создан, или другой channel). Технически — задача простая (S, hook в `history.log_event`, fire-and-forget threading, есть `httpx` в requirements). Когда возьмёмся — см. обсуждение 13.05.2026 в conversation history: Variant A (hook в log_event), threading.Thread fire-and-forget, поддержка Discord + Telegram + Generic, env vars `WEBHOOK_*` для конфига.

---

### 4.9. Мульти-сейв `[M / M / todo]`

Несколько персонажей в папке `saves/char_<name>.json`. Меню выбора при старте. После 1.1 это вопрос: добавить выбор имени сейва в `characteristics.py:load_data_from_google_sheet_or_csv()` и в `save_characteristic()`, плюс CLI-меню при старте перед загрузкой `game_state`.

---

### 4.10. Dashboard в Google Sheets `[L / M / todo]`

Уже есть интеграция с Sheets. Добавить отдельный лист `daily_stats`, куда пишется snapshot раз в день (шаги, энергия, уровень, деньги). В самой таблице — график средствами Sheets. Ноль нового UI-кода.

**⚠️ Частично замещается by 4.48.1 (2026-04-29):** web Dashboard (4.48.1) даст похожий UX в браузере. 4.10 остаётся как опциональный low-priority backup-визуализатор средствами самих Sheets.

---

### 4.11. Negative events / "налог на бездействие" `[L / S / todo]`

Если игрок не ходил 3 дня — маленькая потеря денег "за еду" + сброс стрика. Делает выбор "пройти 10k сегодня" более весомым. Риск: демотивация, нужно тестировать на себе.

---

### 4.12. Сезонные события `[L / L / todo]`

Временный бонус к дропу в течение 2 недель, уникальное приключение с эксклюзивной наградой. Требует инфраструктуру для активных модификаторов (1.1 + 4.5).

---

### 4.13. Google Apps Script + iOS Shortcut для автоматической отправки шагов `[L / M / todo (отложено 13.05.2026 — приоритет понижен H→L)]`

**⏸ Отложено (01.05.2026):** в текущей дорожной карте отказались от iPhone Shortcut в пользу прямого ввода через CLI / Web / API (4.48.2 `POST /api/steps`). Apps Script и Shortcut могут вернуться позже как альтернативный канал, если потребуется автономный фоновой синк без открытия игры.

Конвейер, который раз в час отправляет шаги с iPhone в Google Sheet без участия игры.

**Компоненты:**
1. Web App на Google Apps Script, привязанный к существующей таблице. Принимает POST `{user_id, steps, ts}`, пишет строку в лист `steps_log`. Выдаёт публичный URL (`anyone with the link`, но логику защиты от чужих запросов добавить проверкой `user_id` + секретного токена в POST).
2. iOS Shortcut на iPhone:
   - Читает `Health -> Steps -> Today`.
   - POST на URL Apps Script с JSON.
   - В начале — блок "если час между 02 и 08 — выход", чтобы не писать ночью.
3. iOS Automations:
   - Часовые триггеры 08:00–23:00 на запуск Shortcut'а (16 автоматизаций, "Run Immediately" = on).
   - Плюс иконка на Home Screen для ручного запуска (когда хочешь подтвердить свежие шаги немедленно).

**Блокируется 4.14** — endpoint должен писать в отдельный лист `steps_log`, а не в `game_state`.

**⚠️ Deprecated by 4.48.2 (2026-04-29):** после реализации FastAPI backend (4.48) iOS Shortcut будет POST'ить шаги напрямую в свой `/api/steps`, минуя Apps Script. Apps Script остаётся как **fallback** — если решим не реализовывать, или если 4.48 откладывается.

---

### 4.14. Разделить Google Sheets: `game_state` + `steps_log` `[H / S / done (01.05.2026)]`

**Сделано:** один лист Key/Value заменён на два специализированных листа.

**Структура (финальная):**
- `game_state` — переименован из `Sheet1`. Snapshot текущего GameState через flat-dict от `state.to_dict()`.
- `steps_log` — append-only лог замеров. Колонки: `ts` (Unix timestamp `float`) | `user_id` (string, дефолт `'alex'` из `config.DEFAULT_USER_ID`) | `steps` (int) | `source` (`'manual'` / `'auto'` / `'web'`).

**Технические решения (01.05.2026):**
- **`ts` как Unix timestamp**, не ISO-8601 — компактнее в Sheets, парсинг через `datetime.fromtimestamp()` тривиален. Форматирование в человекочитаемую дату — на UI-слое, не в логе.
- **API через классы**: `GameStateRepo` (save/load) и `StepsLogRepo` (append/for_day) в `google_sheets_db.py`.
- **Lazy singleton client** (`_get_client()`) — одна авторизация на весь процесс вместо ~0.5 сек на каждый save/load.
- **Auto-create `steps_log` листа** в `StepsLogRepo._ensure_sheet()` — защитный fallback если миграция не прошла. Удаление в задаче **4.14.2**.
- **Запись в `steps_log` — только при явном `s` (Save) или `q` (Save & Exit)**, не при каждом вводе `+N`. Промежуточные изменения теряются — для max-merge (4.15) важен только максимум за день. Это даёт offline-mode: ввёл шаги → сменил решение → выход без save → данные не уехали в Sheets.
- **Локальный CSV/JSON save идёт первым**, потом Sheets. Если Sheets падает — игра продолжается оффлайн с актуальными local saves.
- **iPhone Shortcut (4.13)** отложен — ввод теперь через CLI / Web / API (4.48.2 `POST /api/steps`).

**Новый файл:** `migrate_sheets.py` (idempotent миграционный скрипт):
- Переименовывает `Sheet1` → `game_state` если нужно.
- Создаёт `steps_log` с заголовком если нет.
- Запускается **вручную один раз**: `python migrate_sheets.py`.

**Изменения в коде:**
- `google_sheets_db.py` полностью переписан: классы `GameStateRepo` + `StepsLogRepo` + lazy `_get_client()` + pure helpers `_state_dict_to_rows` / `_rows_to_state_dict` / `_format_steps_entry`. Старые функции `save_char_characteristic_to_google_sheet` / `load_char_characteristic_from_google_sheet` удалены.
- `characteristics.py` — `init_game_state()` использует `GameStateRepo().load()` вместо удалённой функции.
- `game.py` — `_sync_to_cloud()` хелпер: local save (CSV/JSON) → `GameStateRepo().save(state.to_dict())` → `StepsLogRepo().append(...)`. `load_from_cloud` через `GameStateRepo().load()`.
- `config.py` — `GAME_STATE_SHEET_NAME = "game_state"`, `STEPS_LOG_SHEET_NAME = "steps_log"`, `DEFAULT_USER_ID = "alex"`.

**Тесты:** `tests/test_sheets_repo.py` — 21 тест (round-trip rows ↔ dict, format_steps_entry, GameStateRepo save/load с моком gspread, StepsLogRepo append/for_day с фильтрацией по user/date и malformed rows).

**Разблокирует:** 4.15 (max-merge стратегия), 4.48.2 (POST /api/steps).

#### 4.14.1. Pruning steps_log `[L / S / todo (отложено — реализовать при реальной потребности)]`

Лог append-only — за год набирается ~16 000 строк (один игрок, ввод раз в час 16 ч/день). Лимит Sheets — 10M ячеек, поэтому не критично, но в перспективе пригодится стратегия:
- Rolling window: оставить только последние N дней (e.g. 90).
- Архивный лист: `steps_log_archive` с старыми записями.
- Compaction: один-агрегат-в-день вместо per-измерение (теряем источник, но компактно).

Реализуется при первой реальной потребности (e.g. лог стал тормозить на чтении или приближается к лимиту).

**Статус (07.05.2026):** отложено. Сейчас лог небольшой (несколько сотен строк), чтение мгновенное, max-merge работает быстро. Возобновить когда:
- старт игры начнёт ощутимо тормозить из-за чтения `steps_log` (subjective: > 1 секунды на load), ИЛИ
- лог приблизится к 10k строк, ИЛИ
- появится multi-user support (4.53) — тогда лог раздуется быстрее × N игроков.

#### 4.14.2. Удалить auto-check `_ensure_sheet()` после миграции `[L / XS / todo (отложено — выполнить после миграции на втором ноутбуке)]`

Сейчас `StepsLogRepo._ensure_sheet()` создаёт лист если его нет — защитный fallback на случай, если кто-то клонирует код без запуска `migrate_sheets.py`. После того как миграция точно прошла на всех окружениях (laptop + VPS, когда появится), можно удалить эту ветку — `_worksheet()` будет просто бросать `WorksheetNotFound` и заставлять явно запустить миграцию.

**Статус (07.05.2026):** отложено. Сейчас актуальное окружение только один лэптоп. Удалять auto-check имеет смысл когда `python migrate_sheets.py` будет запущен на **всех** окружениях, где может быть запущена игра — в первую очередь на втором ноутбуке (когда появится / будет настроен). До тех пор `_ensure_sheet()` остаётся как страховка для свежего клона.

#### 4.14.3. Offline queue для steps_log `[L / S / todo (20.05.2026 — пересмотрен приоритет M → L; стабильный интернет, реальной потребности нет)]`

Сейчас при сетевом сбое во время `Save & Exit` — Sheets-вызов кидает ошибку наверх. CSV/JSON уже сохранены, но запись в `steps_log` потеряна. Для надёжности при offline-сценариях:
- Локальный JSON-файл `pending_steps_log.jsonl` с очередью записей.
- При неудаче `StepsLogRepo.append()` — добавить в очередь.
- При следующем успешном save — слить очередь в Sheets.

Не критично для single-player MVP. Делается, если оффлайн станет регулярным.

---

### 4.15. Merge-стратегия шагов: `max(все записи за сегодня)` `[H / S / done (01.05.2026)]`

**Сделано:** `apply_steps_log_max_merge(state)` в `characteristics.py` поднимает `state.steps.today` до максимума по записям лога за сегодня + пересчитывает `state.steps.can_use` если today изменился. Silent-fail при сетевой ошибке (steps_log недоступен — оставляем как есть). Вызывается:
- В `init_game_state()` после load — для CLI start.
- В `web.sync.try_reload_state()` после load — для web F5 / pull-to-refresh.

**Контекст:** до этого фикса 4.48.2 имела смущающий баг — web ввёл шаги 1500, переоткрыл страницу или CLI — и видел старое значение из `game_state` листа. Причина: `_apply_new_steps` пишет только в `steps_log`, не обновляя `game_state` snapshot. Без max-merge при load — никто не читал `steps_log`. Теперь любой канал ввода (CLI / Web / iPhone Shortcut) применяется немедленно при следующем старте/F5.

**Тесты:** `tests/test_steps_max_merge.py` — 6 тестов (raises today, doesn't lower, picks max from multiple, empty log no-op, silent fail on Sheets error, recomputes can_use with bonuses).

**Версия:** `0.2.0i`.

Когда игра спрашивает "сколько шагов сегодня", читает все строки `steps_log` с `date(ts) == today` и `user_id == self` и возвращает **максимум** по полю `steps`.

**Почему max:** Mi Fitness может отстать или дать 0 в момент синка. Ручной ввод всегда актуален (игрок смотрит на браслет прямо сейчас). Максимум = "самое свежее реальное значение, которое кто-либо видел".

**Нюанс:** поле `steps` в логе — это **абсолютное значение за день**, а не инкремент. Не суммируем, а берём max.

---

### 4.16. Удалить Fitness API `[H / S / done]`

**Сделано (2026-04-27).** Изначально задача была "deprecate после недели работы нового pipeline". Решено вырезать сейчас, поскольку Fitness API фактически не работал у пользователя (нет валидных credentials, при старте выводил шумные сообщения "Файл token.json не найден"), а ручной ввод (`+`, задача 4.1) уже работает.

**Удалено:**
- `api.py` (122 строки) — модуль Fitness API.
- `get_token_fitnes_api.py` (92 строки) — OAuth-flow для Google Fit.
- Функции `steps_today_update_manual()` (~80 строк) и `steps_today_update_manual_nocodeapi_old()` (~25 строк) из `functions.py`.
- Закомментированный `#print(steps_today_update_manual())` (`functions.py:399`).
- Импорты `from api import ...` и `from get_token_fitnes_api import ...` в `characteristics.py`, `functions.py`.
- Пункт меню `0` "Обновить кол-во шагов через API" в `game.py` (диспатч + текст).
- Зависимости из `requirements.txt`: `requests`, `google-auth`, `google-auth-oauthlib` (gspread не зависит от google-auth, использует oauth2client).
- Строки `.gitignore`: `token.json`, `fitness_api_credential.txt/.json`, `/fitness_api_credential_.txt`.

**Изменено:**
- `characteristics.py:steps_today()` — теперь возвращает `loaded_data_char_characteristic.get('steps_today', 0)` вместо вызова `api.steps_today_update()`. Сетевых запросов при импорте больше нет.
- `functions.py:save_game_date_last_enter()` — на смену даты теперь сбрасывает `char_characteristic['steps_today'] = 0` (раньше делал HTTP-запрос). Игрок вводит фактическое значение через `+`.
- `CLAUDE.md` — секции "Step-count integration (Google Fit)" заменена на "Step-count input"; убраны упоминания `api.py`, `get_token_fitnes_api.py`, `token.json`, `fitness_api_credential.json`; `requirements.txt` команды без `get_token_fitnes_api.py`.
- `docs/game_console.md` — раздел 5 переписан (одна секция 5.1 "Источник: ручной ввод" вместо двух Google Fit / manual); таблица команд главного меню без пункта `0`; раздел 1.2 без OAuth-credentials; раздел 6.1 без упоминания `api.py`; раздел 8 без строки про Fitness API.

**Будущее:** конвейер iPhone → Google Sheets через iOS Shortcut запланирован в задачах **4.13** + **4.14** + **4.15**. После их реализации `steps_today()` сможет читать из `steps_log` (отдельного листа Sheets); потребуется переписать функцию ещё раз.

---

### 4.17. PyInstaller: сборка `.app` для личного использования на Mac `[M / S / todo]`

Собрать консольную версию в `2Walks.app` для запуска двойным кликом из `/Applications`.

**Команда:** `pyinstaller --onefile --windowed --icon=icons/2walks.ico --name=2Walks game.py`

**Нюансы:**
- Credentials (`credentials/2walks_service_account.json`) включать в бандл через `--add-data`.
- Gatekeeper на Mac попросит "Open Anyway" при первом запуске — это ок для личного использования.
- На Apple Silicon: собирать на Apple Silicon Mac, чтобы не было Rosetta.
- Проверить, что относительные пути до `characteristic.csv`/`.txt`/`save.txt` не ломаются при запуске из `.app` (PyInstaller меняет CWD).

---

### 4.18. Offline/lite-сборка для раздачи друзьям `[L / M / todo]`

Стриппнутая версия без Google Sheets и Fitness API: локальный JSON-сейв, ручной ввод шагов, ничего в облако.

**Делать только когда:** появится реальный второй игрок, который сказал "хочу поиграть". Не на спекуляцию.

**Что вырезается:**
- `google_sheets_db.py` — убрать или заменить на no-op.
- `credentials/` — не бандлить.

Сборка: `pyinstaller --onefile --name=2Walks-Lite game.py` с `config.py`-флагом `OFFLINE_MODE=True`.

---

### 4.19. Pity system для дропа `[M / M / todo (blocked by 3.2.1)]`

Механика "подкручивания" шанса дропа после серии неудач. Известна как *pity system* / *bad luck protection* / *mercy mechanic* (термин из Genshin Impact и подобных).

**Идея:** если игрок несколько раз подряд прошёл walk_hard и ничего не выпало — на следующий раз шанс дропа вырастает. При успешном дропе счётчик сбрасывается.

**Design (согласовано 24.04.2026):**
- Счётчики **per-walk**: `pity_walk_easy_counter`, `pity_walk_normal_counter`, `pity_walk_hard_counter`, `pity_walk_15k_counter`, `pity_walk_20k_counter`, `pity_walk_25k_counter`, `pity_walk_30k_counter` в `char_characteristic` — отдельный счётчик на каждое приключение.
- При `item_collect()`:
  - Если дроп `None` → `pity_<walk>_counter += 1`
  - Если дроп не `None` → `pity_<walk>_counter = 0`
- Формула подкрутки: два уровня (обсудить при реализации)
  - **Soft pity** — начиная с N₀ каждый промах добавляет `+X%` к шансу
  - **Hard pity** — на N_max промахах дроп гарантирован
  - Числа N₀, N_max, X определяются дизайном; для начала можно взять консервативные значения (например, N₀=5, N_max=15, X=5%) и откалибровать через симулятор 3.2.2.

**Реализация:**
- `drop.py`: `Drop_Item.__init__(self, luck=0, pity=0)`. В `one_item_random_grade()` учитывать `self.pity` при вычислении порога (например, `threshold = drop_percent_gl + soft_pity_bonus(self.pity)`).
- `adventure.py`: передавать актуальный `pity_<walk>_counter` из `char_characteristic` при создании `Drop_Item`. После вызова `item_collect` — инкремент/reset.
- `characteristics.py`: добавить 7 новых полей в дефолтный словарь `char_characteristic` + в load/save-таблицы.
- `google_sheets_db.py` + CSV + JSON — типичная ловушка с сохранением новых полей в трёх форматах (см. предупреждение в CLAUDE.md). **Отложено до момента реализации pity** — когда доберёмся, разбираемся с save-слоями тогда.
- Симулятор 3.2.2: цикл с разными значениями pity, таблица "прирост шанса от pity".

**Почему blocked by 3.2.1:** pity требует передачи параметра в `Drop_Item.__init__`. В 3.2.1 мы как раз добавляем туда параметр `luck` — удобно сразу спроектировать сигнатуру с учётом будущего `pity`. Без 3.2.1 pity пришлось бы хачить через module-level переменные.

**Вне приоритета сейчас.** Сначала стабилизируем drop + luck (2.8 → 3.2 → 3.2.1 → 3.2.2). Pity — улучшение поверх рабочей основы, отдельной сессией.

---

### 4.20. Новый навык: Экономия денег / Money Saving (-1% к тратам) `[M / S / done (0.2.3a, 07.05.2026)]`

Навык для экономии денег. Каждый уровень снижает стоимость денежных трат на 1%. Применяется к Gym training + Shop purchases. НЕ применяется к Work salary (доход), Bank deposit/withdraw, Bank loan repay.

**Дизайн (07.05.2026):**
- Title: «Экономия денег», icon 🏷, internal field `money_saving: int = 0`.
- Формула — **линейная** `cost * (1 - skill/100)` (выбрана пользователем, несмотря на «риск 0»). На skill=100 цена = 0$ (бесплатно). При skill > 100 — clamp до 0 (нет «отрицательной цены»). diminishing returns / cap альтернативы отвергнуты ради простоты.
- Возвращаемый тип — `float`, всегда `round(..., 2)` (макс 2 знака после запятой).
- `state.money: float` (с 0.2.2) — копейки сохраняются и текут корректно.

**Реализация (07.05.2026):**

1. `state.GymSkills.money_saving: int = 0` — поле с round-trip.
2. `bonus.py:apply_money_saving(cost: float, state) -> float` — `round(max(0.0, cost * (1 - skill/100)), 2)`. Pure helper.
3. `actions.try_spend(...)` — сигнатура `money: float = 0.0` (поднята с int). state.money: float уже принимает.
4. `gym.py` — все 4 точки `cost['money']` обёрнуты в `apply_money_saving`:
   - `format_lvl_up_info` (display) — формат `:,.2f`.
   - `get_lvl_up_info` (display) — формат `:,.2f`.
   - `Skill_Training.check_requirements` — сравнение и сообщение о нехватке.
   - `Skill_Training.start_skill_training` — передача в `try_spend`.
5. `shop.py` — все 4 точки покупок (cheeseburger / coffee / 3 кед):
   - `_buy_item` сигнатура `cost: float`.
   - Display цен через `apply_money_saving(base, state)`, формат `:,.2f`.
   - Сообщения «Не хватает» с float-разницей.
6. `web/main.py:_build_gym_skills` и `_validate_and_apply_training` — передают через `apply_money_saving`. Сообщение о нехватке формат `:,.2f`.
7. `gym.py:_SKILL_DESCRIPTIONS['money_saving']` — title «Экономия денег».
8. `gym_menu skill_options` — пункт `'13'`.
9. `web._GYM_SKILL_DISPLAY['money_saving']` — icon 🏷, available=True.

**Тесты:** 8 в test_bonus.py (no skill / linear / fractional / round to 2 / skill 100 → 0 / skill 150 clamp / cost 0 / тип float), 4 в test_bank.py (skill в _SKILL_DESCRIPTIONS / _GYM_SKILL_DISPLAY, try_spend принимает float, _buy_item с дисконтом). 2 теста в test_state.py (expected_keys + 1 ключ). 2 теста в test_web_main.py (13 skills, 14 details). All 522 tests pass (510 + 12), mypy 0 issues.

**Версия:** `0.2.3a` (мини-фича в рамках 0.2.3).

**Что НЕ делалось:** применение к Bank operations (отвергнуто как exploit-prone), применение к Adventure money cost (там нет money cost).

#### 4.20.1. Аудит округления цен / денег по всему коду `[M / S / done (0.2.3b, 07.05.2026)]`

**Решение (07.05.2026):** Стратегия A — унифицировать **всё** на `:,.2f` через единый helper. Это гарантирует точность отображения копеек везде где они могут появиться.

**Реализация:**

1. Новый helper `functions_02.format_money(amount: float, decimals: int = 2) -> str` — plain text без `$` / colorama, единая точка форматирования. Default `:,.2f`.
2. `bank.py:_format_money` (раньше приватный) — заменён на alias `format_money` из `functions_02`. Семантика та же.
3. **Все display-точки** money / wallet / cost обёрнуты через `format_money(...)`:
   - `functions.py:status_bar` — Money line.
   - `gym.py` — header Money + 4 точки cost (format_lvl_up_info, get_lvl_up_info, check_requirements not enough message).
   - `shop.py` — `_money_line` (wallet) + 4 cost displays (cheeseburger / coffee / 3 кед) + покупка-success + «не хватает».
   - `adventure.py` — header Money.
   - `web/main.py` — сообщение о нехватке в `_validate_and_apply_training`.
   - `web/templates/_status_fragment.html` — Stats Money через Jinja-global `format_money` (зарегистрирован как `format_hours` ранее).
4. `bank.py` — продолжает использовать helper через alias (без regression).

**Перешли с `:,.0f` на `:,.2f`** — везде. Wallet displays теперь показывают `2,038.00 $` вместо `2,038 $` (единообразие важнее компактности; копейки могут появиться в любой момент после Bank-операций).

**Тесты:** 8 новых в `test_functions_02.py` (default 2 decimals / thousand separator / round / decimals=0 / negative / no-$ / int-input / typical game values). 1 существующий в `test_actions.py` обновлён под float-точность. All 530 tests pass (522 + 8), mypy 0 issues.

**Версия:** `0.2.3b` (follow-up к 0.2.3a / 4.20).

**Что НЕ делалось:** smart formatter с drop `.00` для целых (опция C из обсуждения) — отвергнуто ради консистентности; переход на разные locale separators (например `1 234,56` вместо `1,234.56`) — пока не нужно, делается через параметр в format_money если понадобится.

---

### 4.21. Разделить Speed на два навыка: Speed + Energy Regen `[M / M / done in 0.2.4i (13.05.2026)]`

Сейчас `speed_skill` влияет на:
1. Длительность активностей (Gym training, Work shifts, Adventure walks) — `speed_skill_equipment_and_level_bonus()` в `skill_bonus.py`.
2. Скорость регенерации энергии — тот же helper вызывается в `energy_time_charge()` (`functions.py`) для интервала 60 сек.

Это **связывает несвязанные механики**: игрок прокачал Speed для быстрых тренировок и невольно получил быстрый regen энергии. Хочется разделить на два независимых выбора.

**Целевая модель:**
- `speed_skill` — только длительность активностей (как сейчас, минус regen). Equipment с `characteristic='speed_skill'` И `state.char_level.skill_speed` продолжают работать тут (бонусы остаются).
- Новый `energy_regen_skill` — только скорость регенерации энергии. Берёт бонус **только** из Gym-скилла + новой CharLevel-allocation `skill_energy_regen`. Equipment **не влияет** в V1 (V2-задача).

#### Решения по дизайну (13.05.2026)

| Вопрос | Решение |
|---|---|
| Equipment `characteristic='speed_skill'` после разделения | Влияет ТОЛЬКО на длительность активностей (как и было). Не влияет на regen. |
| CharLevel `skill_speed` после разделения | Остаётся ТОЛЬКО для длительности. Прокачка не сбрасывается. |
| CharLevel `skill_energy_regen` (новый) | Включаем в эту задачу. Allocation menu расширяется 4 → 5 опций. |
| Migration Gym `energy_regen_skill` для existing saves | **β — start at 0**. Не копируем speed_skill. Игрок видит новый скилл с 0, прокачивает с нуля. Regen становится медленнее (interval 60 → ~52 сек для текущих игроков с Speed 14) пока не докачает. |
| Migration CharLevel `skill_energy_regen` | **β — start at 0**, не копируем skill_speed. Тоже прокачивается с нуля. |
| Position в Gym menu | Slot 3 (сразу после Energy Max). Все остальные сдвигаются +1 (4-16 → 5-17). 17 скиллов total. |
| Icon в web `_GYM_SKILL_DISPLAY` | 🔋⚡ (батарея + молния) — комбо для regen. |
| Equipment `characteristic='energy_regen'` тип дропа | **V2 — отдельная задача 4.57**, не делаем в этой. |
| Версия | **0.2.4i** |

#### Список изменений по файлам

**Code:**

1. **`state.py`**
   - `GymSkills.energy_regen_skill: int = 0` (новое поле).
   - `CharLevel.skill_energy_regen: int = 0` (новое поле).
   - `to_dict`: + `'energy_regen_skill'` + `'lvl_up_skill_energy_regen'`.
   - `from_dict`: `int(d.get('energy_regen_skill', 0))` + `int(d.get('lvl_up_skill_energy_regen', 0))`.
   - Legacy сейвы без полей → default 0 (β).

2. **`bonus.py`**
   - Новый helper: `energy_regen_interval(base_seconds: int, state: GameState) -> int`
     - Формула: `base - (base / 100) * (state.gym.energy_regen_skill + state.char_level.skill_energy_regen)`.
     - Pure. Equipment не учитывается (V2).

3. **`functions.py`**
   - `energy_time_charge()`: заменить `interval = speed_skill_equipment_and_level_bonus(60, state)` → `interval = energy_regen_interval(60, state)`.
   - `char_info` display: добавить строку «- Регенерация энергии: +N%».
   - Print с countdown (+ 1 эн. через: ...) → тоже использует `energy_regen_interval`.

4. **`web/main.py`**
   - `_dashboard_context`: `energy_interval_sec = energy_regen_interval(60, state)`.
   - `_GYM_SKILL_DISPLAY['energy_regen_skill']` — entry с иконкой 🔋⚡, position сразу после `energy_max_skill`.
   - `_SKILL_DISPLAY` (CharLevel allocation): добавить `'energy_regen'` entry для 5-й кнопки.

5. **`gym.py`**
   - `_SKILL_DESCRIPTIONS['energy_regen_skill']` — entry.
   - `gym_menu skill_options`: вставить `'3': ('energy_regen_skill', ...)`, сдвинуть существующие 3-16 на 4-17.

6. **`level.py`**
   - `CharLevel.menu_skill_point_allocation`: добавить 5-ю опцию «5. Регенерация энергии».
   - `lvl_up_skill_energy_regen` поле в распределении.

7. **`skill_training_data.py`** — НЕ требуется изменений (общая таблица `skill_training_table` подходит для нового скилла).

**Tests:**

| Файл | Изменения |
|---|---|
| `tests/test_state.py` | expected_keys: 61 → 63 (+ `energy_regen_skill` + `lvl_up_skill_energy_regen`). Round-trip тест. Legacy default тест. |
| `tests/test_bonus.py` | +5 тестов для `energy_regen_interval` (sanity, linear, edge cases). |
| `tests/test_functions.py` | `energy_time_charge` использует новый helper, не зависит от speed_skill. |
| `tests/test_web_main.py` | gym_skills order 16 → 17. CharLevel allocation skill_options 4 → 5. |
| `tests/test_level.py` (если есть) | menu_skill_point_allocation добавляет skill_energy_regen. |

**Docs:**

- `CLAUDE.md` — skill count 16 → 17. Описание разделения в bonus.py секции.
- `docs/game_console.md` — раздел 7 (energy regen): новая формула. Раздел про CharLevel allocation: 4 → 5 опций.
- `changelog.txt` — entry 0.2.4i.

#### Выпуск-нотис для игрока (в changelog)

> **Внимание:** в 0.2.4i `Speed` skill разделён на два: `Speed` (длительность активностей) и `Energy Regen` (скорость regen). Существующие сейвы получают `energy_regen_skill = 0` (нужно прокачать с нуля). Regen энергии становится медленнее пока новый скилл не прокачается. Скилл `Speed` остаётся как был — длительность тренировок / работ / приключений не изменилась.

---

---

### 4.22. Новые навыки: Energy Optimization per-activity (-1% к энергозатратам) `[M / M / done in 0.2.4j (13.05.2026)]`

Группа из **трёх навыков**, симметрично существующим `move_optimization_adventure / gym / work`. Каждый снижает стоимость энергии для своей категории активностей на 1% за уровень.

**Цель разбиения** — увеличить количество прокачиваемых навыков (стимул больше ходить), а не давать один универсальный мульти-эффект.

**Глобальная цель скиллов** — не просто «сэкономить энергию», а **разблокировать прогрессию**: дать игроку возможность прокачивать навыки в Спортзале / делать high-tier Adventures / запускать длинные Work shifts, когда базовая стоимость превышает текущий `energy_max`. Конкретный кейс: Stamina lvl 19 стоит 95 эн, а `energy_max` = 65. Без energy_optimization это полная блокировка.

#### Новые навыки

- `energy_optimization_adventure` — экономия энергии в Adventure (`adventure.py`).
- `energy_optimization_gym` — экономия энергии в Gym training (`gym.py`).
- `energy_optimization_work` — экономия энергии в Work shifts (`work.py`).

#### Дизайн-решения (13.05.2026, обсуждение)

| Вопрос | Решение |
|---|---|
| Формула | Линейная `-1% за уровень`, **clamp `max(1, int(adjusted))`** — никогда не бесплатно. |
| Сравнение с другими reduction-скиллами | Match с `move_optimization_*` / `money_saving` / `trader` — все используют `int(base × (1 − skill/100))`. Никаких diminishing/cap для consistency. |
| **Round behaviour** | `int()` truncate финальной стоимости = savings округляются ВВЕРХ. Например base=10, skill=1: cost=int(9.9)=9, saving=1 (0.1 округлено до 1). |
| **Application scope для Work** | На **TOTAL** (per_hour × hours), НЕ per-hour. Это убирает плато в low-base активностях (watchman 4 эн/ч: per-hour rounding давал бы saving=1 на skill 1-25, total approach даёт линейный saving). |
| Application scope для Gym / Adventure | На single transaction (base = total, нет batching). |
| **Min cost = 1** | `max(1, int(adjusted))` — игрок никогда не платит 0 энергии. Защита от skill=100 эксплоита. |
| Migration legacy сейвов | β-вариант — все 3 новых скилла начинают с 0. |
| Position в Gym menu | Сразу после `move_optimization_*` (поз. 9-11). 17 → **20 опций**. neatness/money trilogy/bank/inspiration/backpack сдвигаются 9-17 → 12-20. |
| Title (CLI + web) | «Экономия энергии в Adventure / Gym / Work». |
| Icon (web) | 🗺️⚡ / 🏋⚡ / 🏭⚡ — match с move_opt icons + молния. |
| Adventure architecture | **Отдельный helper** `apply_energy_optimization_adventure(adv_data, state)` мутирует `adv_data['energy']`. Вызывается в `Adventure.__init__` после `apply_move_optimization_adventure`. |
| Equipment characteristic | НЕТ. Match `move_optimization_*` pattern. |
| CharLevel allocation | НЕТ. Match `move_optimization_*` (CharLevel skill allocation остаётся 5 опций после 4.21). |
| Skill training cost | Общая `skill_training_table` (без отдельной таблицы для energy_opt). |
| Версия | **0.2.4j**. |

#### Implementation plan

**Code:**

1. **`state.py`** — 3 новых поля `GymSkills.energy_optimization_{adventure,gym,work}: int = 0` + round-trip flat-keys.

2. **`bonus.py`** — 3 helper'а:
   ```python
   def apply_energy_optimization_adventure(adv_data: dict, state) -> dict:
       adjusted = adv_data['energy'] * (1 - state.gym.energy_optimization_adventure / 100)
       adv_data['energy'] = max(1, int(adjusted))
       return adv_data

   def apply_energy_optimization_gym(energy: int, state) -> int:
       adjusted = energy * (1 - state.gym.energy_optimization_gym / 100)
       return max(1, int(adjusted))

   def apply_energy_optimization_work(energy: int, state) -> int:
       """Применяется к TOTAL energy (per_hour × hours), не per-hour."""
       adjusted = energy * (1 - state.gym.energy_optimization_work / 100)
       return max(1, int(adjusted))
   ```

3. **`adventure.py`** — в `Adventure.__init__` для каждого приключения после `apply_move_optimization_adventure`:
   ```python
   data = dict(adventure_data_table[name])
   data = apply_move_optimization_adventure(data, state)
   data = apply_energy_optimization_adventure(data, state)
   ```

4. **`gym.py`** — wrap `cost['energy']` в `apply_energy_optimization_gym(cost['energy'], state)`:
   - В `start_skill_training` перед `try_spend`.
   - В cost preview меню (display).

5. **`work.py`** — wrap `energy_per_hour × hours` через helper:
   - В `check_requirements`: `energy_cost = apply_energy_optimization_work(per_hour × hours, state)` перед `try_spend`.
   - В UI / hour_options: каждая опция показывает optimized total.
   - `max_hours_by_energy` — новый helper с loop (max 8 итераций) находит максимальное h, где optimized total ≤ state.energy. Без этого игрок видит конс ервативный cap и не понимает что может больше.

6. **`gym.py`** — `_SKILL_DESCRIPTIONS` + skill_options menu (положение 9-11, сдвиг 12-20 для остальных).

7. **`web/main.py`** — `_GYM_SKILL_DISPLAY` с тремя entries и иконками 🗺️⚡ / 🏋⚡ / 🏭⚡. `_build_hour_options` / `_build_work_vacancies` показывают optimized total.

**Tests:**

| Файл | Изменения |
|---|---|
| `tests/test_state.py` | expected_keys 63 → 66 (3 новых поля). |
| `tests/test_bonus.py` | +9 тестов (sanity / linear / clamp_min_1 / clamp_at_zero / Work total approach). |
| `tests/test_functions.py` | n/a (helpers не в functions.py). |
| `tests/test_work.py` | max_hours_by_energy с optimization (forwarder 65 эн, skill=50 → 4h вместо 2h). |
| `tests/test_adventure.py` | walk_30k base 70 → 56 при skill=20. |
| `tests/test_gym.py` | Gym training cost reduces with skill. |
| `tests/test_web_main.py` | gym order 17 → 20 keys, +3 details (18 → 21 total). |

**Docs:**

- `CLAUDE.md` — skill count 17 → 20. Описание apply_energy_optimization_* в bonus.py секции. Объяснение total-vs-per-hour для Work.
- `docs/game_console.md` — Gym menu 17 → 20 опций. Energy regen formula уже отдельно (4.21), добавить энергозатраты с energy_optimization.
- `changelog.txt` — entry 0.2.4j.

#### Analysis при практической прокачке (skill 0-20)

Для понимания UX в реальной игре. Все 4 работы в практическом диапазоне skill 0-20 показывают линейную экономию ~ nominal %:

| Работа | base/h | 8h @ skill=20 | Real saving |
|---|---|---|---|
| Watchman | 4 | 25 (vs 32 base) | 22% |
| Factory | 7 | 44 (vs 56) | 21% |
| Courier | 10 | 64 (vs 80) | 20% |
| Forwarder | 30 | 192 (vs 240) | 20% |

Adventure walk_30k base 70 эн → 56 эн при skill=20 (20% saving) — открывает доступ для игроков с energy_max < 70.

Gym training (top-tier base 95 эн) → 76 эн при skill=20.

#### Известное ограничение — chicken-and-egg

Прокачка `energy_optimization_gym` сама требует энергии из общего `skill_training_table`. При `energy_max=65` skill упирается в потолок ~lvl 15 (cost=int(80×0.85)=68 > 65 для lvl 16). Дальнейший progress требует параллельных каналов:

- `steps.daily_bonus` (+1 эн за каждые 10k+ шагов в день).
- Equipment с `characteristic='energy_max'` (random drop).
- `char_level.skill_energy_max` allocation (требует unallocated CharLevel points).

**Это намеренный design** — late-game требует grinding по нескольким направлениям, а не одной кнопки. Сам `energy_optimization` даёт значительный partial progress (открывает ~5-10 уровней прокачки) и стимулирует прокачивать его.

Дополнительные balance changes (cheaper progression для energy_optimization / base ENERGY_MAX 50 → 60 / buff CharLevel allocation +5 вместо +1) — **не делаем в этой задаче**. Если в будущем chicken-and-egg окажется блокирующим — обсудим отдельной задачей.

#### Effort

| Phase | Сложность |
|---|---|
| state.py — 3 поля + round-trip | S |
| bonus.py — 3 helper'а | S |
| adventure.py — extend init | S |
| gym.py — wrap cost + display | S |
| work.py — wrap total cost + max_hours helper + 4 UI places | M |
| gym.py — menu shift (17 → 20 опций) | M |
| Tests — ~12 новых | M |
| Docs — CLAUDE.md / docs / changelog | S |

**Total: M** — широкий объём, но мелкие изменения.

#### Зависимости

Не блокируется ничем. После 4.21 (Speed split в 0.2.4i) — отдельная задача без overlap.

---

### 4.23. Новый навык: Earnings Boost / Бонус к зарплате `[M / S / done (0.2.4a, 08.05.2026)]`

Симметричен Money Saving (4.20). Каждый уровень увеличивает зарплату на работе на 1%.

**Где применять:** `work.py:work_check_done()` при начислении `money += salary * hours`. Только Work — другие источники денег (продажа items в Shop) сюда не входят.

**Реализация:**
1. Ключ `earnings_boost_skill` в `char_characteristic`.
2. Запись в `skill_training_table` (или общая таблица).
3. Пункт в меню Gym.
4. Helper `earnings_boost_bonus(base_salary) -> int` в `bonus.py`.
5. Вызов в `work_check_done()`.
6. Save в трёх форматах.

**Баланс:** менее критичный, чем reduction-скиллы — линейный `+1%` за уровень даёт в худшем случае удвоение дохода на lvl=100. Можно оставить линейное без cap. Финальное решение — при реализации, после симуляции экономики.

**Зависимость:** не блокирующая. Логически делать вместе с 4.20 (Money Saving) или сразу после — они образуют пару экономических навыков.

---

### 4.24. Разделить Luck на Drop Chance + Item Quality (нужно обсудить) `[M / M / todo]`

**⚠️ Нужно обсудить — возможно отказаться от задачи.** Не очевидно, нужно ли разделение.

Сейчас единый `luck_skill` в `drop.py` влияет на три механики одновременно:
1. **Шанс дропа** — `randint(1, 100 - luck_chr)` для global gate (выпадет ли вообще что-то).
2. **Грейд дропа** — тот же `randint(1, 100 - luck_chr)` для grade-rolls (C / B / A / S / S+).
3. **Качество предмета** — `randint(20 + luck_chr, 100)` в `item_quality()`. Прокачка Luck повышает минимум качества → лучше прочность и цена продажи.

**Идея:** разделить на два навыка:
- `luck_skill` — только пункты 1 и 2 (drop chance + grade).
- `quality_skill` (новый) — только пункт 3 (минимальное качество).

**Pro:**
- Игроку больше контроля: можно билдить под "много дешёвых вещей" или "редкие качественные".
- +1 прокачиваемый навык — больше стимул ходить.

**Contra:**
- Усложняет понимание: два очень похожих по смыслу навыка.
- Quality сам по себе не даёт значимого преимущества без 4.25 (где он реально monetizes).
- Текущая интегрированность Luck — это фича, а не баг: один навык, понятный эффект.

**Решение:** обсудить позднее. Если решим делать — потребуется аккуратно мигрировать старые сейвы (скопировать `luck_skill` в `quality_skill` или начать с 0).

---

### 4.25. Новый навык: Grade Upgrade Chance (бонус к грейду дропа) `[M / S / todo]`

Каждый уровень даёт +1% шанса при дропе **апгрейднуть грейд предмета на одну ступень**: C → B, B → A, A → S, S → S+. Если грейд уже S+, апгрейда нет.

**Идея:** дополнение к Luck. Luck уже влияет на грейд через rolls, но имеет естественный потолок (S+ выпадает только из walk_25k/walk_30k). Этот навык открывает возможность получить S+ из walk_15k/walk_20k и выше.

**Реализация:**
1. Ключ `grade_upgrade_skill` в `char_characteristic`.
2. Запись в skill table.
3. Пункт в меню Gym.
4. В `drop.py:Drop_Item.item_collect()` или `one_item_random_grade()`: после определения базового грейда, прокинуть через `try_upgrade_grade(base_grade, lvl)` — функцию, которая с шансом `lvl%` возвращает следующий грейд.
5. Save в трёх форматах.

**Баланс:**
- Линейный `+1%` за уровень → на lvl=100 каждый дроп гарантированно апгрейдится. Слишком сильно.
- Cap (например, 30-40%) — разумнее.
- Diminishing returns — альтернатива.

**Hype-фактор:** дроп S+ из walk_easy на удачном проке — отличный момент для игрока. Стоит проектировать так, чтобы это случалось редко (1-3% даже на максимуме навыка), но возможность была.

**Зависимость:** не блокирующая. Логически делать **после 3.2.1** (luck → параметр Drop_Item) — эта механика тоже будет передаваться через тот же init.

---

### 4.26. Repair Skill — навык ремонта экипировки `[merged into 4.59.1 — 14.05.2026]`

**Объединена с 4.59** (Кузница / Blacksmith) 14.05.2026 — Repair стал подзадачей 4.59.1, реализуется через локацию «🔨 Кузница». Cost формула зафиксирована (1% = 1000 шагов + 100 $ + 10 эн), skill'ы экономии (steps/money/energy saving) — TBD при реализации. Номер 4.26 оставлен для traceability ссылок.

---

#### Legacy plan (для истории)

Игрок прокачивает навык, который позволяет восстанавливать прочность (`quality`) надетой экипировки за пройденные шаги. Полезно для S/S+ предметов — они дороги и редки, замена занимает много адвентюр.

**Идея механики (черновик):**
- Прокачка навыка на 10 уровней (например) даёт возможность восстановить +10% прочности **одного** предмета за ~10 000 пройденных шагов. Привязка к шагам, а не к энергии — отдельная "цена" в реальных шагах.
- На lvl=20 — +20% за 10к шагов. На lvl=50 — +50%. И т.д.
- Игрок выбирает в меню "Ремонт" → выбирает предмет → видит требование (X шагов) → подтверждает → шаги списываются с `steps_today`, `quality` предмета растёт.
- Альтернатива: ремонт идёт автоматически в фоне при каждой пройденной активности (как сейчас идёт wear).

**Где жить в коде:**
- Возможно отдельный модуль `repair.py` или метод в `inventory.py:Wear_Equipped_Items` (там уже есть логика wear — добавить inverse-операцию).
- Меню — либо в Inventory, либо отдельный пункт в главном меню.

**Открытые design-вопросы:**
1. Можно ли ремонтировать только надетое или вещи в инвентаре тоже?
2. Что происходит, если steps_today < требуемых шагов на ремонт? Накапливать прогресс или блокировать?
3. Сколько ремонтов одной вещи можно сделать? Бесконечно или есть cap "вещь может потерять max 100% и восстановить max 100% за всю жизнь"?
4. Нужна ли стоимость в деньгах (для Shop "запчасти")? Или только шаги?
5. Если предмет уже на 100% — ремонт ничего не делает / не доступен.
6. Прокачка только на S/S+ или работает на любые предметы? (Если на любые — игрок может ремонтировать дешёвый C-grade за те же 10к шагов, что неинтересно — нужен ограничитель типа "только grade A+".)

**Зависимости:**
- Не блокирующая, но связана с 1.6 (Items as dataclass) — repair-логика проще, если у предмета есть метод `repair(amount)`.
- Связана с 4.7 (Доделать Shop) — если будут "запчасти" как покупаемый ресурс.

---

### 4.27. Новый навык: Обучение / Inspiration (+1% XP) `[M / S / done (0.2.3, 07.05.2026)]`

Ускоряет рост уровня персонажа (`char_level`), не затрагивая шаги, доступные для активностей. Каждый уровень навыка даёт +1% к получаемому XP за каждый потраченный шаг (forward-only multiplier — применяется только к будущим тратам, не пересчитывает накопленные).

**Дизайн (07.05.2026, обсуждение перед реализацией):**
- Title в UI — «Обучение» (русский, не «Inspiration»). Internal field name — `inspiration` (без `_skill` суффикса для краткости).
- Без cap — линейный +1%/level бесконечно.
- **Forward-only**, не retroactive: накопленные `total_used` не пересчитываются при апгрейде. Reasoning — даёт игроку чистый стратегический выбор (вкладывать сейчас в Inspiration или нет, без post-hoc эксплоитов).
- Иконка 📚.

**Реализация (07.05.2026):**

1. `state.StepsState.xp_bonus: float = 0.0` — accumulator для накопленного бонуса. Round-trip flat-key `steps_xp_bonus`. Старые сейвы → 0.0 (back-compat, поведение неизменно при `inspiration=0`).
2. `state.GymSkills.inspiration: int = 0` — новый skill. Round-trip + дефолты.
3. `actions.py:try_spend()` — после `state.steps.total_used += steps`: `if state.gym.inspiration > 0: state.steps.xp_bonus += steps * inspiration / 100.0`. Хранится как float чтобы не терять копейки на маленьких тратах. Не добавляется при failed spend.
4. `level.py:CharLevel`:
   - Новый `_effective_xp() -> int` = `total_used + int(xp_bonus)`.
   - `calculate_level_from_total_used_steps` и `progress_to_next_level` теперь используют `_effective_xp()`.
   - `total_used_steps` (property) НЕ изменён — используется для отображения «total used» в status_bar (показывает реальные шаги, не виртуальный XP).
5. `gym.py:_SKILL_DESCRIPTIONS['inspiration']` — title «Обучение», описание упоминает forward-only.
6. `gym.py:gym_menu skill_options` — пункт `'12'`. Стоимость прокачки шарится из общей `skill_training_table`.
7. `web/main.py:_GYM_SKILL_DISPLAY['inspiration']` — icon 📚, available=True.

**Тесты:** 5 в `test_actions.py` (try_spend без bonus / с bonus / accumulate / fractional / not on failure), 4 в `test_level.py` (effective_xp без bonus / +int(bonus) / level использует bonus / progress использует bonus), 2 в `test_bank.py` (skill в _SKILL_DESCRIPTIONS / _GYM_SKILL_DISPLAY). `test_state.py` обновлён: expected_keys + 2 (`steps_xp_bonus`, `inspiration`). `test_web_main.py` обновлён: 12 навыков, 13 details. All 510 tests pass (499 + 11), mypy 0 issues.

**Версия:** `0.2.3` (новая mini-feature вне зонтичной 4.49).

**Что НЕ делалось:** cap (если поздно станет имба — затюним), retroactive multiplier (намеренно forward-only), display xp_bonus в UI отдельно (кумулятивная цифра не показывается, только эффект через level).

---

### 4.28. Новый навык: Trader / Торговец (+1% к цене продажи) `[M / S / done in 0.2.4h (12.05.2026)]`

Третья нога экономической трилогии: 4.20 (Money Saving — на тратах), 4.23 (Earnings Boost — на работе), 4.28 (Trader — на продаже инвентаря). Каждый уровень даёт +1% к цене продажи всех предметов (включая еду / экипировку из Adventure / Shop-покупки).

**Реализовано в 0.2.4h** (см. changelog). Применяется во всех 4 точках продажи через единый helper `bonus.apply_trader(price, state) -> float`. Линейная без cap (x2 на skill=100). Position 11 в Gym menu (money trilogy: money_saving / earnings_boost / trader).

---

### 4.29. Новый навык: Insight — видимость информации о дропе `[M / M / rejected (12.05.2026)]`

**Отменено 12.05.2026:** не вписывается в концепцию (gated information за skill — слишком RPG-механика для walk-driven игры). Вместо этого — показ %-вероятностей дропа сразу в Adventure menu с учётом Luck (см. **новую задачу ниже**).

---

### 4.29 (legacy description, для истории)

Сохраняю старое описание для контекста:

В отличие от других навыков, Insight открывает **информацию**, а не даёт количественный бонус. Сейчас в меню Adventure написано просто "Награда: A-Grade, S-Grade, S+Grade" — без точных процентов выпадения.

**Идея:** на старте игрок видит только базовое описание ("что может выпасть"). По мере прокачки Insight — раскрываются всё более детальные параметры:
- lvl 1-3: видны проценты по грейдам
- lvl 4-6: видны проценты по типам предметов (ring/necklace/...)
- lvl 7-9: виден диапазон quality (например "20-100")
- lvl 10+: показывается влияние Luck на текущие шансы

Похоже на "perception" / "appraisal" в классических RPG.

**Где применять:**
- `adventure.py:adventure_menu()` — расширить рендеринг описания.
- `drop.py:Drop_Item.item_collect()` — после дропа можно показывать дополнительный спойлер: "Этот предмет был на грани S+, повезло на B".
- `inventory.py` / `equipment.py` — детальная статистика на надетых предметах (при высоком lvl).

**Реализация:**
1. Ключ `insight_skill` в `char_characteristic`.
2. Запись в skill table.
3. Пункт в меню Gym.
4. Helper `insight_level()` для проверки доступности информации в каждом блоке UI.
5. Save в трёх форматах.

**Сложность:** не в коде самой механики (тривиальная), а в **UI-дизайне** — продумать, какие куски информации показывать на каком уровне. Нужно сначала задать таблицу `INSIGHT_TIERS = {1: ['grade_percents'], 4: ['type_percents'], 7: ['quality_range'], 10: ['luck_breakdown']}` или подобную.

**Зависимость:** не блокирующая.

---

### 4.30. Идея: Adventure Mastery — бонус от количества прохождений `[M / M / todo (нужно обсудить)]`

**⚠️ Нужно обсудить детали баланса и формулу.**

Не классический навык (через Gym), а **динамический бонус**, который зависит от количества раз, которое игрок прошёл данную прогулку. Чем больше пройдено walk_easy — тем эффективнее последующие прохождения (повышение шанса дропа / снижение требований / etc.).

**Идея механики:**
- Базовая формула: `+0.1%` к шансу дропа за каждое прохождение, capped (например, +20% макс).
- Привязка к существующим счётчикам `adventure_walk_*_counter` — данные уже есть.
- Mastery считается отдельно для каждой прогулки: walk_easy mastery влияет только на walk_easy.

**Зачем:** поощряет повторное прохождение уже разблокированных приключений, а не только переход к более высоким. Сейчас игрок проходит walk_easy 3 раза → переключается на walk_normal → walk_easy забыт. С mastery — есть смысл возвращаться (или специально гриндить).

**Открытые вопросы:**
1. **Что именно даёт mastery?** Шанс дропа / качество / quantity / больше/меньше шагов на прогулку / комбинация?
2. **Формула:** линейная с cap, log, диминишинг? Cap-значение?
3. **Прогулка вычерпывает себя?** Например, 100 прохождений walk_easy = mastery_max — после этого новые прохождения ничего не добавляют. Пушит игрока к walk_normal.
4. **Видимость:** игрок должен видеть свой mastery-уровень для каждой прогулки в Adventure меню?
5. **Сбрасывается ли при reincarnation (4.33)** или сохраняется?

**Похоже на:** "expertise" / "weapon mastery" из World of Warcraft, "skill ranks" из Disco Elysium.

**Зависимость:** не блокирующая, но решения по балансу должны быть согласованы с 4.19 (Pity) — обе механики "делают повторение интереснее".

---

### 4.31. Идея: Collector — бонус за разнообразие инвентаря `[M / L / todo (нужно обсудить, концепция нравится)]`

**⚠️ Нужно обсудить и проработать концепцию.**

Пассивный бонус за обладание уникальными предметами в инвентаре или экипировке. Чем разнообразнее коллекция — тем выше бонусы. Поощряет НЕ продавать всё подряд, а собирать.

**Базовая идея (минимум):**
- За каждый тип предмета (helmet/necklace/ring/t-shirt/shoes), которым обладает игрок хотя бы в одном экземпляре → +1% к одной из характеристик (например, Stamina).
- Прокачивая `collector_skill` — увеличивается бонус за каждый тип (lvl 1: +1% за тип, lvl 5: +5% за тип).

**Расширенная идея (нужно обсудить):**
Ввести **локации** для приключений — несколько географических зон, в каждой свой пул предметов с уникальными именами/визуалом:
- Лесная зона: предметы "Лесной венок", "Дубовый кулон", "Шишечный амулет".
- Горная зона: "Каменный шлем", "Кристалл", "Плащ альпиниста".
- Городская зона: "Кепка", "Цепь", "Кроссовки".
- (или другие тематики — пустыня, побережье и т.п.)

В каждой зоне свои walk_easy/normal/hard/15k/.../30k. Уникальные имена с одинаковыми механиками.

Если игрок собирает **полную коллекцию из одной зоны** (по одному предмету каждого типа) — получает значимый бонус (например, +20% к Stamina и +10% Speed). Это даёт **долгосрочную цель** и чёткий путь развития.

**Открытые вопросы:**
1. **Сколько зон?** 3 / 5 / 10? Каждая требует контента.
2. **Как игрок переключается между зонами?** Меню локаций? Привязка к шагам? Случайный выбор?
3. **Бонус за полный сет** — фиксированный или зависит от грейда предметов в коллекции?
4. **Что с дублями?** Если 2 ring из лесной зоны — бонус один или два?
5. **Кросс-зонные комбинации** — есть ли мета-бонус "собрал по 1 предмету из всех зон"?
6. **Совместимость с Equipment:** надетый предмет считается в коллекции, или нужно держать "заначку" дополнительных?

**Технически:** требует добавить в `Drop_Item` поле `region`, переписать `adventure_data.py` под зоны, добавить новое меню "Регионы" перед выбором walk'а.

**Effort: L** — это не одна задача, это новая большая фича (возможно несколько связанных задач).

**Зависимость:** связана с **1.6** (Items as dataclass — нужны расширяемые поля типа `region`) и **4.4** (Achievements — коллекция = ачивка).

---

### 4.32. Идея: Tavern Rest / Patience — бонусная энергия за idle-время в Home `[L / M / todo (отложено 14.05.2026 — хорошая идея, реализация позже)]`

**Обсуждение 14.05.2026:** концепция нравится, но реализация пока не нужна. Рекомендованный paths при возврате к задаче — **объединить с 4.39 Meditation** в единую rest-систему (pool+spend pattern): Tavern копит `state.rest_buffer` пассивно, Meditation тратит буфер с выбором эффекта. Это убирает exploit-cycle Meditation и даёт целостную фичу. Variant 5 — расширить до полной Recovery-системы в Home location (наполняет также stub-локацию из 4.42). При возврате — см. полное обсуждение V1-V5 в conversation history 14.05.2026.

**⚠️ Нужно обсудить детали.** Пользователю нравится концепция, проблема — текущая дороговизна энергии для high-lvl скиллов (например, Stamina lvl 19 требует 95 энергии, восстановление с lvl=0 ≈ 1.5 часа).

**Аналог из других игр:** WoW Rested XP — персонаж в таверне накапливает бонусный XP, который применяется при следующем выполнении активностей. Здесь — то же самое, но для энергии.

**Базовая идея:**
- Когда персонаж находится в локации **Home** (`char_characteristic['loc'] == 'home'`) и **ничего не делает** (нет активной тренировки, работы, приключения) — копится бонус.
- Бонус применяется как мгновенное пополнение энергии при следующем входе в активность ИЛИ как накопленный множитель к regen.
- Прокачка `patience_skill` увеличивает скорость накопления и/или максимальный потолок.

**Альтернативная идея:**
- Игрок не появляется в игре N часов → при заходе видит "За время отсутствия накоплено 50 энергии".
- Привязка к `timestamp_last_enter` (есть в `char_characteristic`).
- Прокачка увеличивает rate накопления (например, lvl 0: 0.5 эн/час offline, lvl 10: 1.5 эн/час, lvl 50: 5 эн/час).
- Cap (например, max 200 накопленных), чтобы не было "вернулся через месяц = бесконечная энергия".

**Зачем нужно:** на текущем этапе игры энергия — главный bottleneck. Stamina lvl 19 стоит 95 энергии — это 1.5+ часа базового regen. Этот навык отчасти решает проблему "long sessions".

**Открытые вопросы:**
1. **Idle vs Offline:** копится только когда игра запущена в Home, или работает и оффлайн (через timestamp)?
2. **Что копится — энергия напрямую или "буфер"** (например, накопленный буфер расходуется при тратах вместо обычной энергии)?
3. **Может ли превышать `energy_max`?** Если да — насколько?
4. **Cap по времени** (макс 24 часа idle учитываются) или абсолютный (макс 100 эн в буфере)?
5. **Visual:** должен быть отдельный индикатор в `status_bar` ("Rest: 47 эн").

**Зависимость:** не блокирующая. Связана с 2.2.3 (sync energy stamp при тратах — отложено по 1.1).

---

### 4.33. Идея: Reincarnation / Prestige — сброс прогресса с бонусом `[L / L / todo (нужно обсудить)]`

**⚠️ Нужно обсудить — большая фича, требует тщательного дизайна.**

Стандартный паттерн idle-RPG: после достижения определённого порога игрок может **сбросить весь прогресс**, чтобы получить **постоянный мета-бонус**, который применяется во всех будущих "жизнях". Цикл повторяется.

**Базовая идея:**
- При достижении, например, `char_level >= 30` или `steps_total_used >= 10kk` — открывается возможность реинкарнации.
- При нажатии — сброс всего: `steps_today = 0`, `money = 0`, инвентарь очищен, все skill_* = 0, char_level = 0.
- Сохраняется только: `prestige_level += 1` + накопленные мета-бонусы.

**Какой мета-бонус давать (центральный design-вопрос):**
- **Variant A — multiplier:** "+10% ко всему" за каждую реинкарнацию. Простой, понятный, экспоненциально ломает баланс на 10-й итерации.
- **Variant B — очки престижа:** реинкарнация даёт N очков → игрок тратит их в "Зале Славы" на постоянные бонусы (увеличить energy_max, ускорить Adventure, открыть новый skill, etc.). Гибче, требует UI.
- **Variant C — открытие контента:** каждая реинкарнация открывает новую локацию / приключение / тип предмета, которые недоступны в первой жизни. Создаёт ощущение "новая глава".
- **Variant D — комбинация B+C.**

**Открытые вопросы:**
1. **Когда становится доступной?** Уровень / сумма шагов / время игры / комбинация?
2. **Что именно сохраняется?** Обычно — Achievements, possibly best records.
3. **Сколько реинкарнаций возможно?** Бесконечно или cap?
4. **UI:** отдельная локация "Алтарь" / меню в Home / спец-команда?
5. **Можно ли отменить?** (Безусловно нет — иначе бессмысленно.)
6. **Как это согласуется с Google Sheets save?** Backup перед prestige?

**Зачем игроку:** даёт долгосрочную горизонтальную прогрессию ("я реинкарнировал 5 раз!") поверх вертикальной (уровень внутри одной жизни). Стандарт жанра — Antimatter Dimensions, Trimps, Crusaders of the Lost Idols.

**Effort: L** — большая фича. Нужен UI, новая логика сохранения, тестирование баланса.

**Зависимость:** разблокировано после 1.1. Реализация: `actions.py:reincarnate(state)` — вызывает `GameState.default_new_game()` для тех полей, что сбрасываются, и сохраняет `prestige_level` + `meta_bonuses`. Чистый перезапуск GameState с whitelist'ом сохраняемых полей.

---

### 4.34. Прогресс-бар разблокировки приключений (вместо порога) `[L / S / todo]`

Сейчас walk_15k разблокируется после 3 прохождений walk_hard — резкий threshold. **Идея:** показывать **процентный прогресс** к разблокировке.

Пример:
```
- walk_15k: 2/3 прохождений walk_hard. (Прогресс: 67%)
```

**Реализация:** в `adventure.py:adventure_menu()` для каждой неразблокированной прогулки рассчитать процент по `adventure_walk_<prev>_counter / 3`. Никаких изменений в логике разблокировки — только UI.

**Effort: S** — 10-15 строк правки.

---

### 4.35. Exponential Daily Bonus + Streak Counter `[H / M / rejected (01.05.2026)]`

**Отклонено.** Идея была в экспоненциальном множителе к Daily Bonus за длинный стрик (тиры 1/7/30/100/365 дней → +5%/+25%/+100%/+500%/+2000%).

**Причина отказа:** ломает баланс игры. На длинном стрике (100+ дней) множитель `+500%` к и без того накопленному `steps_daily_bonus` (растёт +1 за каждый 10k+ день) даёт каскадный эффект — `steps_can_use` начинает превышать реальные шаги в разы, тренировки/работа становятся бесплатными. Игра превращается в idle-награду за факт удержания стрика, а не за реальную ходьбу.

Текущая линейная логика (`steps_daily_bonus += 1` за каждый 10k+ день) сохраняется как есть.

**Что сохраняется отдельно:**
- **4.3 (Streak Counter)** — остаётся живой задачей. Стрик как чистый счётчик без экспоненциальных бонусов: показывать "🔥 12 дней подряд" в status_bar, использовать как мотивационный визуальный элемент. Возможные неэкспоненциальные бонусы — отдельным дизайн-вопросом (например, achievement за 30 дней, открытие предмета в Shop за 100 дней).
- **4.36 (Streak Freeze)** — остаётся в обсуждении, имеет смысл и без 4.35.

---

### 4.36. Идея: Streak Freeze — заморозка стрика через Shop `[M / S / todo (нужно обсудить)]`

**⚠️ Идея, требует обсуждения.** Пользователь подтвердил: после потери стрика мотивация ходить пропадает. Streak Freeze — экономический способ защиты.

**Базовая идея:**
- Расходник в Shop. Стоимость: дорогая (например, 500 $).
- В инвентаре до использования.
- При смене дня, если `steps_yesterday < 10000` И есть Streak Freeze → стрик сохраняется, 1 Freeze тратится.

**Открытые вопросы:**
1. **Auto vs Manual** — автоматически списывать или предлагать выбор? Я бы делал manual.
2. **Cap на количество** в инвентаре / в месяц — чтобы не сделать стрик неуязвимым.
3. **Цена** — статика или динамическая (растёт после каждой покупки в стрике)?
4. **Ограниченность по времени** — Freeze "истекает" через N дней или хранится вечно?
5. **Уведомление при срабатывании** — "Streak Freeze потрачен. Стрик сохранён: 47 дней".
6. **Несколько уровней** (Bronze / Silver / Gold для разных длительностей)?

**Зависимость:** **blocked by 4.35** (Streak Counter). Связана с 4.7 (Shop), 4.40 (Shop catalog).

---

### 4.37. Идея: Pets / Companion — питомцы для Adventure `[L / L / todo (нужно обсудить; приоритет понижен H→L 13.05.2026)]`

**⚠️ Идея, требует обсуждения.**

Питомец сопровождает в Adventure. Эмоциональная привязка → больше мотивации играть. Получает свой опыт, прокачивается.

**Базовая идея:**
- Несколько типов с разными бонусами:
  - 🐕 Собака — +10% Stamina
  - 🐈 Кот — +5% Luck
  - 🦅 Сокол — +1 предмет за прогулку (раз в день)
  - 🐢 Черепаха — −20% энергозатрат на adventure
- Получение: Shop / random drop / quest reward.
- Прокачка: кормить шагами / энергией.
- Один активный, остальные в "питомнике".

**Открытые вопросы:**
1. **Сколько типов** в первой версии? (3-5)
2. **Способы получения** — баланс между Shop / drop / quest.
3. **Прокачка** за шаги (стимул ходить) vs за время (idle-friendly).
4. **Смена активного питомца** — когда доступна?
5. **Кормление** — расходный ресурс или просто tap?
6. **Эмоциональная механика** — голод / грусть, если не кормить (или это too much guilt)?

**Effort: L** — новая система, UI (питомник), новые предметы в Shop.

**Зависимость:** связана с 1.1, 1.6, 4.7 (Shop), 4.40, 4.46 (питомец как компаньон в Story Mode).

---

### 4.38. Crafting / Forging — крафт предметов из дублей `[merged into 4.59.2 — 14.05.2026]`

**Объединена с 4.59** (Кузница / Blacksmith) 14.05.2026 — Crafting стал подзадачей 4.59.2, реализуется через локацию «🔨 Кузница». Recipe зафиксирован (Variant A — строгая идентичность 2 одинаковых grade → 1 next grade, 100% success rate, quality = avg). Номер 4.38 оставлен для traceability ссылок.

---

#### Legacy plan (для истории)

Открывает gameplay loop "не продаю, копию для крафта". Из 2-3 одинаковых предметов одного грейда → один предмет следующего грейда. Шанс успеха зависит от навыка `crafting_skill`.

**Открытые вопросы:**
1. **Формат рецепта** — 2 одинаковых = +1 grade? 3? Разные → новый случайный?
2. **Шанс успеха** — стартовый, рост от прокачки, кап.
3. **При неудаче** — потеря всех материалов / частичный возврат / "осколки" как новый ресурс.
4. **Cap грейда** — A → S разрешено? S → S+?
5. **Стоимость** — кроме материалов, нужны деньги/шаги/энергия?
6. **Quality новых предметов** — усреднение или random?
7. **UI** — где интерфейс (Inventory / отдельная локация "Кузница")?
8. **Связь с Luck** — влияет ли удача на шанс успеха?

**Эффект:** C-grade перестаёт быть мусором, экономика смещается к "копить-крафтить".

**Effort: L** — новая большая система. UI, статы, навык, риск/реворд механика.

**Зависимость:** связана с 1.6 (Items dataclass), 4.7 (Shop / Forge UI).

---

### 4.39. Новый навык: Meditation — отдых с бонусом на выбор `[L / M / todo (отложено 14.05.2026 — хорошая идея, реализация позже)]`

**Обсуждение 14.05.2026:** концепция нравится, но реализация пока не нужна. **Сильно связана с 4.32 Tavern Rest** — рекомендуется реализовывать их **вместе** как единую rest-систему (pool+spend pattern): Tavern копит buffer пассивно, Meditation тратит его с выбором эффекта (+эн / +% к шагам / +% к деньгам). Это убирает exploit-cycle Meditation (тратится накопленный буфер, не текущие ресурсы). При возврате — см. полное обсуждение V1-V5 в conversation history 14.05.2026.

**⚠️ Идея, требует обсуждения баланса. Возможен exploit-цикл.**

Активность "Медитация" — альтернатива продуктивным действиям. Длится ~1 час реального времени, тратит шаги и энергию, **в конце игрок выбирает бонус:**
- +1% к получаемым шагам (сегодня или завтра?)
- +1% к энергии (макс или мгновенный пополнитель?)
- +1% к деньгам

Каждый уровень `meditation_skill` усиливает на 1%.

**Главный вопрос баланса:** если медитация тратит шаги, а даёт +% к шагам сегодня → на высоком уровне игрок может получить больше, чем потратил → бесконечный фарм. **Возможные решения:**
- Бонус на **завтра**, не на сегодня (нет цикла).
- Бонус не "к шагам" (например, +% к энергии не возвращает потраченные шаги).
- Жёсткий cap на скиллы.

**Открытые вопросы:**
1. **Длительность** — 1 час реалистично или скучно? 30 мин для базовой / 1 час для усиленной?
2. **Меню выбора бонуса** — после медитации (как RPG levelup) или перед стартом?
3. **Stacking** — несколько раз в день? Бонусы складываются или cap?
4. **UI** — новая локация / активность из Home?
5. **Связь с 4.32 (Tavern Rest)** — Tavern пассивный idle-bonus, Meditation активный choice. Совместимы или дублируют?

**Effort: M** — новая активность, выбор бонуса, accumulation logic.

**Зависимость:** не блокирующая, но логически после 4.32 (Tavern Rest).

---

### 4.40. Расширение Shop: бустеры, расходники, специальные предметы `[merged into 4.7.X — 14.05.2026]`

**Объединена с 4.7** (Shop зонтичная) 14.05.2026 — концептуально это одна Shop-фича разбитая на этапы. Все категории каталога переехали в подзадачи 4.7:
- 4.7.1 — расходники (Energy Drink, Vitamins, Energy Pack)
- 4.7.2 — бустеры (Speed Boost, Lucky Charm, Money Fever, XP Surge)
- 4.7.3 — стратегические (Streak Freeze, Repair Kit, Insurance)
- 4.7.4 — pet items (Pet Egg, Pet Food)
- 4.7.5 — косметика

Active buffs system (используется бустерами 4.7.2) вынесена в отдельную задачу **4.58** как big-фича независимая от Shop. Номер 4.40 оставлен в TASKS.md для traceability ссылок из других задач / коммитов.

---

### 4.41. Идея: Skill Tree Milestones — бонусы каждые 5-10 уровней навыка `[M / M / todo (нужно обсудить)]`

**⚠️ Идея, требует обсуждения. Без конкретного списка бонусов — нужно отдельно проработать.**

Сейчас прокачка линейная. Идея — **дополнительный бонус на круглых уровнях** (5, 10, 15, ...). Может быть:
- Постоянный (Stamina lvl 10 → +10% к max энергии).
- Активный (Stamina lvl 20 → раз в день мгновенно +50 эн).
- Открытие контента (Speed lvl 30 → доступен walk_50k).
- Косметический титул.

**Что обсудить:**
1. Какие именно уровни (5, 10... vs 10, 25, 50...).
2. Конкретные бонусы для каждого навыка — большая работа.
3. Все навыки получают milestones или часть.
4. Trade-off (выбор между двумя путями).

Аналог: PoE keystones, WoW talent trees.

**Effort: M** — реализация простая (`lvl % 5 == 0`), сложность в дизайне.

**Зависимость:** не блокирующая. Логически после 4.20-4.28.

---

### 4.42. Идея: Locations с уникальной механикой `[M / L / todo (нужно обсудить)]`

**⚠️ Идея, требует обсуждения и проработки контента.**

Расширение 4.31 (Collector). Каждая локация имеет уникальные правила.

**Предварительный список (для обсуждения):**

| Локация | Бонус | Минус |
|---|---|---|
| 🌲 Лес | +25% drop | +50% длительность |
| 🏙 Город | +50% к цене продажи | -25% drop |
| ⛰ Гора | S+ доступны раньше | x2 расход энергии |
| 🌊 Побережье | Бесплатные ремонты раз в день | x0.5 regen энергии |
| 🏜 Пустыня | x2 XP | x2 расход шагов |
| 🌃 Ночной город | Шанс x3 денег или ограбление | Случайный негатив |
| ❄ Снежные горы | Уникальный сет | -30% Speed |

**Что обсудить:**
1. Сколько локаций в первой версии (3 / 5 / 7).
2. Способ переключения (меню в Home / по шагам / последовательно).
3. Уникальные предметы в каждой (синхронно с 4.31 Collector).

**Связь:** **4.31** Collector фактически зависит от этой задачи.

**Effort: L** — большая контентная фича.

**Зависимость:** связана с 1.6, 4.31, 4.46 (Story Mode — главы).

---

### 4.43. Daily Reflection — статистика прогресса при старте дня `[L / S / todo (отложено 13.05.2026 — низкая ценность на текущем этапе)]`

В начале каждого нового дня — короткое meta-сообщение с трекингом. Поощрение через данные.

**Отложено** до момента когда engagement-фичи (4.3 Streak, 4.4 Achievements) станут актуальны — Daily Reflection лучше всего работает в связке с ними (цели на день, streak status). Сейчас reflection без этих контекстов даёт меньше ценности. Технически — задача простая (S, derived from history.jsonl, новый module daily_reflection.py + state.last_reflection_date flag). Когда возьмёмся — см. обсуждение 13.05.2026: Variant A (derive from history.jsonl), Trigger B (last_reflection_date flag), 7 базовых метрик (steps vs avg, drops, earnings, skills, level progress, streak).

**Пример:**
```
=== Утро 27 апреля ===
Вчера ты прошёл 12,500 шагов и получил 3 предмета.
Это на 2,500 больше, чем в среднем за неделю — отличная работа!

Стрик 10k+: 12 дней (+30% к шагам).
Уровень: 9 (89% до уровня 10).

Цель на сегодня: 10k шагов для сохранения стрика.
```

**Метрики:**
- Шаги вчера vs средние за 7 / 30 дней.
- Дропы вчера / общее.
- Прогресс к open goals (4.44).

**Реализация:**
1. Поле `daily_history: list[DayStat]` (последние 30 дней) в `char_characteristic`.
2. При смене дня — добавить запись о вчера, обрезать старше 30 дней.
3. Helper `format_daily_reflection()` в `functions.py`.
4. Вывод при первом тике status_bar нового дня.
5. Save в трёх форматах.

**Effort: S-M** — формирование текста простое, продумать какие метрики.

**Зависимость:** связана с 4.6 (History JSONL — может жить полная история).

---

### 4.44. Goals & Achievements — расширенная система достижений `[merged into 4.62 — 15.05.2026]`

**Объединена с 4.4** в новую зонтичную **4.62 Triumphs / Достижения** (концепция Destiny 2 Triumphs). Goals как «player-defined custom targets» **переосмыслены** как Pinned/Tracked triumphs (выбор 1-3 из системного каталога для приоритетного показа) — это убрало необходимость в отдельной механике custom goals. Категории + бонусы + 4 открытых вопроса переехали в 4.62 как зафиксированные дизайн-решения / open questions. Номер 4.44 оставлен для traceability ссылок.

#### Legacy plan (для истории)

**Два уровня:**
1. **Achievements** — статичные триггеры с бонусами (постоянные / временные / косметика / открытие контента).
2. **Goals** — игрок задаёт сам ("500к шагов до конца месяца"), трекает прогресс.

**Категории achievements (для обсуждения):**

| Категория | Примеры |
|---|---|
| Шаги | 10k / 100k / 1M / 10M total |
| Стрики | 7 / 30 / 100 / 365 дней |
| Дропы | Первый B/A/S/S+, 100/1000 предметов |
| Уровень | char_level 5 / 10 / 25 / 50 |
| Adventures | 100/500 walk_easy, все unlocked |
| Коллекции | Полный сет из локации (4.31) |
| Экономика | 1k / 10k / 100k earned/spent |
| Питомцы | 3 / 5 / все типы (4.37) |

**Бонусы за достижение (для обсуждения):**
- Постоянные (+1% к Stamina навсегда).
- Временные (+10% к шагам на неделю).
- Косметика (титул, badge).
- Открытие контента (новая локация / питомец / активность).

**Что обсудить:**
1. Сколько achievements в первой версии (20 / 50 / 100).
2. Бонус обязательно для каждого или часть — просто trophies.
3. Locked видимость — показывать всё или скрыть до прогресса.
4. Goals vs Achievements — отдельные системы или одна.

**Effort: L** — большая система с UI, контентным дизайном.

**Зависимость:** расширяет 4.4. Связана почти со всем (4.35, 4.31, 4.37).

---

### 4.45. Weekend Bonus / Quests — особое расписание выходных `[M / S / todo]`

В пятницу/субботу/воскресенье — особое расписание игры. Поощряет длинные пешие прогулки.

**Варианты (комбинируемые):**

**1. Глобальные множители:**
- Пятница: +25% drop chance.
- Суббота: +50% drop + x2 XP.
- Воскресенье: +30% Luck + x1.5 деньги.

**2. Уникальные quests:**
- "Weekend Adventure" — длинное приключение (50k шагов), только сб-вс. Гарантированный S-grade.
- "Long Walk" — 25k за день → уникальный предмет.

**3. Achievements за выходные стрики:**
- "10 выходных подряд с 10k+ в субботу" — отдельная награда.

**Реализация:**
1. Helper `is_weekend()` (Fri-Sun).
2. В local helper'ах (luck, drop, money) — weekend modifier.
3. Status_bar показывает "🎉 Weekend +50% drop".
4. Особые quests — пункт в меню Adventure только в выходные.

**Effort: S** — модификаторы простые, основная работа — дизайн набора фич.

**Зависимость:** связана с 4.5 (weekly quest на выходные).

**Связь с 4.59.3 (Gems):** weekend Adventures — натуральный источник rare gems как наградa. Когда дойдём до gems implementation — добавить здесь chance gem drop в weekend-only adventures (например 5-10% при luck=0 vs 1-2% в будни).

---

### 4.46. Story Mode: Путь к Эвересту — нарративная арка игры `[H / L / todo (большая фича)]`

**⚠️ Большая фича, нужна детальная проработка нарратива.** Изначальный замысел игры — трекер реальной ходьбы через путешествие в горы. Финальная цель — **восхождение на Эверест**. Путь — постепенное усложнение реальных маршрутов.

**Структура нарратива:**

| Глава | Локация | Ключевая механика |
|---|---|---|
| 1 | 🌳 Парк у дома | Туториал. Walk_easy / walk_normal. Базовые механики. |
| 2 | 🌲 Лес | Walk_hard. Сет "Лесной". Расширение Shop (спортивная одежда). |
| 3 | 🏞 Холмы / ближние горы | Walk_15k / 20k. **Введение рельефа** (см. ниже). |
| 4 | 🏔 Карпаты — Говерла | **Multi-day expedition** (см. ниже). |
| 5 | 🏔 Альпы / Анды | Холодная погода, **акклиматизация** (новый параметр), уникальные сеты. |
| 6 | 🗻 Эверест | Финальный квест. Самая сложная экспедиция (5-7 дней). Завершение нарратива. |

**Новые механики Story Mode:**

1. **Surface coefficient** — у каждого типа поверхности свой множитель `real_steps × coef → game_steps`:
   - Ровная тропа: ×1.0
   - Подъём: ×0.6 (медленнее, +вес)
   - Спуск: ×1.2 (быстрее, но устаёшь)
   - Лесная тропинка: ×0.85
   - Снег / лёд: ×0.5
2. **Multi-day expeditions:**
   - Игрок выбирает длительность (2-7 дней).
   - Распределяет километраж по дням (день 1: подъём 18 км; день 2: спуск 25 км).
   - В конце игрового дня — обязательная активность "Лагерь" (тратит ресурсы, отдых).
   - Если не выполнен план дня — экспедиция проваливается.
3. **Weather system** — каждый день expedition'а случайная погода:
   - Дождь: -30% Speed.
   - Ветер: +20% энергозатраты.
   - Солнечно: +10% drop.
   - Можно купить "прогноз погоды" в Shop.
4. **Acclimatization** — на больших высотах энергозатраты постепенно растут. Новый навык `adaptation_skill` смягчает.
5. **Equipment requirements** — высокие маршруты требуют exclusive снаряжение (тёплая одежда для Альп, кислородный баллон для Эвереста).
6. **Story beats** — текстовые сценки между главами: описания, диалоги с NPC (тренер, гид), мотивационные сообщения.

**План реализации (фазы):**
- **Phase 0:** Зафиксировать дизайн в `docs/story_mode.md`.
- **Phase 1:** Surface coefficient в существующих adventures (быстрая выгода).
- **Phase 2:** Простые expeditions (1 день, без weather).
- **Phase 3:** Multi-day expeditions с camp.
- **Phase 4:** Weather system.
- **Phase 5:** Acclimatization, equipment requirements.
- **Phase 6:** Story beats, narrative integration.

**Связь с 4.59.3 (Gems):** multi-day expeditions (Phase 3 Холмы / Phase 4 Карпаты-Говерла / Phase 5 Альпы / Phase 6 Эверест) — натуральный источник **гарантированных** gems как reward за длинные маршруты. Чем сложнее экспедиция — тем выше grade gem (small / medium / large). Это даёт content для gems system без spam-droppa из обычных Adventure'ов.

**Преимущества:** игра обретает смысл и направление за пределами цифр. "Хочу подняться на Эверест" — мощнее "хочу +1 stamina". Привязка к реальным горам — долгосрочное вовлечение.

**Риски:**
- Большой объём работы.
- Контентный дизайн (тексты, истории) — отдельный навык.
- Возможный конфликт с sandbox-механикой: Story Mode заменяет sandbox или существует параллельно?

**Effort: L+** — это roadmap на месяцы.

**Зависимость:** разблокировано после 1.1. Story progress / current chapter / expedition state хранятся как новые nested-поля в `GameState` (например, `state.story.chapter`, `state.story.expedition` — отдельный dataclass). Связана с 4.42 (Locations), 4.40 (Equipment), 4.37 (Pets — собака как компаньон).

---

### 4.47. Inline ввод шагов: `+1232` / `+ 1312` сразу из главного меню `[L / S / done]`

QoL-улучшение: чтобы ввести шаги, не нужно делать два шага (`+` → подменю → число). Можно сразу написать команду с числом: `+1232` или `+ 1312` — шаги применяются мгновенно.

**Сделано (2026-04-28):**
- Новый helper `steps_today_set(entered: int)` в `functions.py` — инкапсулирует общую логику `max(old, entered) → steps_today` + проверку отрицательного. Старый `steps_today_manual_entry()` рефакторен под него.
- В `game.py:location_selection()` — диспатчер расширен: при `temp_number.startswith('+') and temp_number != '+'` парсится `int(temp_number[1:].strip())` и вызывается `steps_today_set()`. Простой `+` (включая `"+ "` с одним пробелом) идёт по старому пути через `steps_today_manual_entry()`.

**Edge cases:**
| Ввод | Результат |
|---|---|
| `+1232` | sets steps_today |
| `+ 1312` | strip → sets |
| `+   500` | strip всех пробелов |
| `+` | старое подменю (interactive) |
| `+ ` | как `+` |
| `+abc` / `+1.5` | "Неверный формат..." |
| `+-100` | парсится `-100` → отказ из-за отрицательного |
| `+0` | существующее поведение `max(old, 0)` |
| `++100` | `int("+100") = 100` ✓ |

---

### 4.48. Web Interface + FastAPI backend (зонтичная) `[H / L+ / partial — 11/12 substasks done (20.05.2026, 0.2.5a); остался Shop (4.48.7, blocked by 4.7)]`

**Цель:** добавить веб-интерфейс игры как параллельный путь играть. Открываешь на iPhone после прогулки — управляешь через браузер. CLI остаётся **primary** (содержит больше функциональности), web нарастает incrementally.

**Принципы:**
- CLI первичный, web — дополнение. CLI всегда поддерживается.
- Sheets как **single source of truth** (вариант A, без БД).
- "Last writer wins" — игрок не использует CLI и web одновременно.
- Mobile-first UI (после прогулки открываешь с iPhone).
- В MVP — **без авторизации** (публичный URL по IP:PORT). Auth — отдельная задача 4.55.

**Зафиксированные технические решения (29.04.2026):**
- Backend: **FastAPI** (Python).
- Frontend: HTML + **HTMX** + ванильный JS, минимум зависимостей. Стилизация через Pico.css или Tailwind CDN (mobile-first).
- Templates: Jinja2 (стандарт FastAPI).
- Real-time: **polling каждые 15 секунд** + локальный countdown timer на frontend (плавное убывание между обновлениями).
- Source code reuse с CLI: через **1.1 GameState** — выделение pure mutation functions (`start_work`, `start_training`, `start_adventure`, `set_steps_today`) из CLI меню. Они не печатают в stdout и не вызывают `input()`, поэтому пригодны и для CLI-обёрток, и для FastAPI handler'ов.
- Backup: только Google Sheets (без отдельного JSON-экспорта на VPS).
- Версионирование: **единая** для CLI+web (например, `0.2.0` на major bump после web release).
- Доступ: **IP:PORT** в первой версии. Доменное имя — позже, по необходимости.
- Конфигурация: добавляется в `config.py` через переменные окружения:
  ```python
  import os
  WEB_HOST = os.getenv("WEB_HOST", "127.0.0.1")
  WEB_PORT = int(os.getenv("WEB_PORT", "8008"))
  ```
  - На ноуте при разработке — дефолт `127.0.0.1:8008` (только локально).
  - На VPS — `WEB_HOST=0.0.0.0` через systemd `Environment=` (слушает на публичном IP).
  - Так же можно унести SPREADSHEET_ID и прочее в env, чтобы laptop и VPS не конфликтовали.

**Зависимости:**
- **1.1 GameState** — ✅ **сделано (30.04.2026, версия 0.2.0b)**. Action endpoints могут вызывать `actions.try_spend / start_work / start_training / start_adventure` напрямую — у них нет print/input, они работают с `state: GameState`.
- **4.14 Sheets split** — желательно ДО 4.48 для разделения `game_state` и `steps_log` в источнике.

**Замены / устаревания:**
- **4.13 (Apps Script + iOS Shortcut)** — **deprecated by 4.48.2**. После работоспособности `/api/steps` — заменяет Apps Script, iOS Shortcut шлёт прямо в FastAPI.
- **4.10 (Dashboard в Sheets)** — частично замещается 4.48.1.

#### 4.48.0. Setup: FastAPI скелет + локальный запуск `[H / M / done (01.05.2026)]`

**Сделано:** FastAPI приложение готово к локальной разработке. VPS deploy — отдельная задача 4.48.0.1 (создана), делается когда понадобится publish.

**Реализовано:**
- Папка `web/` с `__init__.py` + `main.py`. `app = FastAPI(title='2Walks Web', version='0.2.0e', lifespan=lifespan)`.
- `lifespan` async context manager → `init_game_state()` синхронно при startup. Idempotent — повторный вызов в тестах no-op.
- Endpoint `GET /healthz` → JSON `{"status": "ok", "state_loaded": bool, "version": str}`.
- Endpoint `GET /` → HTMLResponse-заглушка с версией и индикатором state_loaded. Полноценный dashboard будет в 4.48.1.
- `config.py`: `WEB_HOST` / `WEB_PORT` через env vars (defaults `127.0.0.1` / `8008`). На VPS — `WEB_HOST=0.0.0.0`.
- `requirements.txt`: добавлены `fastapi>=0.110`, `uvicorn[standard]>=0.27`, `jinja2>=3.1`, `httpx>=0.27` (httpx нужен для FastAPI TestClient).
- `tests/test_web_main.py` — 5 тестов через `fastapi.testclient.TestClient` (healthz, root HTML, lifespan idempotency, 404 на unknown route).
- Smoke test: `uvicorn web.main:app` стартует, `curl /healthz` возвращает корректный JSON, `curl /` отдаёт HTML.
- `CLAUDE.md` обновлён с командой запуска web.

**Запуск локально:**
```bash
uvicorn web.main:app --reload --host 127.0.0.1 --port 8008
```

**Note:** CLI (`python game.py`) и web (`uvicorn web.main:app`) — отдельные процессы, у каждого свой `game.state`. В MVP запускаем что-то одно. Sync — задача 4.54.

#### 4.48.0.1. Deploy FastAPI на сервер `[H / S / done (18.05.2026)]`

**Цель (15.05.2026):** локальный Ubuntu-сервер крутит web 24/7. Доступ только из домашней сети (`http://server-ip:8008`), без публичного интернета / без TLS / без auth. Игрок открывает вкладку с iPhone / MacBook / любого устройства и играет (вводит шаги, стартует смены, прокачивает скиллы). CLI на ноутбуке остаётся как secondary debug-инструмент — concurrent usage защищён через 4.54 optimistic concurrency (STALE prompt в CLI / auto-reload toast в web).

**Реализовано (18.05.2026):**

- **Сервер:** Ubuntu 24.04 на домашнем PC (Gigabyte H61M-DS2H, hostname `aleksey-H61M-DS2H`, пользователь `aleksey`). Уже был использован для проекта convertme (gunicorn на :8000 + cloudflared tunnel) — 2Walks занял непересекающийся порт :8008.
- **IP:** 192.168.0.155 (по факту deploy'а), доступ также через mDNS `aleksey-H61M-DS2H.local:8008` (avahi-daemon на Ubuntu даёт Bonjour-resolution из коробки, работает с MacBook/iPhone).
- **Путь:** `/home/aleksey/2Walks/` (clone из GitHub), `.venv/` рядом, credentials в `~/2Walks/credentials/` (scp с MacBook'а, gitignored).
- **systemd:** `/etc/systemd/system/2walks.service` с `Restart=on-failure`, `RestartSec=5`, `User=aleksey`, `WorkingDirectory=/home/aleksey/2Walks`, `ExecStart=.venv/bin/uvicorn web.main:app --host 0.0.0.0 --port 8008`. Enable + start — Active: running. Auto-start на reboot настроен.
- **Firewall:** `sudo ufw allow 8008/tcp` (ufw был active с :22/:8000/Nginx Full уже разрешёнными — :8008 пришлось добавить отдельно).
- **Smoke-test (live verification, 15:01-15:02 EEST):** MacBook (192.168.0.218) GET / → 200 OK; iPhone (192.168.0.132) GET / → 200 OK; iPhone POST /web/steps → 200 OK (полный mutation цикл через сервер работает, persist в Sheets подтверждён).
- **Updates workflow:** `ssh aleksey@192.168.0.155 "cd ~/2Walks && git pull && .venv/bin/pip install -r requirements.txt && sudo systemctl restart 2walks && sudo systemctl status 2walks"` — одна команда с MacBook'а.
- **Логи:** `sudo journalctl -u 2walks -f` (реал-тайм) или `-n 50 --no-pager` (последние 50 строк). Видны GET / POST с client IP, Sheets timings, ошибки.
- **Документация:** добавлен раздел «Production: web 24/7 на Ubuntu-сервере» в `docs/local_setup.md`. CLAUDE.md обновлён — «Secondary (planned)» → «Secondary (deployed on home Ubuntu server, 0.2.4p / 18.05.2026)».

**Pending follow-up (не блокер):**
- **DHCP reservation** в роутере для 192.168.0.155 — иначе IP может переназначиться через несколько дней. Делается в админке роутера, не через терминал. (mDNS URL `aleksey-H61M-DS2H.local` будет работать даже если IP сменится — fallback).
- **Bake-test 1-2 дня** — играть обычно через web на сервере + occasional CLI на MacBook. По итогам `ssh ... "grep '\"sync_conflict\"' ~/2Walks/history.jsonl | wc -l"` — если редко, всё ОК. Если часто (>5/день) — повод вернуть auto-retry в save_safe (см. follow-up в 4.54.8).
- **Convenience aliases на MacBook** (`2walks-deploy`, `2walks-logs`, `2walks-status`) — опционально, добавлять по запросу.

**Блокер снят (15.05.2026):** 4.54 завершена, optimistic concurrency защищает данные при одновременной работе CLI ↔ web. Старого риска тихого overwrite'а больше нет.

---

##### Pre-flight checklist (что нужно знать до начала)

Перед запуском любого `ssh` собрать заранее:

- **IP сервера в локальной сети** — `ipconfig getifaddr en0` на самом сервере (если Mac mini / лэптоп) или `ip addr show | grep inet` (Ubuntu). Этот IP нужно **зарезервировать в роутере** (DHCP reservation) чтобы не менялся.
- **SSH доступ** — `ssh user@<server-ip>` должен работать без пароля (key-based auth). Если нет — `ssh-copy-id user@<server-ip>`.
- **Python 3.11+ на сервере** — `python3 --version`. Если нет: `sudo apt install python3.11 python3.11-venv` (Ubuntu 22.04+) или из deadsnakes PPA для старых.
- **Git installed** — `git --version`. Если нет: `sudo apt install git`.
- **Файл `credentials/2walks_service_account.json`** на ноутбуке — копия service account для Google Sheets (gitignored). На сервере его не будет после `git clone`, нужно перенести вручную.
- **Снимок текущего state** — Sheets уже primary source of truth, поэтому ничего seed'ить не нужно. Сервер при первом запуске прочитает Sheets и заведёт локальный `characteristic.csv` как фолбэк автоматически.

**Critical nuance: `characteristic.csv` НЕ в репо** (с 0.2.4p, после .gitignore cleanup'а 15.05.2026). Раньше был отслеживаемым — теперь нет. На свежем clone файл отсутствует, но это **не блокер**: при наличии валидных credentials `init_game_state()` загружает state из Sheets и при первом save локальный CSV создаётся автоматически. Если же credentials невалидны / Sheets недоступен И CSV нет — `init_game_state()` упадёт с ошибкой, web не стартанёт. Поэтому критично: **переносим credentials до первого запуска**.

---

##### Пошаговая процедура deploy

**Шаг 1 — Подготовка сервера (один раз).**

```bash
# На сервере (через SSH с ноутбука).
ssh user@<server-ip>

# Проверить базовое окружение.
python3 --version    # ожидаем 3.11+
git --version

# Установить недостающее (Ubuntu).
sudo apt update
sudo apt install -y python3.11 python3.11-venv git

# Создать директорию для проекта (опционально — можно в $HOME).
mkdir -p ~/projects && cd ~/projects
```

**Шаг 2 — Clone репо + venv.**

```bash
# Всё ещё на сервере, в ~/projects.
git clone https://github.com/A1ekseyN/2Walks.git
cd 2Walks

# Создать venv и поставить runtime-зависимости (НЕ requirements-dev).
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

**Шаг 3 — Перенос credentials (CRITICAL).**

```bash
# С ноутбука (НЕ с сервера — credentials живут только локально на ноуте).
scp credentials/2walks_service_account.json user@<server-ip>:~/projects/2Walks/credentials/

# Если на сервере нет директории credentials/ — создать сначала:
ssh user@<server-ip> "mkdir -p ~/projects/2Walks/credentials"

# Проверить что файл на месте.
ssh user@<server-ip> "ls -la ~/projects/2Walks/credentials/"
```

**Шаг 4 — Smoke-test ручным запуском.**

```bash
# На сервере.
cd ~/projects/2Walks
source .venv/bin/activate

# Запустить web вручную с привязкой ко всем интерфейсам.
.venv/bin/uvicorn web.main:app --host 0.0.0.0 --port 8008
```

В выводе должно быть:
- `Loading...` → `Data Loaded from Google Sheets. [N sec]` — Sheets подключился, state загружен.
- `Application startup complete.` — uvicorn готов принимать соединения.

С ноутбука / iPhone открыть `http://<server-ip>:8008/` — должен показать dashboard. Submit'нуть форму steps (например +1) — проверить что обновляется + новая запись в `history.jsonl` на сервере.

Если всё ОК — `Ctrl+C` в терминале сервера, переходим к systemd. Если нет — см. раздел Troubleshooting ниже.

**Шаг 5 — Systemd unit для production.**

Создать `/etc/systemd/system/2walks.service`:

```ini
[Unit]
Description=2Walks web (FastAPI)
After=network.target

[Service]
Type=simple
User=<your-username>
WorkingDirectory=/home/<your-username>/projects/2Walks
Environment="PATH=/home/<your-username>/projects/2Walks/.venv/bin"
ExecStart=/home/<your-username>/projects/2Walks/.venv/bin/uvicorn web.main:app --host 0.0.0.0 --port 8008
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**Заменить `<your-username>` на реального пользователя** (обычно совпадает с тем, под кем `ssh`'ился). Проверить через `whoami`.

```bash
# Включить и запустить.
sudo systemctl daemon-reload
sudo systemctl enable 2walks
sudo systemctl start 2walks

# Проверить статус.
sudo systemctl status 2walks
# Ожидаем: Active: active (running)

# Логи (через journald — default backend).
sudo journalctl -u 2walks -f
```

Закрыть SSH — uvicorn продолжит работать. Перезагрузка сервера — auto-restart.

**Шаг 6 — Updates workflow (после изменений в репо).**

```bash
# С ноутбука.
ssh user@<server-ip>
cd ~/projects/2Walks
git pull
sudo systemctl restart 2walks
sudo systemctl status 2walks    # verify
```

Если в обновлении новые зависимости (изменился `requirements.txt`) — добавить `source .venv/bin/activate && pip install -r requirements.txt` между `git pull` и `restart`.

**Шаг 7 — Bake-test 1-2 дня.**

- Игра через iPhone / MacBook без рестартов.
- Параллельно периодически запускать CLI на ноутбуке (`python game.py`) — проверять что STALE prompt появляется естественно при concurrent действиях.
- Мониторить `journalctl -u 2walks -f` на ошибки.
- В конце дня: `ssh user@<server-ip> "grep '\"sync_conflict\"' ~/projects/2Walks/history.jsonl | wc -l"` — счётчик STALE-конфликтов. Если стабильно >5/день — повод вернуть auto-retry в save_safe (см. follow-up watch в 4.54.8).

---

##### Troubleshooting

| Симптом | Вероятная причина / решение |
|---|---|
| `ModuleNotFoundError: No module named 'fastapi'` | venv не активирован или пустой. `source .venv/bin/activate && pip install -r requirements.txt`. |
| `init_game_state()` крашится с Sheets-ошибкой | credentials не на месте или невалидные. Проверить `ls credentials/2walks_service_account.json`, что в Sheets открыт share для service account email (см. CLAUDE.md). |
| 404 при заходе с iPhone (а с самого сервера всё ОК) | uvicorn запущен с `--host 127.0.0.1` (default). Должно быть `--host 0.0.0.0`. Проверить `ExecStart` в systemd unit. |
| iPhone не может зайти даже с правильным IP | Firewall на сервере: `sudo ufw allow 8008/tcp`. Или iPhone не в той же Wi-Fi сети. |
| `systemctl status` показывает `failed` | `sudo journalctl -u 2walks -n 50` — посмотреть последние строки логов. Чаще всего: неправильный путь в WorkingDirectory / User / Environment. |
| После git pull web не подхватил изменения | Забыли `systemctl restart 2walks`. systemd не auto-reload'ит на изменение файлов (это не uvicorn `--reload` mode). |

---

##### Не входит в скоуп MVP

- **Reverse proxy** (nginx / caddy) — нужен только если будет несколько сервисов на одном порту или TLS.
- **Domain / DNS** — local-only, по IP достаточно. Опционально mDNS (`<hostname>.local`) если хочется не запоминать IP.
- **HTTPS / Let's Encrypt** — local-only, нет смысла.
- **Auth** (см. 4.55) — отдельная задача, не блокирует local deploy.
- **Multi-user** (4.53) — single-user game, нет нужды.
- **Backups** Sheets — Sheets сами по себе хранят историю изменений. CSV-фолбэк на сервере как secondary safety. Этого достаточно для MVP.

---

##### Эффорт + зависимости

**Эффорт:** **S** (1-2 часа на сервере с Python 3.11+, всё по checklist'у).

**Зависимости:**
- **4.54** (sync resolution) ✓ done (15.05.2026, 0.2.4p) — разблокировал.
- **4.48.1** (dashboard) ✓ done — основа для deploy.
- **4.55** (auth) — НЕ блокирует (local-only deploy).

**Связь с другими задачами:**
- После deploy документация `docs/local_setup.md` дополняется новым разделом «Production: web на сервере» (текущий focus раздела — local dev на ноуте).
- `history.jsonl` будет жить на сервере. Для чтения с ноутбука — `scp user@<server-ip>:~/projects/2Walks/history.jsonl ./` или ждём 4.6.2 (CLI viewer истории) для удобного access'а.
- На сервере credentials живут локально — это **single point of failure**. При переустановке сервера / диск-краше credentials придётся переносить вручную с ноутбука. Backup-копию credentials рекомендую держать в защищённом месте (1Password / encrypted backup).

#### 4.48.1. Dashboard (read-only HTML) `[H / M / done (01.05.2026)]`

**Сделано:** read-only веб-dashboard с автообновлением. Открываешь URL на iPhone после прогулки — видишь свой статус-бар, активные таймеры, инвентарь и экипировку без ввода.

**Реализация:**
- `web/templates/dashboard.html` — главная страница (Pico.css + HTMX через CDN). Wrapper `<div id="status-bar" hx-get="/status" hx-trigger="every 15s" hx-swap="innerHTML">{% include "_status_fragment.html" %}</div>`.
- `web/templates/_status_fragment.html` — общий фрагмент (Stats / Active sessions / Inventory / Equipment), ре-используется и в полной странице (через `include`), и в HTMX-полинге.
- `web/main.py:_dashboard_context()` — собирает все данные для шаблонов в один dict (state + bonuses + char_level + active session timestamps как Unix float для JS-таймеров).
- `GET /` — рендерит `dashboard.html`.
- `GET /status` — рендерит `_status_fragment.html` (без `<html>` обёртки, для HTMX swap'а).
- JS-таймер в dashboard.html — раз в секунду пересчитывает `data-end-ts="<unix_ts>"` элементы, плавно убывает время. После HTMX swap (`htmx:afterSwap`) — refresh.
- Adventure после истечения end_ts: показываем "Adventure finished — return to game (CLI) to claim drop" — read-only слой не финализирует mutations. Финализация через web — задача 4.48.3.
- Mobile-first via Pico.css defaults; точечные правки в `<style>` (крупные элементы, минимум скролла).

**Технические нюансы:**
- Starlette 1.0+ изменил сигнатуру `TemplateResponse(request, name, context)` — старый порядок `TemplateResponse(name, context)` ломается с криптической ошибкой "unhashable type: 'dict'" в LRUCache. Используем новую сигнатуру.
- HTMX через CDN (`unpkg.com/htmx.org@1.9.10`), Pico.css через CDN (`@picocss/pico@2`). Локальные копии — на VPS-deploy если нужен offline.
- `state.steps.can_use` НЕ пересчитывается на каждый polling (read-only). Live-recalc при day rollover — задача на будущее.

**Версия:** `0.2.0e` → `0.2.0f`.

**Тесты (`tests/test_web_main.py`):** 19 тестов всего — расширены с 5 (4.48.0). Покрывают: dashboard HTML + secret/HTMX/CDN markers; status fragment без `<html>` обёртки; active session rendering (training / work / adventure with `data-end-ts`); finished adventure shows warning not timer; empty inventory placeholder; filled inventory rendering; empty equipment slots; filled equipment slot details; location icon + name; no-active-sessions section omitted. Все 203 теста pass.

**Smoke verified:** `uvicorn web.main:app` на ноуте; открытие в браузере iPhone через локальную сеть рендерит весь dashboard корректно.

**Прогресс-бары активных сессий (доделано 01.05.2026):** для Work / Training / Adventure добавлены `<progress>` элементы (формат: 🕑 timer + bar + `XX.XX %` + `✓ Завершено` если pct≥100). Гибрид server-side initial render + client-side JS update раз в секунду через `data-progress-start-ts` / `data-progress-end-ts` атрибуты. Адвенчура с `end_ts < now` показывает progress=100 + ✓ Завершено + сохранённый warning "Adventure finished — return to game (CLI) to claim drop". 6 новых тестов в test_web_main.py.

**UI tweak (01.05.2026):** секция Экипировки перемещена выше Инвентаря. Экипировка короче (7 слотов фиксировано) и меняется реже — "что надето сейчас" видно выше fold'а. Новый тест `test_equipment_section_appears_before_inventory` фиксирует порядок. Всего 210 тестов pass.

**Что НЕ сделано в 4.48.1 (отложено в подзадачи):**
- Action endpoints (start training / work / adventure / sell / equip) — задачи 4.48.3–4.48.8.
- Live recalc `steps.can_use` при day rollover — отдельной задачей при необходимости.
- Auth — задача 4.55.

#### 4.48.2. POST /api/steps + web-форма ввода `[H / S / done (01.05.2026)]`

**Цель:** ввод реальных шагов с браслета через любой канал — web-форма на dashboard, `curl`/iPhone Shortcut через API. Применяется `max(old, new)` к `state.steps.today` (max-merge) и пишется в `steps_log` Sheet.

**Реализация (01.05.2026):**
- **Два endpoint'а с общим helper:**
  - `POST /api/steps` — JSON `{"steps": int, "ts"?: float, "source"?: str}`. Возвращает JSON `{ok, applied, steps_today, steps_can_use, logged}`. Универсально для curl / Shortcut.
  - `POST /web/steps` — form-data `steps=N`. Возвращает HTML-фрагмент `_status_fragment.html` (HTMX swap `#status-bar`). Используется кликабельным блоком на dashboard.
- **Применение к state (Variant ii):** `state.steps.today = N` + `state.steps.can_use = today - used + total_bonus_steps(state)` + `StepsLogRepo().append(ts, N, source)`. Instant memory update.
- **Валидация:** `N > state.steps.today` (строго больше). Меньшее → 422 + сообщение. Client-side `<input min="today+1">` + server-side проверка для curl/Shortcut.
- **Ошибка Sheets:** state НЕ обновляется, log не пишется, 503 + `{"ok": false, "error": "Sheets unavailable"}`. Без retry, без cache.
- **UX (web):** клик на блок `🏃 Steps` (вся строка с цифрами + bonuses) → ниже expand inline-форма (input + Применить + Отмена). Pre-fill input пустой. Loading state — disabled + "Сохраняем..." на кнопке. После успеха форма закрывается (HTMX swap фрагмента, который рендерится без открытой формы).

**Версия:** `0.2.0h`.

**Тесты:**
- `POST /api/steps` valid > today → 200 + applied=true + steps_log.append вызван.
- `POST /api/steps` <= today → 422 + applied=false + state не изменён.
- `POST /api/steps` non-int / negative → 422 от Pydantic.
- `POST /api/steps` Sheets error → 503 + state не изменён.
- `POST /web/steps` valid → 200 + HTML fragment с обновлёнными числами.
- `POST /web/steps` invalid → 200 + HTML fragment с error message + form open.
- HTML form с `<input min="N+1">` присутствует в dashboard.
- Форма скрыта по умолчанию (CSS), показывается через JS toggle на клик.

**Что НЕ делается в этой задаче:**
- Авто-сохранение `game_state` в Sheets после применения шагов — задача на будущее (web Save button).
- Силовой пересчёт day rollover — отдельный канал через `save_game_date_last_enter` остаётся для CLI.
- iPhone Shortcut canonical интеграция — задача отложена (4.13). Endpoint работает с любым клиентом, но воспринимается как "ручной".
- Авторизация — задача 4.55.

#### 4.48.2.1. UX: placeholder поля шагов показывает текущее значение `[L / XS / done (0.2.1w)]`

**Проблема:** placeholder в форме ввода шагов был статичным текстом "введи число с браслета". Игрок не видел, какое значение он вводил в прошлый раз, поэтому не мог легко решить — нужно ли обновлять или текущее уже актуально (особенно при возврате к web после длительного перерыва).

**Решение (06.05.2026):** placeholder сделан динамическим — показывает `state.steps.today` с разделителями тысяч: `"Введите число пройденных шагов. Сегодня пройдено: 1,234"`. Если значение ещё не введено сегодня (новый день / новая игра) — отобразится `"Сегодня пройдено: 0"`, что тоже информативный сигнал.

**Версия:** `0.2.1w`.

**Изменения:**
- `web/templates/_status_fragment.html` (1 строка): `placeholder="Введите число пройденных шагов. Сегодня пройдено: {{ '{:,}'.format(state.steps.today) }}"`.

**Что НЕ делалось:**
- Тесты на конкретный placeholder text — фрагильно, при i18n / переформулировках сразу ломается, ценности мало.
- `<small>` подсказку рядом с формой — placeholder достаточно. Если на узких мобильных текст обрежется и станет проблемой UX — отдельная задача.

#### 4.48.3. Web: Adventure `[H / M / done (19.05.2026, 0.2.4s)]`

- `GET /adventure` — список доступных прогулок + прогресс разблокировки (синергия с 4.34).
- `POST /api/adventure/start` — старт прогулки + списание ресурсов.
- Локальный countdown до завершения, прогресс-бар.
- Auto-finalize при истечении таймера (детектится в polling, дроп показывается).

**Реализовано (19.05.2026, 0.2.4s):**
- Меню старта = новая `<section id="adventure">` в `_status_fragment.html` (между Work и Gym). 7 прогулок с прогрессивной разблокировкой (3 прохождения предыдущего тира); locked — greyed-out + 🔒 + unlock hint, unlocked — cost + probabilities (`compute_grade_probabilities` с current luck) + Start button (`hx-confirm`) или disabled c «не хватает». Active state — informational summary без кнопок.
- Endpoints: `POST /web/adventure/start` (Form, fragment swap) + `POST /api/adventure/start` (JSON, `AdventureStartRequest`). STALE 409 на concurrent save.
- `_validate_and_apply_adventure`: already-active / unknown / locked / insufficient checks → try_spend → actions.start_adventure → decrease_durability → log_event → persist.
- Auto-finalize через `_finalize_adventure_with_drop_capture(state)` в `_dashboard_context` рядом с work_check_done.
- **Drop notification mechanism**: новое runtime-only `state.last_adventure_drop` (НЕ сериализуется, как `last_loaded_snapshot`). Finalize wrapper детектит transition через delta inventory/pending_drop и пишет item. Banner («🎁 Из приключения выпало», зелёный) переживает F5, очищается на любом успешном mutation (через `_persist_and_handle_stale` и явный clear в `_apply_new_steps`).
- Тесты: 28 новых в `tests/test_web_main.py` (view helper 7, validate 5, web POST 2, api POST 4, finalize 4, banner 4, section render 3) + 2 существующих обновлены (старое «claim drop in CLI» поведение убрано). 859 passed total, mypy 0 issues.
- **Polish после feedback'а игрока (тот же день, 0.2.4s):** (1) cost time из сырых минут переведён на human-readable формат через новый `functions_02.format_minutes(x)` — plain-text близнец `time(x)` без colorama (Jinja global). «🕑 ~103 мин» → «🕑 ~1 ч. 43 мин.», то же в hx-confirm. 6 новых тестов. (2) Grade labels раскрыты с одиночных букв на полные формы через `_GRADE_LABELS` constant (`c-grade → C-Grade`, ..., `s+grade → S+ Grade` с пробелом, consistent с CLI). «B [28.86%]» → «B-Grade [28.86%]». 2 новых теста. После polish — 867 passed, mypy 0 issues.
- **Web feature parity с CLI достигнута** для геймплейных активностей. Остались только Inventory/Equipment mutations (4.48.6) и Shop (4.48.7 — blocked by 4.7) + Банк (4.48.9 — готов к работе).

#### 4.48.4. Web: Gym `[H / M / done (0.2.1e)]`

- Старт прокачки навыков (8 пунктов) через web. Новая `<section id="gym">` после Work, свёрнута по умолчанию.
- Когда `state.training.active=True` → блок показывает подсказку "Идёт прокачка X. Прогресс в Active sessions"; меню стартов скрыто (одна тренировка за раз, как в CLI).
- Когда тренировки нет — 8 карточек навыков с pre-computed cost (`🏃 -N · 🔋 -M · 💰 -K · 🕑 ~Xm`). Если ресурсов не хватает — кнопка `disabled` + строка `Не хватает: 🏃 N · 🔋 M`. `hx-confirm` перед стартом ("Прокачать Stamina (4 → 5)? Спишется ...").
- 2 endpoint'а: `POST /web/gym/start` (Form) и `POST /api/gym/start` (JSON через `GymStartRequest`). Общий helper `_validate_and_apply_training(state, skill_name)` делает pre-flight проверку ресурсов, дёргает CLI helper `Skill_Training(state, name).start_skill_training()` (`try_spend` + `actions.start_training` + `Wear_Equipped_Items.decrease_durability`), затем `persist_state_to_cloud()`.
- Auto-finalize: `skill_training_check_done(state)` теперь вызывается в `_dashboard_context` (рядом с `work_check_done`). Каждый GET / POST после истечения таймера повышает уровень навыка на +1 и обнуляет training. CLI остаётся primary path для main loop.
- `energy_max` в меню отображается, но помечен `available=False` — не запускается через web с понятной ошибкой "Особая логика — см. задачу 4.48.4.1". CLI flow для energy_max тоже сломан (`getattr(state.gym, 'energy_max')` → AttributeError, поле в dataclass называется `energy_max_skill`).

#### 4.48.4.1. Review: логика energy_max_skill `[M / S / done (0.2.1g)]`

**Контекст (04.05.2026, обнаружено при реализации 4.48.4):** прокачка навыка `energy_max` сломана и в CLI, и в web. Симптомы:

1. `state.gym.energy_max_skill` существует как поле в dataclass `GymSkills`, но **никогда не записывается** — в коде нет `setattr(state.gym, 'energy_max_skill', ...)`.
2. CLI `gym_menu` использует ключ `'energy_max'` (без `_skill`) для skill_options, передаёт его в `Skill_Training(state, name='energy_max')`.
3. `Skill_Training.check_requirements()` / `start_skill_training()` делают `getattr(state._state.gym, self.name)` → `getattr(state.gym, 'energy_max')` → **AttributeError** (поля с таким именем нет, есть только `energy_max_skill`).
4. `skill_training_check_done(state)` тоже сделает `getattr(state.gym, 'energy_max') + 1` → `setattr(state.gym, 'energy_max', ...)` — создаст лишнее поле, не относящееся к dataclass-схеме.

**Логика которая работает:** `_energy_max_skill_level(state) = state.energy_max - 49 - equipment_energy_max_bonus(state) - state.steps.daily_bonus`. Этот reverse-calc правильно показывает уровень в меню (для default state.energy_max=50 → level=1).

**Что нужно решить:**

1. **Привести имя в соответствие.** Либо переименовать `_skill` суффикс везде на `state.gym.energy_max_skill` (как в `speed_skill`, `luck_skill`), либо хранить уровень в `state.energy_max_skill_level` отдельно от `state.energy_max`.
2. **Решить, где хранить накопленный уровень навыка.** Текущая логика "уровень = state.energy_max - 49 - bonuses" работает только если каждый level-up инкрементит `state.energy_max`. Но bonuses тоже бьют по этой же переменной — путаница. Лучше: завести отдельное `state.gym.energy_max_skill` (целевое имя), и `state.energy_max` вычислять как `50 + state.gym.energy_max_skill + bonuses` на лету.
3. **`skill_training_check_done` для energy_max:** должен инкрементить `state.gym.energy_max_skill` (или альтернативную переменную) и пересчитать `state.energy_max`.
4. **Тесты:** `tests/test_gym.py` — добавить test_energy_max_training_increments_correctly + round-trip через `state.from_dict / to_dict`.

**Effort:** S (понятный refactor, ~30-50 строк + миграция существующих save'ов).

**Зависимость:** не блокирующая. Текущий web-флоу 4.48.4 показывает energy_max в UI с пометкой "недоступно", остальные 7 навыков работают. CLI тоже не использует energy_max нормально (упадёт при попытке).

**Сделано (04.05.2026, версия 0.2.1g):**
- Pure variant A: добавлен helper `bonus.compute_energy_max(state)` — сумма из 5 источников (50 + gym.energy_max_skill + equipment + daily_bonus + char_level.skill_energy_max). Все читатели (`actions.try_spend`, `functions.energy_time_charge`, `functions.status_bar`, `functions.char_info`, `web/main.py:_dashboard_context`) теперь используют эту функцию вместо `state.energy_max` (поле осталось в dataclass для save-format совместимости — обновляется при load через `compute_energy_max`).
- Удалён off-by-one helper `_energy_max_skill_level` (формула `state.energy_max - 49 - bonuses` могла давать отрицательные значения при рассинхроне между runtime energy_max и источниками).
- Унификация ключа: `'energy_max'` → `'energy_max_skill'` в `gym.py:_SKILL_DESCRIPTIONS`, `gym_menu skill_options`, `gym._next_skill_level`, `gym._training_cost`, `web/main.py:_GYM_SKILL_DISPLAY` (флаг `available=False` снят, energy_max_skill теперь обычный навык).
- Защитная миграция в `state.from_dict`: если `skill_training_name == 'energy_max'` (старый сейв) — автоконвертация в `'energy_max_skill'`.
- Удалена мёртвая функция `bonus.skill_bonus_energy_max` + соответствующий тест.
- Удалён дубликат `_equipment_energy_max_bonus` в characteristics.py — все используют `equipment_bonus.equipment_energy_max_bonus`.
- 4 новых теста в `test_bonus.py` (compute_energy_max default / gym_skill / all_sources / ignores_state_field).
- Существующие тесты обновлены: `test_gym.py` (удалены `_energy_max_skill_level` тесты, добавлен `test_next_skill_level_for_energy_max_skill`), `test_characteristics.py` (импорт обновлён на `equipment_bonus.equipment_energy_max_bonus`), `test_web_main.py` (energy_max_skill теперь работает + старый ключ `'energy_max'` возвращает "Неизвестный навык").
- Smoke verify (read-only, без записи в Sheets): загруженный state имеет `gym.energy_max_skill = 15`, `compute_energy_max(state) = 65`, `state.energy_max (cache) = 65` — всё консистентно. Прокачка с уровня 15 теперь работает (раньше падала на AttributeError).
- All 355 tests pass.

- `GET /gym` — таблица скиллов с ценами/требованиями.
- `POST /api/gym/train` — старт обучения.
- Локальный countdown до завершения тренировки.

#### 4.48.5. Web: Work `[H / M / done (0.2.1a)]`

- `GET /work` — выбор вакансии и часов. **Реализовано как блок `id="work"` в `_status_fragment.html`**, без отдельного route'а — UI работы интегрирован в основной dashboard через `<details>`. Свёрнут по умолчанию в обоих состояниях (и когда работаешь, и когда нет) — чтобы Stats оставалась primary view, а игрок сам раскрывает Work при необходимости.
- `POST /web/work/start` (Form) — старт смены, возвращает HTML-фрагмент.
- `POST /web/work/add_hours` (Form) — добавить часы к активной смене (берёт `state.work.work_type` из state — UI не даёт сменить вакансию посреди смены, как в CLI).
- `POST /api/work/start` (JSON) + `POST /api/work/add_hours` (JSON) — для curl / future iPhone Shortcut.
- 4 вакансии (`watchman / factory / courier_foot / forwarder`) с кнопками часов 1..N (cap 8). N = `min(steps/req, energy/req, 8)`, считается в Python (`_max_work_hours`).
- Auto-finalize смены: `work_check_done(state)` вызывается на каждый рендер `_dashboard_context()` — F5 / любой POST автоматически закроет смену, начислит зарплату и обнулит `state.work`. CLI не нужен для claim'а.
- Известное ограничение: если игрок никогда не зайдёт на web после `state.work.end`, смена не финализируется до следующего захода (или CLI tick'а). Не критично, но см. 4.48.5.1 ниже.

#### 4.48.5.1. Web: double-claim race в финализаторах (Work + Training + Adventure) `[L / S / done (20.05.2026, 0.2.5a)]`

**Контекст:** auto-finalize Work / Training / Adventure через `_dashboard_context()` мутировал RAM ПЕРЕД save_characteristic. Если save fail (network / quota) → mutation в RAM, но Sheets stale (state.work.active=True). На web restart → reload из Sheets → финализатор срабатывает снова → **двойной claim**. До 0.2.5a в коде висел warning «retry on next user save» которая не закрывала race.

**Реализация (20.05.2026, 0.2.5a, Variant A per design discussion):** Atomic save-first pattern с rollback при STALE.

1. **Новое runtime-only поле** `state.GameState.finalize_stale: bool = field(default=False, repr=False, compare=False)` — НЕ сериализуется, сбрасывается caller'ом после обработки.

2. **3 финализатора рефакторены** одинаковым паттерном:
   - **`work.work_check_done`** — snapshot (money + 6 work fields) → tentative mutate → save → rollback при STALE. log_event('work_done') + «заработали» print фаерятся только после OK commit.
   - **`gym.skill_training_check_done`** — snapshot (skill level + 4 training fields) → tentative mutate (+ `stamina_skill_bonus_def` recompute) → save → rollback (+ re-call recompute с старым уровнем). log_event('skill_upgraded') + «улучшен до» print только после OK.
   - **`web/main.py:_finalize_adventure_with_drop_capture`** — snapshot 6 полей (inventory list + pending_drop + adventure tuple + counters dict + money + last_adventure_drop) → call adventure_check_done → capture drop → save → rollback при STALE.

3. **Web STALE response для финализаторов:**
   - Новый helper `_stale_response_full_page()` — полный HTML doc с warning toast + JS `window.location.reload()` через 2 сек. Для GET / navigation (в отличие от существующего `_stale_response()` который returns fragment для HTMX swap).
   - Новая обёртка `_render_dashboard_or_stale(request, template_name, context)` проверяет `state.finalize_stale` после `_dashboard_context` и возвращает либо STALE response, либо обычный template. 20 callers `templates.TemplateResponse` заменены на helper через replace_all.

4. **CLI остаётся прежним UX** — print warning «[X finalize] STALE — claim откатан». На следующем `s`/`q` сработает `handle_stale_prompt` (3-option r/f/c) и подтянет fresh state. Асимметрия web/CLI оправдана: web пассивны (вкладка в браузере), CLI активны (видят каждую stdout строку).

**Closes race:** claim попадает в state ТОЛЬКО если save в Sheets прошёл успешно. Web restart до сохранения = в Sheets state.work остаётся active → reload web попробует финализировать снова, но это будет ПЕРВЫЙ commit (никакого double).

**Known minor issue (deferred 4.48.5.1.1):** `Adventure.adventure_check_done` фаерит `log_event('adventure_done')` и `log_event('drop')` ВНУТРИ себя, ДО save. При STALE rollback'е эти entries остаются в history. Не критично (history fail-resistant noise), но не 100% чисто. Fix — refactor adventure_check_done чтобы log_event вызывался ПОСЛЕ save commit (через callback или return-value pattern).

**Тесты:** 6 новых (3 STALE rollback + 1 OK happy-path для adventure + 2 endpoint tests для full-page и fragment STALE). 1 existing test обновлён (mock возвращает "OK" явно). 1051 passed total, mypy 0 issues (68 source files).

#### 4.48.5.4. Critical: `load_meta` UNFORMATTED_VALUE — fix false-positive STALE `[H / XS / done (20.05.2026, 0.2.5d)]`

**Регрессия из 1.4.3 (0.2.5):** новый JSON-blob layout пишет `last_modified` (float) в ячейку A1. Sheets применяет дефолтное "Number" форматирование (без decimals), display value округляется до integer. `load_meta` использовала `ws.acell('A1').value` который возвращает **FORMATTED** display string — `'1779300151'` вместо реального `1779300150.71383`. Потеря ~0.3 сек > 0.01 epsilon → **ложный STALE на каждом save после паузы 200+ мс**.

**Симптом:** игрок видит STALE prompt `(diff пустой — race condition без явных изменений)` при любом save через несколько секунд после успешного `s`. Воспроизводилось стабильно (заметил Oleksii, инцидент 20.05.2026).

**Диагноз через direct Sheets query:**
```
A1 FORMATTED:   '1779300151'           ← display, rounded
A1 UNFORMATTED: 1779300150.71383       ← raw
B1 blob last_modified: 1779300150.71383 ← правильно
```

**Fix:** `ws.acell('A1', value_render_option=ValueRenderOption.unformatted).value` — возвращает float напрямую (без формат-округления). 1 тест обновлён, 1 regression test добавлен. 1057 passed.

**Альтернативы рассмотрены:** убрать форматирование с A1 в Sheets вручную (не reproducible, хрупко); хранить last_modified только в blob (теряем fast-path load_meta — раз; нарушает 4.54.2 архитектуру — два).

**Note:** в `load()` той же проблемы НЕТ — он читает blob B1 через JSON parsing с full precision.

#### 4.48.5.3. Защита от регрессии state.steps.today при save `[H / XS / done (20.05.2026, 0.2.5c)]`

**Реальный инцидент 20.05.2026:** игрок в CLI увидел STALE diff `steps.today: 2,878 → 2,171 (-707)` — Sheets откатился на меньшее значение чем CLI знал из max-merge'а steps_log.

**Root cause:** web RAM содержал устаревший state.steps.today=2,171 (web load был ДО появления entry 2,878 в steps_log). `apply_steps_log_max_merge` запускается ТОЛЬКО в `try_reload_state` на GET /, не на каждом mutation endpoint. Когда web mutation запустила `persist_state_to_cloud` → save_safe записала stale value поверх свежего в Sheets. Optimistic concurrency (4.54) не помогла — web корректно прошёл pre-check, просто записал stale value со свежим last_modified.

**Fix A (Variant A per design discussion):** в `save_characteristic` ПЕРЕД формированием state_dict вызывается `apply_steps_log_max_merge(game.state)` — гарантия что любой save пишет в Sheets текущий максимум по log'у. Реализация ~5 строк (импорт + вызов). Silent-fail если steps_log недоступен (offline-tolerance).

**Тесты:** 3 новых в `tests/test_characteristics.py` (max-merge before save / no regression when RAM higher / silent fail). 1056 passed. **Стоимость:** +1 Sheets API call (~500ms) на save.

**Альтернативы рассмотрены:** B (max-merge на каждом render — too expensive), C (helper в `_state_dict_to_blob_rows` — глубоко в репозитории), D (не сохранять steps_today в Sheets — большой refactor), E (auto-resolve STALE регрессии — прячет проблему).

#### 4.48.5.2. Navigation overlay при F5 / pull-to-refresh `[L / XS / done (20.05.2026, 0.2.5b)]`

**Контекст:** игрок жаловался: «при заходе на web в новый день страница как будто зависает на 3-5 секунд». Объективно — `try_reload_state` делает 4 Sheets round-trip'а при rollover (load game_state + read steps_log + load_meta + save_safe write), total 3.5-5 сек. Native browser spinner на iPhone Safari еле виден.

**Реализация (20.05.2026, 0.2.5b, Variant B per design discussion):** Client-side overlay с day-specific сообщением.

1. Переиспользован существующий `#save-overlay` (был только для HTMX requests) — новое CSS правило `body.navigating #save-overlay { opacity: 1; transition: none; }` для instant показа (без 150ms delay).
2. `<span>` в overlay получил `id="save-overlay-text"` чтобы JS мог менять текст контекстуально.
3. `beforeunload` handler — устанавливает текст: «🌅 Новый день — обновляем счётчики...» если `localStorage.lastSeenDate !== today`, иначе «Загрузка...». Затем `body.classList.add("navigating")`.
4. `DOMContentLoaded` handler — обновляет `localStorage.lastSeenDate` на сегодня для следующего сравнения.
5. **Без backend изменений** — чисто UX-fix.

**Tradeoff:** в обычный день F5 теперь тоже показывает overlay с «Загрузка...» (~2 сек) — небольшая регрессия для нормальных дней, но компенсация в день смены значительно перевешивает.

**Тесты:** 2 новых (`test_dashboard_has_navigation_overlay_handler` + `test_dashboard_has_navigating_overlay_css_rule`). 1053 passed.

##### 4.48.5.1.1. Deferred log_event в Adventure финализаторе `[L / XS / todo (опциональное продолжение 4.48.5.1)]`

**Контекст:** `Adventure.adventure_check_done` (`adventure.py`) фаерит `log_event('adventure_done')` и `log_event('drop')` ВНУТРИ себя, ДО save. При STALE rollback'е в `_finalize_adventure_with_drop_capture` (4.48.5.1) эти entries остаются в `history.jsonl` / Sheets `history` лист — phantom события которые не отражают реального state.

**Минорно:** history — fail-resistant noise по дизайну (entries никогда не блокируют gameplay). Phantom drop/adventure_done entries — косметический мусор в логах, не gameplay impact. Возможно когда-то будут влиять на дешборды (4.10) или streak-counter logic — тогда придётся чистить.

**Решение:**
1. Refactor `Adventure.adventure_check_done` — возвращать tuple `(adv_done_payload, drop_payload)` вместо internal log_event. Caller вызывает `log_event('adventure_done', **adv_done_payload)` + `log_event('drop', **drop_payload)` ПОСЛЕ save commit.
2. CLI caller (`functions.py:status_bar`) и web wrapper (`_finalize_adventure_with_drop_capture`) обновить под новый return shape.
3. Тесты — добавить assertion «log_event не фаерится при STALE rollback».

**Effort:** XS (~20-30 строк refactor + 1 тест). **Trigger:** появятся реальные следствия phantom entries (например 4.10 dashboards считают неверный drop rate) — тогда стоит закрывать.

#### 4.48.6. Web: Inventory + Equipment `[M / M / done (19.05.2026, 0.2.4u)]`

- Просмотр инвентаря, продажа (`POST /api/inventory/sell`).
- Equipment слоты, надевание/снятие (`POST /api/equipment/wear`, `/unwear`).

**Реализовано (19.05.2026, 0.2.4u):**
- 6 endpoints (3 Form + 3 JSON pair): `/web|api/inventory/sell` + `/web|api/equipment/wear` + `/web|api/equipment/unwear`. Все через `_persist_and_handle_stale` (STALE 409 на concurrent save).
- Pydantic models: `InventorySellRequest(index)`, `EquipmentWearRequest(inventory_index, slot_attr?)`, `EquipmentUnwearRequest(slot_attr)`. Для ring `slot_attr` обязателен (explicit «finger_01» / «finger_02»), для non-ring опционален (auto-determined из `_ITEM_TYPE_TO_SLOTS`).
- Pre-computed views: `_build_inventory_view(state, sort_key)` (items + sort_options dropdown + trader-applied sell_price + eligible_slots), `_build_equipment_view(state)` (slots с can_unequip + block_reason для tooltip).
- `_sort_inventory_view(inventory, sort_key)` — 4 опции (default/grade/price/bonus), возвращает `[(orig_index, item)]` чтобы wear/sell оперировали на оригинальном state.inventory.
- UI: inline always-visible buttons на каждой строке (pattern из 4.50.2 sell-existing). Ring → 2 кнопки «На палец 1» / «На палец 2». Non-ring → 1 «🧥 Надеть». Все с `hx-confirm`. Auto-swap при занятом слоте (как в CLI).
- Sort dropdown в Inventory секции — server-side `<select onchange="this.form.submit()">`. Hidden `sort` input в mutation формах preserves выбор через HTMX swap. GET / принимает `?sort=key` query param.
- Capacity check для unwear: если `inventory_full` → кнопка disabled + warning «⚠ Рюкзак полон» в конце Equipment блока.
- Trader skill (4.28) применяется к sell price display через `bonus.apply_trader`.
- 42 новых теста (`tests/test_web_main.py`). 909 passed, mypy 0 issues.
- **Разблокирует 4.63.3** Web для optimizer + presets — все wear/unwear endpoints доступны.

#### 4.48.7. Web: Shop `[M / M / todo (blocked by 4.7, 4.48.0)]`

- После доделывания Shop в CLI (4.7).
- Food / Clothes / Equipment / Sell — те же категории, что и в CLI.

#### 4.48.8. Web: Level + skill point allocation `[M / S / done (0.2.1d)]`

- Меню распределения `state.char_level.up_skills` между 4 навыками (Stamina / Energy Max / Speed / Luck) реализовано как новая `<section id="skills">` в `_status_fragment.html`, видимая только когда `up_skills > 0`. Свёрнута по умолчанию. Каждый клик = +1 к навыку, подтверждение через `hx-confirm` (нативный browser confirm). Без возможности отмены — соответствует CLI (`level.menu_skill_point_allocation`).
- 2 endpoint'а: `POST /web/level/allocate` (Form → HTML fragment) и `POST /api/level/allocate` (JSON через Pydantic `SkillAllocateRequest`). Общий helper `_validate_and_apply_skill_allocation(state, skill)` валидирует skill name + наличие очков, мутирует state, зовёт `persist_state_to_cloud`.
- **Prerequisite-фикс:** `_dashboard_context` теперь зовёт `CharLevel(state).update_level()` на каждом рендере. До 0.2.1d web-игрок никогда не апал level и не получал очков навыков (метод вызывался только из CLI `level_status_bar`). Persist делается только при фактическом level-up.

#### 4.48.9. Web: Банк (депозиты + кредиты) `[M / M / done (19.05.2026, 0.2.4w)]`

Web-зеркало CLI Bank меню (4.49). Сейчас локация Банка работает **только в CLI** — игрок не может управлять депозитами / кредитами через web. Эта задача восполняет gap, переиспользуя готовую pure-логику из `bank.py`.

**Контекст готовности:**
- ✅ `bank.py` (4.49) содержит полный набор pure mutation helpers: `_deposit`, `_deposit_all`, `_withdraw`, `_withdraw_all`, `_take_loan`, `_repay_loan`, `_repay_loan_all`, `accrue_deposit`, `accrue_loan`, gate helpers (`can_open_deposit`, `can_withdraw`, `can_take_loan`, `can_repay_loan`).
- ✅ Все 3 банк-навыка зарегистрированы в `_GYM_SKILL_DISPLAY` (banking_interest_rate / loan_capacity / loan_interest_reduction).
- ✅ Round-trip persist через flat-keys в state.

**Что нужно сделать:**

1. **Display layer** — новая секция `<section id="bank">` в `_status_fragment.html`:
   - Collapsed `<details>` по умолчанию.
   - Summary: `🏦 Банк (12,345.67 $ deposit / 5,000 $ loan)` или `🔒 Заблокирован — прокачай навыки` при skill=0.
   - Внутри 2 sub-блока (Депозит / Кредит), аналогичные CLI шапке.
   - Pre-computed данные через helper `_build_bank_view(state)`.

2. **Mutation endpoints** (7 Form + 7 API):
   - `POST /web/bank/deposit` (Form: amount) + `POST /api/bank/deposit` (JSON)
   - `POST /web/bank/deposit_all` + `POST /api/bank/deposit_all`
   - `POST /web/bank/withdraw` (Form: amount) + `POST /api/bank/withdraw`
   - `POST /web/bank/withdraw_all` + `POST /api/bank/withdraw_all`
   - `POST /web/bank/take_loan` (Form: amount) + `POST /api/bank/take_loan`
   - `POST /web/bank/repay_loan` (Form: amount) + `POST /api/bank/repay_loan`
   - `POST /web/bank/repay_all` + `POST /api/bank/repay_all`

3. **Pydantic models:**
   - `BankAmountRequest(amount: float, gt=0)` — для операций с суммой.
   - Endpoints без amount (`*_all`, `repay_all`) — без request body.

4. **Helpers в `web/main.py`:**
   - `_validate_and_apply_bank_op(state, op_name, amount=None) -> Optional[str]` — единая точка валидации + delegation в `bank.py` helpers + `persist_state_to_cloud()`. Возвращает текст ошибки или None.
   - `_build_bank_view(state) -> dict` — pre-compute для шаблона: `{deposit, deposit_accrued_preview, loan, loan_accrued_preview, rate_deposit, rate_loan, max_loan, can_open_deposit, can_withdraw, can_take_loan, can_repay_loan, locked_reason}`.

5. **UI patterns (следуя 4.48.5 Work):**
   - `hx-confirm` на critical операциях: take_loan («Взять X $ под Y% годовых?»), withdraw_all («Снять всё (X $)?»), repay_all («Погасить весь долг (Y $)?»).
   - Disabled buttons при gate-блокировке — visual indication (как в Gym для locked navykov).
   - `bank_error` прокидывается через `_dashboard_context(bank_error=...)` для отображения сообщений.

6. **Auto-finalize на каждом render:**
   - `accrue_deposit(state)` + `accrue_loan(state)` в `_dashboard_context` (как `work_check_done`). Синхронизирует preview значения.
   - Persist **не делается** на render (как `energy_time_charge`) — следующая mutation подтянет snapshot.

7. **Тесты (по pattern 4.48.5 Work + 4.50.2 Drop UI):**
   - Render: bank section visible, summary форматирование, locked/unlocked states.
   - 7 web endpoints + 7 api endpoints — happy path + validation errors (insufficient funds, locked, zero amount).
   - `_validate_and_apply_bank_op` — все 7 ops × all error paths.
   - `_build_bank_view` — pre-compute correctness в разных states.
   - hx-confirm presence на critical операциях.

**Architecture pattern:** следует 4.48.5 (Work) — Form-data возвращают `_status_fragment.html` для HTMX swap, JSON endpoints возвращают snapshot dict. Reuse существующих helpers — никакой бизнес-логики в web layer.

**Effort:** **M** — основная логика в `bank.py` готова. Скоуп: ~14 endpoints + 2 helpers в web/main.py + 1 section в template + ~20-25 тестов. По объёму близко к 4.48.5 (Work) или 4.50.2 (Drop UI).

**Зависимости:**
- ✅ 4.49 (Bank CLI) — done.
- ✅ 4.48.1 (Dashboard) — done.
- ⚠ 4.49.2.2 (Auto-repay) — НЕ блокирует, может быть реализован позже как Web-toggle отдельно.

**Реализовано (19.05.2026, 0.2.4w):**
- 14 endpoints (7 web Form + 7 API JSON) для 7 ops: deposit / deposit_all / withdraw / withdraw_all / take_loan / repay_loan / repay_all.
- Single dispatcher `_validate_and_apply_bank_op(state, op_name, amount?)` с explicit pre-checks в каждой ветке для понятных error messages (skill gate / insufficient money / over-limit / no debt).
- Single Pydantic `BankAmountRequest(amount: int, gt=0)` для 4 amount-based API; `*_all` без body.
- `_build_bank_view(state)` pre-compute: deposit/loan + preview_amount (capitalized), rates, max_loan, loan_available, 4 can_* gate flags, locked_reason.
- **Auto-accrue в `_dashboard_context`** на каждом render (accrue_deposit + accrue_loan) — symmetric с CLI capitalize-on-change pattern.
- UI section между Gym и Бонусы (зафиксировано в дизайне). Summary inline показывает active deposit/loan суммы или 🔒 при locked. Депозит + Кредит sub-blocks с inline формами. Withdraw/Repay скрыты когда нет депозита/долга.
- Critical ops с `hx-confirm`: **take_loan с rate-инфо** в тексте, withdraw_all/repay_all с суммой.
- Locked-state messaging: при skill=0 показывается hint про прокачку Banking Interest Rate / Loan Capacity.
- 34 новых теста. 972 passed total, mypy 0 issues.
- **Web feature parity почти полная** — остался только Shop (4.48.7, blocked by 4.7).

---

### 4.49. Локация "Банк" — депозиты, кредиты (зонтичная) `[H / M / done in 0.2.2 (06.05.2026, 8 подзадач)]`

**Зонтичная завершена 13.05.2026** — основная функциональность Банка (депозиты + кредиты + 3 банк-навыка) реализована в версии 0.2.2 в течение 06.05.2026.

**Follow-up'ы (НЕ блокируют closure, вынесены в отдельные задачи):**
- **4.49.2.2** Auto-repay toggle — низкий приоритет, оставлен под номером 4.49.2.2 для traceability с зонтичной.
- **4.48.9** Web UI Банка — формальная подзадача в зонтичной 4.48 (Web Interface), не часть 4.49.

**Контекст:** в коде уже есть `locations.py:bank_location` — печатает "В разработке". Эта зонтичная наполняет локацию реальной экономикой: депозиты с пассивным доходом + кредиты с долговой нагрузкой. CLI-only на старте, web — отдельная задача 4.48.9 после стабилизации CLI.

**Дизайн (06.05.2026, обсуждение перед реализацией):**

- **Один депозит** (не множественные «вклады»). Top-up прибавляет к существующему телу.
- **Один кредит** (не множественные займы). Погашение — частичное / полное.
- **Recompute с capitalize-on-change**, НЕ lock-rate-at-open. Подробности — в каждой подзадаче.
- **Точность:** `state.bank.deposit_amount` хранится как `float`, отображается с двумя знаками в Bank меню. `state.money` остаётся `int`. Снятие: `floor(deposit_amount)` идёт в `state.money`, копейки остаются на депозите.
- **Ставки:** годовые. Депозит default = 0%, +1%/level навыка `banking_interest_rate`. Кредит default = 100%, -1%/level навыка `loan_interest_reduction`. Cap'ов нет.
- **Capitalize-on-change** — формула: перед любым событием, меняющим тело или ставку, начисляются накопленные проценты по ТЕКУЩЕЙ ставке за `elapsed = now - last_accrual_ts`. Триггеры: top-up, withdraw, апгрейд `banking_interest_rate` (хук в `skill_training_check_done`). Это даёт compound-interest эффект с капитализацией на событиях.
- **Кредитный gate:** новый навык `loan_capacity` (default = 0$, +100$/level). При skill=0 кредит недоступен. Cap = «лимит непогашенного долга», не lifetime.
- **Penalty:** только daily interest (растущий долг). Auto-repay из зарплаты — опциональный toggle, добавляется отдельной подзадачей. Никакого принудительного списания.

**Phasing (по запросу пользователя — депозиты сначала):**

```
Phase 0 (инфра)        → 4.49.0.0
Phase 1 (депозиты)     → 4.49.0.1, 4.49.0.2
Phase 2 (deposit skill)→ 4.49.1.0, 4.49.1.1
Phase 3 (loan capacity)→ 4.49.2.0
Phase 4 (кредиты)      → 4.49.2.1
Phase 5 (auto-repay)   → 4.49.2.2
Phase 6 (loan skill)   → 4.49.3
```

#### 4.49.0. Депозиты (зонтичная) `[H / M / todo]`

Базовая инфра + UI ввести/снять + live preview накопленных процентов. Без скиллов — все ставки = 0% (default).

##### 4.49.0.0. Bank infra: `BankState` dataclass + save/load `[H / S / done (0.2.2, 06.05.2026)]`

**Скоуп:**
1. Новый nested `BankState` в `state.py`: поля `deposit_amount: float = 0.0`, `deposit_last_accrual_ts: Optional[float] = None`. **Loan-поля не добавляются** — придут в Phase 4 (4.49.2.1).
2. `GameState` получает `bank: BankState = field(default_factory=BankState)`.
3. `default_new_game()` инициализирует `bank=BankState()`.
4. `to_dict()` сериализует `bank_deposit_amount` (float) и `bank_deposit_last_accrual_ts` (float | None) — flat-keys чтобы не ломать CSV-формат.
5. `from_dict()` восстанавливает `BankState` из flat-keys, дефолтит к `BankState()` при отсутствии (старые сейвы).

**Что НЕ делается:** `bank.py`, изменения в `locations.py`, какое-либо UI. Только state-слой.

**Тесты:**
- `tests/test_state.py` — расширить existing round-trip: `BankState()` со значениями (1234.56, 1700000000.0) → to_dict → from_dict → assert equal.
- Test «старый сейв без bank-keys» → BankState defaults применяются.

##### 4.49.0.1. Депозиты: внести / снять / preview (CLI меню) `[H / S / done (0.2.2, 06.05.2026)]`

**Реализация (06.05.2026):**

1. `state.py`:
   - `state.money: int → float` — чтобы копейки могли течь между кошельком и депозитом без потерь (`Снять всё` забирает дробную часть). Display везде кроме Bank — `f"{state.money:,.0f}"`.
   - `GymSkills.banking_interest_rate: int = 0` — добавлено сейчас (Phase 2 потом только подключит к Gym training-table + меню). +1 ключ в `to_dict` / `from_dict`.

2. Новый `bank.py`:
   - `accrue_deposit(state)` — pure mutation. Идемпотентна. No-op при amount=0 или ts=None. Защита от clock-skew (now < last_ts → обновить ts до now без отрицательных процентов).
   - `current_deposit_rate_pct(state)` — `state.gym.banking_interest_rate * 1.0`.
   - `preview_deposit_amount(state)` — pure, без мутации. Используется в шапке меню для показа «виртуального» остатка.
   - `_deposit(state, amount: int)` — accrue first, deduct from money, add to deposit. Overdraft / amount<=0 → False.
   - `_deposit_all(state)` — переносит ВЕСЬ кошелёк (включая копейки) на депозит. Симметричен `_withdraw_all`.
   - `_withdraw(state, amount: int)` — strict floor. Auto-promote отключён — если игрок ввёл `100` при остатке `100.42`, копейки остаются на депозите (для полного снятия — отдельная опция «Снять всё»).
   - `_withdraw_all(state)` — `state.money += deposit_amount` (включая копейки), `deposit_amount = 0.0`, `last_interest_ts = None`.
   - `bank_menu(state)` — UI loop с шапкой: кошелёк / депозит / ставка / накоплено-с-прошлой-капитализации (если > 0). 5 опций: «Внести / Внести всё / Снять / Снять всё / Назад». При ставке 0% — приписка «(прокачай навык в Спортзале)».

3. `locations.py:bank_location()` — заменён stub-print на `bank_menu(state)`.

4. Display rules: Bank меню — 2 знака; status_bar / shop / gym / adventure / web — `:,.0f` (целое + разделители тысяч). Обновлено в `adventure.py`, `gym.py`, `shop.py`, `web/main.py`, `web/templates/_status_fragment.html`.

**Тесты (`tests/test_bank.py`):** 31 новый тест — `current_deposit_rate_pct` (default / skill 5), `accrue_deposit` (no-op / 0% / 10%/1day / idempotent / clock-skew), `preview_deposit_amount` (no mutation / empty), `_deposit` (normal / overdraft / zero / top-up капитализирует first), `_deposit_all` (cents / empty), `_withdraw` (strict floor / partial / over / zero), `_withdraw_all` (cents / empty / clears ts), `bank_menu` UI flow (exit / deposit flow / invalid choice / zero-rate hint / nonzero-rate hint / invalid amount / overdraft message / withdraw_all flow / deposit_all flow). Один существующий тест в `test_locations.py` обновлён (bank_location теперь интерактивное меню — monkeypatch input='0'). 443 tests total pass.

**Что НЕ делалось:** интеграция с Gym training-table (Phase 2 / 4.49.1.0); хук accrue в `skill_training_check_done` (Phase 2 / 4.49.1.1); web UI Банка (4.48.9 потом).

##### 4.49.0.2. Gate: открытие и снятие депозита требуют skill ≥ 1 `[L / XS / done (0.2.2, 06.05.2026)]`

**Проблема:** до этой задачи игрок мог открыть депозит даже при `banking_interest_rate=0` — но при этом проценты не капали (0% годовых), и smysla во вложении не было. UX подсказывал лишь «прокачай навык в Спортзале», но не блокировал бессмысленную операцию.

**Решение (06.05.2026):** скилл стал полным геймплейным gate'ом для всех операций Bank. **Внести / Внести всё** заблокированы при `skill < 1`; **Снять / Снять всё** заблокированы при `skill < 1` ИЛИ `deposit_amount == 0` (запрос пользователя — консистентность UX и блокировка операций без смысла). Если skill упал до 0 (legacy / future prestige) — снятие тоже блокируется, игрок должен снова прокачать навык; жёсткий gate приоритетнее «спасения средств». В нормальном игровом flow игрок не теряет деньги — депозит можно открыть только после прокачки, а downgrade пока невозможен.

**Реализация:**
- Pure helper `bank.can_open_deposit(state) -> bool` = `state.gym.banking_interest_rate >= 1`.
- Pure helper `bank.can_withdraw(state) -> bool` = `can_open_deposit(state) and state.bank.deposit_amount > 0`.
- `_deposit` / `_deposit_all` — проверяют `can_open_deposit` первой строкой; при False возвращают False / 0.0 без мутаций.
- `_withdraw` / `_withdraw_all` — проверяют `can_withdraw` первой строкой; при False возвращают False / 0.0 без мутаций.
- UI:
  - Шапка `bank_menu` при skill=0 — строка `🔒 Банк заблокирован — прокачай навык до 1 уровня в Спортзале.`
  - Пункты меню префиксуются `🔒` независимо: `1. Внести` / `2. Внести всё` — при `not can_open_deposit`; `3. Снять` / `4. Снять всё` — при `not can_withdraw`.
  - Handler'ы `_do_*` — при skill=0 печатают `🔒 Банк заблокирован. Прокачай навык...` и возвращаются без prompt'а. При skill≥1 но `deposit=0` для withdraw'а — печатают `Депозит пуст — нечего снимать.` (без 🔒, это не gate а пустой остаток).

**Тесты:** 12 новых (can_open_deposit и can_withdraw по разным комбинациям skill / deposit, _deposit / _deposit_all blocked at skill=0, _withdraw / _withdraw_all blocked at skill=0, _withdraw blocked when deposit=0, UI shows lock at skill=0, no lock at skill=1, deposit attempt at skill=0 shows message). 9 существующих deposit/withdraw-тестов обновлены: добавлен `s.gym.banking_interest_rate = 1` для разблокировки + `monkeypatch.setattr(bank.time, 'time', lambda: 1000.0)` чтобы accrue_deposit не насчитал многолетние проценты по timestamp=1000.0 при skill=1 (раньше при skill=0 это работало без mock'а — accrue был no-op). All 458 tests pass, mypy 0 issues.

**Что НЕ делалось:** ослабление gate (например, разрешить вывести при skill=0 как «defensive recovery») — пользователь явно попросил полную консистентность gate'а.

#### 4.49.1. Skill `banking_interest_rate` (зонтичная) `[M / S / todo (blocked by 4.49.0)]`

##### 4.49.1.0. Gym-инфра нового навыка `[M / S / done (0.2.2, 06.05.2026)]`

**Реализация (06.05.2026):**
- Поле `banking_interest_rate: int = 0` уже добавлено в `GymSkills` ещё в Phase 0.1 (4.49.0.1). Здесь только подключение к UI.
- `_SKILL_DESCRIPTIONS` (gym.py): запись с title «Банковская ставка», body «Каждый уровень добавляет +1% к годовой ставке депозита в Банке.».
- `gym_menu skill_options`: пункт `'9'` (Банковская ставка). Стоимость шарится из общей `skill_training_table` — отдельная цена не нужна.
- `_GYM_SKILL_DISPLAY` (web/main.py): запись с иконкой 🏦, effect «+1 % к годовой ставке депозита», available=True. Web Gym 4.48.4 universal — 9-й навык подхватился без изменений шаблонов.

##### 4.49.1.1. Capitalize-on-skill-up + recompute интеграция `[M / S / done (0.2.2, 06.05.2026), затем undone — см. 4.49.1.2 ниже]`

**Реализация (06.05.2026):**
- Хук в `gym.skill_training_check_done(state)` — при `skill_name=='banking_interest_rate'` ПЕРЕД `setattr(state.gym, ...)` вызывается `accrue_deposit(state)` через lazy import (избегает циклов). Накопленные проценты идут по СТАРОЙ ставке за прошедший период, новая применяется только к будущим — compound interest с капитализацией на событиях, exploit «качнуть навык → бесплатные старые проценты» закрыт.
- 4 новых теста в test_bank.py: end-to-end сценарий 30+30 дней с upgrade посередине; хук НЕ срабатывает для других навыков; banking_interest_rate в _SKILL_DESCRIPTIONS и _GYM_SKILL_DISPLAY.
- 2 существующих теста в test_web_main.py обновлены под 9-й навык. All 447 tests pass, mypy 0 issues.

##### 4.49.1.2. Retro-bonus exploit ОТКРЫТ намеренно (откат 4.49.1.1) `[M / XS / done (0.2.4z, 20.05.2026)]`

**Полное обоснование design choice + numerical examples + maintainer warning** — см. `docs/bank_retro_bonus.md`.

**Контекст и мотивация:** игрок попросил намеренно открыть retro-bonus exploit для banking_interest_rate — стимул прокачивать скилл («открыл депозит → прокачал → собрал retro-проценты»). Симметрично уже существующему механизму в work / earnings_boost (4.23 — `state.work.salary` базовая, `apply_earnings_boost` применяется при финализации с текущим уровнем скилла; прокачал во время смены → ретроактивный бонус ко всем часам). До 0.2.4z Bank работал противоположно — closed exploit через capitalize-on-change. Теперь Bank и Work consistent: оба recompute с текущим уровнем.

**Реализация (20.05.2026):**
- Удалён 10-строчный if-блок в `gym.py:skill_training_check_done` (lines 315-324 в 0.2.4y) — больше нет специальной обработки `banking_interest_rate`. accrue срабатывает только на mutation (top-up / withdraw / take_loan / repay), при следующем accrue новая ставка применяется ретроактивно к накопленному с `last_interest_ts` периоду.
- Тест `test_skill_up_hook_capitalizes_at_old_rate_first` инвертирован → `test_skill_up_no_accrue_retro_bonus_applies` (проверяет что timestamp НЕ сдвигается на skill-up и retro-bonus реально применяется).
- Тест `test_skill_up_hook_does_not_fire_for_other_skills` оставлен без изменений (становится избыточным но служит regression защитой).
- 1020 passed total (без изменения количества тестов).

#### 4.49.2. Кредиты (зонтичная) `[M / M / todo (blocked by 4.49.0)]`

##### 4.49.2.0. Skills `loan_capacity` + `loan_interest_reduction` — Gym registration `[M / S / done (0.2.2, 06.05.2026)]`

Объединили два кредитных скилла (бывшая 4.49.3 — `loan_interest_reduction` — сюда влилась) в один шаг. Оба skills регистрируются в Gym ДО реализации кредитов (4.49.2.1) — это даёт игроку возможность начать прокачку заранее.

**Реализация (06.05.2026):**

1. `state.py:GymSkills`:
   - `loan_capacity: int = 0` — каждый уровень = +100 $ к максимальной сумме кредита (`max_loan = loan_capacity * 100`). Default 0 → кредит вообще недоступен (gate-механика).
   - `loan_interest_reduction: int = 0` — каждый уровень снижает годовую ставку кредита на 1% (от базовых 100%).
   - Round-trip: оба добавлены в `from_dict` (с default=0 для legacy) и `to_dict`.

2. `gym.py:_SKILL_DESCRIPTIONS`:
   - `loan_capacity`: title «Кредитный лимит», description «Каждый уровень добавляет +100 $ к максимальной сумме кредита.»
   - `loan_interest_reduction`: title «Снижение ставки по кредиту», description «Каждый уровень снижает годовую ставку кредита на 1% (от базовых 100%).»

3. `gym.py:gym_menu` skill_options: пункты `'10'` (loan_capacity) и `'11'` (loan_interest_reduction). Стоимость прокачки шарится из общей `skill_training_table`.

4. `web/main.py:_GYM_SKILL_DISPLAY`:
   - `loan_capacity`: icon 💳, effect «+100 $ к максимальной сумме кредита», available=True.
   - `loan_interest_reduction`: icon 📉, effect «−1 % к годовой ставке кредита», available=True.

5. **БЕЗ хука capitalize-on-skill-up для `loan_interest_reduction`** — это будет добавлено в 4.49.2.1 одновременно с `accrue_loan` (сейчас функции просто нет).

**Тесты:** 6 новых в test_bank.py — `loan_capacity` / `loan_interest_reduction` defaults, round-trip обоих, наличие в `_SKILL_DESCRIPTIONS` (с правильным текстом), наличие в `gym_menu` (pre-rendering меню), наличие в `_GYM_SKILL_DISPLAY` (icon / available). 2 существующих теста в test_web_main.py обновлены: `_returns_all_entries` (теперь 11 навыков), `nested_details` (1 внешний + 11 nested = 12). 2 теста в test_state.py обновлены (expected_keys включает 2 новых). All 464 tests pass, mypy 0 issues.

**Что НЕ делалось в этом шаге:** UI кредитов / mutation helpers / accrue_loan / хук capitalize-on-skill-up для loan_interest_reduction — всё в 4.49.2.1. Сейчас оба скилла прокачиваются через стандартный flow Gym, но не имеют игрового эффекта (loan-механики ещё нет).

##### 4.49.2.1. Кредиты: взять / погасить / ежедневные проценты `[M / M / done (0.2.2, 06.05.2026)]`

**Реализация (06.05.2026):**

1. `state.BankState` расширен: `loan_amount: float = 0.0`, `loan_last_interest_ts: Optional[float] = None`. Round-trip через flat-keys `bank_loan_amount` / `bank_loan_last_interest_ts`. Старые сейвы → defaults (0.0 / None).

2. `bank.py` — pure helpers:
   - `current_loan_rate_pct(state)` = `max(0.0, 100.0 - state.gym.loan_interest_reduction)` — default 100% годовых, clamp на 0 для skill > 100.
   - `max_loan(state)` = `state.gym.loan_capacity * 100`.
   - `can_take_loan(state)` = `max_loan > 0 AND loan_amount < max_loan`.
   - `can_repay_loan(state)` = `loan_amount > 0` (НЕ требует skill — игрок не должен застрять с долгом).
   - `accrue_loan(state)` — симметричен `accrue_deposit`. Идемпотентен. No-op при `loan_amount=0` или ts=None. Защита от clock-skew.
   - `preview_loan_amount(state)` — pure, без мутации.
   - `_take_loan(state, amount)` — accrue first; проверка cap (`loan_amount + amount <= max_loan`); `state.money += amount`, `loan_amount += amount`, set ts.
   - `_repay_loan(state, amount)` — accrue first; auto-promote: при `amount == ceil(loan_amount)` списываем точную float-сумму (`state.money -= loan_amount`), кредит закрывается. Иначе — strict integer (копейки на долге остаются). Reject при amount<=0 / нет долга / amount > ceil(loan) / state.money < amount.
   - `_repay_loan_all(state)` — accrue first; точное float-списание (`state.money -= loan_amount`), `loan_amount = 0`, ts = None. Reject при insufficient money.

3. UI (`_print_bank_header` + `bank_menu`):
   - Шапка имеет два блока — «Депозит» (как было) и «Кредит» (новый, всегда виден). Кредит показывает `💳 Кредит: X.XX / Y.YY $ (лимит)`, `📉 Ставка кред.: N% годовых`, `💢 Начислено: +X.XX $` (если accrued > 0). При `max_loan=0` — строка `🔒 Кредит заблокирован — прокачай "Кредитный лимит"...`.
   - Меню — две секции с разделителями `═══ Депозит ═══` и `═══ Кредит ═══`. 7 действий + `0. Назад`. `🔒` префиксы независимо для каждого блока (1+2 при !can_open_deposit, 3+4 при !can_withdraw, 5 при !can_take_loan, 6+7 при !can_repay_loan).
   - Handler `_do_take_loan` — confirmation prompt `"Взять {amount} $ под {rate}% годовых? (y/n)"` (двойное подтверждение для дорогой операции).
   - Handler `_do_repay_loan` — auto-promote message: `Кредит закрыт. Спасибо за пользование банком.` при X == ceil(loan); иначе остаток.
   - Handler `_do_repay_loan_all` — точное float-списание + сообщение «Кредит закрыт. Спасибо за пользование банком.»

4. Хук в `gym.skill_training_check_done`: при `skill_name=='loan_interest_reduction'` ПЕРЕД инкрементом вызывается `accrue_loan` (через lazy import). Симметрично хуку для `banking_interest_rate` — закрывает exploit «качнуть навык → накопленные проценты пересчитаются по новой ставке». **(Снят в 4.49.2.2 ниже, 20.05.2026.)**

**Тесты:** 35 новых в test_bank.py (current_loan_rate / max_loan / can_take/repay matrix, accrue_loan idempotent / 100% / no-op, preview no-mutation, _take_loan blocked at skill=0 / normal / cap respect / zero, _repay_loan partial / auto-promote at ceil / over reject / insufficient / no debt / zero, _repay_loan_all exact float / insufficient / no debt, hook capitalize on skill-up для loan_interest_reduction / not on other skills, UI shows credit section / unlocked / take confirmation flow / cancel / repay full message). 1 тест в test_state.py обновлён (expected_keys: +2 ключа). All 499 tests pass (464 + 35), mypy 0 issues.

##### 4.49.2.3. Retro-discount exploit ОТКРЫТ намеренно (откат хука loan_interest_reduction) `[M / XS / done (0.2.4z, 20.05.2026)]`

**Контекст:** парный к 4.49.1.2 (deposit retro-bonus). Игрок попросил намеренно открыть retro-DISCOUNT для кредита — стимул прокачивать `loan_interest_reduction` («взял кредит → прокачал → отдал меньше процентов»). Симметрично earnings_boost в work (4.23). До 0.2.4z hook закрывал exploit — capitalize по СТАРОЙ ставке перед инкрементом.

**Нумерация:** 4.49.2.2 уже занят (Auto-repay toggle, вынесен 13.05.2026 как deferred follow-up). Этой подзадаче присвоен 4.49.2.3 — следующий свободный номер в зонтичной.

**Реализация (20.05.2026):**
- В 4.49.1.2 удалён весь if-блок в `gym.skill_training_check_done` целиком — обе ветки (`banking_interest_rate` и `loan_interest_reduction`) одновременно. То есть фикс единый.
- Тест `test_skill_up_hook_for_loan_interest_reduction` инвертирован → `test_skill_up_no_accrue_for_loan_retro_discount` (проверяет что timestamp НЕ сдвигается на skill-up и retro-discount реально применяется при следующем accrue).
- Тест `test_skill_up_hook_does_not_affect_loan_for_other_skills` оставлен без изменений (regression защита).

##### 4.49.2.2. Auto-repay toggle: %-отчисление с зарплаты `[L / S / deferred follow-up (вынесена 13.05.2026 из зонтичной 4.49 для closure, номер сохранён для traceability)]`

**Не блокирует зонтичную 4.49** — вынесена как самостоятельный low-priority follow-up. Реализуется когда понадобится QoL-улучшение для игроков с активным кредитом.

Опциональный toggle в Bank меню. Игрок включает «отчислять X% с каждой зарплаты на погашение кредита». При выплате зарплаты в `work_check_done` — если toggle ON и `loan_amount > 0` — забрать `salary * X / 100`, отдать в `_repay_loan` (с `accrue_loan` под капотом). Принудительной блокировки зарплаты НЕТ — это user-controlled опция.

**Скоуп:**
1. `BankState`: `auto_repay_enabled: bool = False`, `auto_repay_pct: int = 20` (или TBD).
2. `bank_menu` — toggle опция и установка %.
3. Хук в `work.py:work_check_done(state)` — после крединга salary в state.money, если auto_repay включён — вызвать `_repay_loan(state, floor(salary * pct / 100))`.

#### 4.49.3. Skill `loan_interest_reduction` `[merged into 4.49.2.0 + 4.49.2.1 — done]`

**Объединено:** регистрация скилла в Gym переехала в **4.49.2.0** (вместе с `loan_capacity`). Хук capitalize-on-skill-up уйдёт в **4.49.2.1** одновременно с `accrue_loan`. Эта подзадача больше не самостоятельная.

---

### 4.50. Новый навык: Размер инвентаря / Backpack Skill (зонтичная) `[M / S / done in 0.2.4d (08.05.2026, all 3 phases)]`

Сейчас `state.inventory: list[dict]` без ограничений — эксплоит, игрок копит сотни предметов. Добавляем capacity + новый навык, расширяющий его.

**Дизайн (08.05.2026, обсуждение):**

#### Базовая концепция (зафиксировано)

- **Базовый размер:** 10 слотов для нового персонажа (`BASE_BACKPACK_CAPACITY = 10`).
- **Skill:** `backpack_skill` в `state.gym` (тематическое имя — про рюкзак). +1 слот за уровень.
- **Title в UI:** «Размер инвентаря».
- **Иконка:** 🎒 (рюкзак — symmetric с 🎒 Инвентарь в UI; путаница допустима — игрок ассоциирует skill с инвентарём).
- **Helper:** `bonus.backpack_capacity(state) -> int = BASE_BACKPACK_CAPACITY + state.gym.backpack_skill`. Pure, в `bonus.py` (рядом с другими helpers).
- **Прокачка:** общая `skill_training_table` (как все остальные навыки).
- **CLI пункт меню Gym:** `'15'` (после Обучения = 14).
- **Backwards-compat:** **Вариант A (хрустящая трактовка)** — если у игрока на момент введения capacity > base+skill → существующие items остаются, но новые НЕ добавляются. Игрок должен прокачать `backpack_skill` или продать что-то перед Adventure.

#### Поведение при полном рюкзаке — 3 точки

**(1) Adventure drop — interactive sell-and-keep flow** (выбор пользователя 08.05.2026)

При выпадении предмета, если рюкзак полон:
1. Печатается описание выпавшего предмета (как сейчас): grade / type / characteristic / bonus / quality / price.
2. Печатается **полный инвентарь** игрока с нумерацией и текущими ценами продажи.
3. Prompt: «Ваш рюкзак полон. Хотите сохранить новый предмет?» Пункты:
   - `1..N` — продать item с этим индексом за его price (refund в state.money), новый item занимает освободившийся слот.
   - `0` — отказаться от нового предмета (drop потерян).

При продаже старого предмета — money credit + log_event('item_sold', source='auto_make_room', refund=...) для трассировки.

**Edge case (web):** auto-finalize adventure через `_dashboard_context` → drop happens без интерактива. Возможные стратегии:
- **(A) Web: drop потерян автоматом** при full inventory + сообщение в last_reload / toast.
- (B) Web: defer auto-finalize если drop pending → adventure остаётся active, игрок должен зайти через CLI / явно нажать "Claim" в web.
- (C) Сохранить drop в `state.pending_drop` поле, CLI / web показывает на следующем заходе, игрок решает.

→ Решается при реализации web-части (sub-task 4.50.2). MVP CLI без web (см. подзадачи ниже).

**(2) Shop purchase — блокировка**

Если рюкзак полон → блокировка покупки с сообщением: «Рюкзак полон. Продайте что-то перед покупкой.» В web — кнопка disabled.

**(3) Equipment unwear — блокировка**

При снятии предмета: если рюкзак полон → блокировка: «Освободите слот в рюкзаке перед снятием экипировки.» Это **дополнительное правило**, обсужденное 08.05.2026 — игрок не может снять всё, если рюкзак полон.

**Edge case `_equip_from_inventory` (swap):** при замене экипировки `del inventory[index]` ОСВОБОЖДАЕТ слот, потом `append(prev_item)` ЗАНИМАЕТ его. **Net effect: 0**. Capacity-check НЕ должен блокировать swap — иначе игрок не сможет менять экипировку при full inventory. Реализовать через временный inventory-decrement перед проверкой, ИЛИ вообще пропускать capacity-check в swap (он уже balanced).

#### Sheets / Save round-trip

- Поле `backpack_skill: int = 0` в `GymSkills` dataclass.
- `from_dict` / `to_dict` flat-key `backpack_skill`. Старые сейвы → 0 (ничего не теряется).

#### Декомпозиция на подзадачи

**4.50.0. Base capacity + skill registration + Shop/Unequip blocking** `[M / S / done in 0.2.4b (08.05.2026)]`
- `state.GymSkills.backpack_skill` + round-trip.
- `bonus.backpack_capacity(state)` helper.
- `gym.py:_SKILL_DESCRIPTIONS` + меню '15'.
- `web/main.py:_GYM_SKILL_DISPLAY` + icon 🎒.
- Capacity-check в `shop.py:_buy_item` (блокировка, return False).
- Capacity-check в `equipment.py:_unequip` (блокировка, return None + сообщение).
- Capacity-check в `equipment.py:_equip_from_inventory` (NET-zero swap — пропускаем check).
- CLI display: `inventory_view` header «Инвентарь (12/15)».
- Web display: `_status_fragment.html` — `🎒 Инвентарь (N/cap)`.
- Тесты — 8-10 новых.

**4.50.1. Drop interactive sell-and-keep flow (CLI)** `[M / M / done in 0.2.4c (08.05.2026)]`

При выпадении предмета в полный рюкзак — interactive prompt с **3 опциями**:
1. **Продать один из существующих предметов** (выбор по индексу) → existing item продаётся за price, освобождается слот, новый drop кладётся в этот слот.
2. **Продать сам найденный предмет** → новый item продаётся за свою price, существующий инвентарь не меняется.
3. **(Опционально skip)** — отказаться от обеих сделок (drop потерян). Edge case на случай если оба варианта неинтересны.

**Скоуп:**
- В `drop.py:item_collect` / `Adventure.adventure_check_done` — при `len(inventory) >= cap` НЕ append, а запустить interactive prompt.
- Helper `_handle_drop_full_inventory(state, new_item)` в drop.py: печать описания нового предмета + полный inventory с ценами + prompt с 2-3 опциями.
- Sell-existing → log_event с `source='auto_make_room'`. Sell-new → log_event с `source='auto_drop_sold'`.
- 5-7 тестов (full + sell existing / sell new / skip / pick worst item / pick best item).

**Архитектура для повторного использования в web (4.50.2):**

Logика «при full inventory не append, а сохранить в `state.pending_drop`» — общая. Adventure auto-finalize в `_dashboard_context` (web) и в CLI при следующем тике делают одно и то же:
- Если `len(inventory) < cap` → нормальный append (текущее поведение).
- Если `len(inventory) >= cap` → set `state.pending_drop = new_item` (вместо append), НЕ append.
- При следующем рендере (CLI status_bar / web dashboard) — показать «У вас есть pending drop, выберите что продать».
- CLI: prompt в Adventure menu / при заходе в инвентарь.
- Web: spec в 4.50.2.

Это потребует **новое поле `state.pending_drop: Optional[dict] = None`** + round-trip + UI в обоих интерфейсах.

**4.50.2. Drop при full inventory в Web** `[M / M / done in 0.2.4d (08.05.2026)]`

Тот же flow что в CLI (4.50.1) — UI в web для resolve pending drop:
- Dashboard показывает баннер «🎁 Pending drop: [grade item]. Выберите что продать.»
- При клике — раскрывается секция с тремя возможными действиями:
  1. Список inventory items с кнопкой «Продать за {price}» — выбор освобождает слот и добавляет drop.
  2. Кнопка «Продать новый предмет за {price}» — credit + clear pending_drop.
  3. (Опционально skip — выбросить новый предмет без денег.)
- POST endpoints: `/web/drop/sell_existing` (с inventory index), `/web/drop/sell_new`, `/web/drop/skip`.
- При успехе: state.pending_drop=None, persist_state_to_cloud, HTMX swap.
- 5-7 тестов на web flow + integration с auto-finalize.

**`state.pending_drop`** — общее поле для CLI и web, добавляется в 4.50.1.

#### Связь с другими

- **4.51** (Backpack item) — может стакаться с `backpack_skill`. Сейчас отложено.
- **4.7** (Дописать Shop) — capacity-check в Shop работает уже сейчас, но если Shop будет добавлять новые типы предметов — capacity-check уже на месте.

#### Версия

`0.2.4b` — мини-фича в рамках 0.2.4 (после earnings_boost / 4.23).

#### Effort

- 4.50.0 — **S** (базовая инфра + блокировки).
- 4.50.1 — **M** (interactive prompt + UX, нужно тестировать).
- 4.50.2 — **M** (web auto-finalize стратегия, может потребовать pending_drop поле).

**Зонтичная M/S — оставляем, основная нагрузка на 4.50.0 (S).**

---

### 4.51. Идея: Рюкзак — квестовый предмет со слотами `[L / M / todo (нужно обсудить)]`

**⚠️ Идея, требует обсуждения дизайна.**

Дополнение к навыку 4.50 (Inventory Capacity): помимо прокачки через Gym, можно получить **специальный предмет "Рюкзак"** (или несколько вариаций), который добавляет +N слотов к инвентарю. Получается через квест / достижение / редкий drop / покупку в Shop.

**Возможные вариации (для обсуждения):**
- **Малый рюкзак** (+5 слотов) — открывается за прохождение walk_15k 10 раз.
- **Средний рюкзак** (+10 слотов) — за достижение level 10.
- **Большой рюкзак** (+20 слотов) — редкий drop из walk_30k S+grade.
- **Туристический рюкзак** (+30 слотов) — финальная награда Story Mode (4.46).

**Открытые design-вопросы:**
1. **Это equipment-слот или просто item в инвентаре?**
   - Equipment-slot — рюкзак "надет" (новый слот, например, 8-й): даёт бонус только когда экипирован, можно снять / поменять.
   - Inventory-item — лежит в инвентаре, бонус активен пока есть. Странновато — рюкзак должен быть "на тебе", а не "в тебе".
   - Quest-flag — невидимый bonus, отдельное поле `state.backpacks: list[str]`. Самая простая модель.
2. **Стакается ли несколько рюкзаков?** Если можешь одеть только один — какой выбираешь? Если можешь иметь несколько — все плюсуются?
3. **Изнашивается ли?** Если equipment-слот — да (как другие предметы). Если quest-flag — нет.
4. **Можно ли потерять/продать?** Quest-предметы обычно не продаются.
5. **Связь с навыком 4.50:** стакается аддитивно (`capacity = base + skill_lvl + sum(backpacks_bonus)`)?

**Реализация:** зависит от выбранной модели. Самая простая (quest-flag):
- `state.backpacks: list[dict]` — список выданных рюкзаков с their `extra_slots`.
- `inventory_capacity(state)` суммирует все `state.backpacks[*]['extra_slots']` к навыку.
- Квестовая логика выдачи — отдельная задача (связана с 4.4 Achievements / 4.5 Quests / 4.46 Story Mode).

**Effort:** M (с учётом design-обсуждения и связей с системой квестов).

**Зависимость:** **4.50** (без базовой capacity-механики не имеет смысла) + **4.4 / 4.5 / 4.46** (нужна система квестов или достижений для выдачи рюкзаков).

---

### 4.53. Multi-user support `[H / L+ / todo (отложено — blocked by storage restructure)]`

**Архитектурная подсказка после 1.2 (01.05.2026):** в `characteristics.py` уже есть container `game = _GameContainer()` с атрибутом `state`. Расширение до multi-user — заменить `state` на `states: dict[str, GameState]`, добавить `init_game_state(user_id, state=None)`, в FastAPI handlers резолвить `user_id` из session/JWT.

User accounts, регистрация, логин. Per-user state в Sheets (отдельные листы или columns) или миграция на БД (SQLite/Postgres).

**Что нужно:**
- Auth: JWT или session cookies.
- Регистрация / логин.
- Per-user изоляция данных.
- Возможно — лидерборды (если несколько игроков).

**Blocker — переразметка хранения (15.05.2026):**

Текущая структура `game_state` в Sheets хранит **один state в одной таблице** (Key/Value layout без `user_id`). Это baked-in single-user assumption. Перед реализацией auth/login **обязательно** провести storage-restructure:

| Сейчас | Должно стать |
|---|---|
| `game_state` лист — один state, фиксированные ключи | `game_state_<user_id>` per-user (отдельный лист на пользователя) ИЛИ единый лист с колонкой `user_id` как partition key ИЛИ миграция на SQLite/Postgres |
| `steps_log` — уже имеет `user_id` колонку (с 4.14) ✅ | Без изменений — фильтрация при load_for_day |
| `history` лист — уже имеет `user_id` (с 4.6) ✅ | Без изменений — фильтрация на чтении |
| `history.jsonl` локальный — одного общий файл | Per-user: `history_<user_id>.jsonl` ИЛИ единый файл с фильтрацией на чтении |
| `characteristic.csv` — один файл, не имеет user_id | Per-user: `characteristic_<user_id>.csv` ИЛИ переход на БД и удаление CSV legacy fallback |

**Sync layer (4.54) остаётся valid per-user.** Optimistic timestamp variant A (которая будет реализована в 4.54) масштабируется автоматически — `last_modified` становится per-user полем в каждой строке user state'а. **Стратегия sync не переписывается** при переходе к multi-user, только scope становится per-user.

**Не нужны для multi-user (НЕ блокеры):**
- B (per-field merge) — нужно только если один user играет с 2+ девайсов синхронно.
- C (event sourcing) — нужно только при shared world / trade / marketplace, чего у нас не планируется.

**На данный момент (15.05.2026):** single-user assumption полностью valid. Достаточно sync через 4.54 (вариант A) + deploy через 4.48.0.1. Multi-user — это **отдельная архитектурная инициатива** (фактически переписывание persistence layer), запускается **только при появлении реального запроса** (друзья хотят играть, нужно несколько пользователей в одной инсталляции).

**Заблокировано:**
- 1.1 (GameState — должен поддерживать множественные инстансы) ✅ done.
- 4.48.0-4.48.5 базовые (single-user web должен работать первым).
- **NEW (15.05.2026): storage-restructure** — обязательно ДО auth/login. Это самостоятельная sub-задача (фактически 4.53.0 если будем разбивать).

**Дата:** не раньше, чем web для single-user стабилен и **только если возникнет реальный multi-user сценарий**. Большая фича, отдельная сессия / месяцы работы.

**Учитывать при реализации (08.05.2026):**
- **История действий (4.6)** — лог `history.jsonl` + Sheets `history` уже содержат поле `user_id` (сейчас всегда `"default"`). При переходе на multi-user: фильтровать события по `user_id` для отображения в CLI / web / dashboard. Sheets `history` лист содержит mixed события всех пользователей — нужна фильтрация на чтении. Local `history.jsonl` — каждый пользователь имеет свой файл (`history_<user_id>.jsonl`), либо один общий с фильтрацией.
- Аналогично для `steps_log` — поле `user_id` уже там (с задачи 4.14).

---

### 4.54. Sync resolution: CLI ↔ Web `[H / M / done (15.05.2026, 0.2.4p) → разблокирует 4.48.0.1]`

Решение конфликтов между CLI и web при одновременной игре.

**Текущая стратегия (в 4.48):** "last writer wins" + предположение, что игрок не использует одновременно. Достаточно для single-user, single-session.

**Эскалация (15.05.2026):** при попытке deploy web на постоянно работающий сервер (4.48.0.1) — становится реальным блокером. Сервер крутит web 24/7, любой запуск CLI на ноутбуке создаёт окно тихого overwrite'а (CLI с stale RAM-snapshot → `s`/`q` затирает прогресс с сервера). До решения 4.54 deploy невозможен без жёсткого правила «CLI больше не запускаем».

#### Зафиксированная стратегия (15.05.2026): Optimistic timestamp + snapshot-based diff

**Variant A — Optimistic concurrency.** Одно дополнительное поле `last_modified: float` (Unix timestamp) в Sheets. Перед каждым save — облегчённый pre-check: `Sheets.last_modified > state.last_loaded_at` → отказ (STALE) + human-readable diff'ом причин + 3 опции (Reload / Force-with-confirm / Cancel).

**Almost zero merge logic** — конфликты разрешает игрок вручную (через Reload + Redo). Это «fail loud, not silent» — приоритет safety над UX-удобством.

**Diff-семантика (Snapshot approach):** при `init_game_state()` снимаем deep-copy текущего state'а в runtime-only поле `state.last_loaded_snapshot: Optional[dict]` (не сериализуется, только в RAM). При STALE — load fresh Sheets, diff vs `last_loaded_snapshot` (а не vs current RAM!) — это показывает чистые «изменения на сервере с момента моего load'а», без mixing с моими незасейвленными правками. Snapshot обновляется при каждом успешном save.

#### Зафиксированные дизайн-решения (15.05.2026)

| # | Вопрос | Решение |
|---|---|---|
| 1 | Где живёт `last_modified` в Sheets | **A.** Новая Key/Value строка в существующей `game_state` таблице (`last_modified`), не отдельный sheet |
| 2 | Force-save в CLI | Давать, но с **двойным подтверждением** («Точно? Потеряешь N изменений с сервера. yes/no») |
| 3 | STALE в web UI | **Auto-reload через 2 сек с toast**, без модала, без выбора |
| 4 | Финализаторы web bump'ят `last_modified`? | **Да, обязательно** — финализаторы реально мутируют state (work_done +600$, skill upgrade и т.д.). CLI будет чаще ловить STALE «просто потому что время прошло» — это правильное поведение, diff покажет причину |
| 5 | Steps_log writes bump'ят `last_modified`? | **Нет** — steps_log append-only, max-merge на load сам разрешает. Не делаем лишних Sheets-запросов |
| 6 | Migration legacy saves | **Не нужна** — load возвращает `0.0` (epoch) для отсутствующего поля, первый save запишет реальный timestamp |
| 7 | Race window между `load_meta()` и `save()` | **Retry 1-2 раза** перед STALE, на повторном конфликте → STALE. Для single-player practically не возникает, но retry дёшев |
| 8 | Logging STALE events | **Да** — `log_event('sync_conflict', source='cli'/'web', diff_summary='...')` в history.jsonl для диагностики |
| 9 | Force-save в web UI | **Нет** — web только auto-reload без выбора (легко нажать случайно) |
| 10 | Web flash-toast verbosity | **Brief** — иконки и числа: `💰 +600 / 🏋 +1 skill / 🏭 смена окончена`. CLI prompt — detailed (полный список изменений с пояснениями) |
| 11 | Multi-tab в одном браузере | Не конфликт (общий uvicorn process, общий state в RAM). Фиксируем как факт. |

#### Архитектурный план

1. **Schema layer:**
   - `state.last_loaded_snapshot: Optional[dict] = None` (runtime-only, не в `to_dict()`).
   - Sheets `game_state`: новая строка `last_modified: float`.
   - `GameState.from_dict()` обновляется чтобы читать `last_modified` (default `0.0`).
   - `GameState.to_dict()` записывает `last_modified` (выставляется в `save_safe` перед write).

2. **Repo layer (`google_sheets_db.py`):**
   - `GameStateRepo.load_meta() -> float` — облегчённый запрос только `last_modified` ячейки. ~10x дешевле полного load'а.
   - `GameStateRepo.save_safe(state_dict, expected_last_modified) -> Literal["OK", "STALE"]` — pre-check + write новым timestamp'ом + retry на race.

3. **Diff helper (`sync_diff.py` новый файл):**
   - `diff_states(snapshot: dict, current: dict) -> dict[str, list[str]]` — возвращает структурированный diff по 11 категориям: money / steps / energy / gym (20 скиллов) / char_level / work / training / adventure / inventory / equipment / bank / date_last_enter.
   - `format_diff_cli(diff) -> str` — multi-line подробный для CLI prompt.
   - `format_diff_brief(diff) -> str` — single-line иконками для web toast.

4. **Persistence wrappers:**
   - `characteristics.save_characteristic()` — оборачивает `save_safe`, возвращает status. Старая сигнатура `() -> None` ломается → callers вверх по стеку обновляются.
   - `web/sync.persist_state_to_cloud()` — то же.
   - На `OK` обновляется `state.last_loaded_snapshot` (deep-copy текущего to_dict()).

5. **CLI integration (`game.py`):**
   - В main loop при `s`/`q` если save вернул STALE → `_show_stale_prompt(state, diff)`:
     - Печатает detailed diff (иконки + значения + объяснения per категория).
     - 3 опции: `[r] Reload`, `[f] Force` (требует второго подтверждения), `[c] Cancel`.
     - Reload → `init_game_state()` пере-инициализирует state из Sheets, обновляет snapshot.
     - Force → save_safe с `expected=None` (bypass check) + double confirm.
     - Cancel → продолжить без save, prompt появится при следующем save attempt.
   - log_event('sync_conflict', ...) после каждого STALE.

6. **Web integration (`web/main.py` + `_status_fragment.html`):**
   - Каждый mutation endpoint оборачивается: если `persist_state_to_cloud()` вернул STALE → возвращаем специальный response: HTML fragment с toast'ом + `HX-Refresh: true` (auto-reload через HTMX) ИЛИ `setTimeout(() => window.location.reload(), 2000)` на JS-стороне.
   - Toast template: «⚠️ Внешнее обновление: {brief_diff}. Перезагружаю...».
   - log_event('sync_conflict', source='web', ...) после каждого STALE.

7. **Тесты:**
   - `tests/test_sync_diff.py` (new) — unit-tests для diff_states по каждой категории (money/steps/gym/inventory/equipment/bank/date) + format_diff_cli / format_diff_brief.
   - `tests/test_save_safe.py` (new) — mock'нутый repo: OK на match, STALE на mismatch, retry на race-симуляции.
   - `tests/test_state.py` extend — round-trip `last_modified`, snapshot mechanism.
   - `tests/test_web_main.py` extend — endpoint возвращает STALE response при mock'нутом конфликте.

8. **Bake test:**
   - 1-2 дня реальной игры через web + occasional CLI на ноуте.
   - Проверить: STALE prompts появляются естественно, diff читается понятно, нет регрессий обычного flow.

**Effort:** **M** (~7-8 часов реальной работы, 8 коммитов).

**Зависимость:** ничем не блокирована, начинаем сразу. **Разблокирует 4.48.0.1 Deploy.**

**Дата:** **High приоритет** — перед 4.48.0.1 deploy на сервер.

#### 4.54.0. Минимальный sync CLI ↔ Web (read-only) `[H / S / done (01.05.2026)]`

**Контекст:** после 4.48.1 web-dashboard read-only показывает свой `game.state` в памяти uvicorn, инициализированный один раз в lifespan на старте процесса. Если в фоне поиграл в CLI и сохранился (`s`) — web не видит изменений до рестарта uvicorn. Это поверхностный фикс для read-only сценария; полная двусторонняя синхронизация — задача 4.54.

**Реализация (Вариант D):**
- **`GET /`** перед рендером дёргает `game.state.update_from_dict(GameStateRepo().load())`. Каждый F5 / pull-to-refresh / заход на главную → свежие данные из Sheets.
- **HTMX polling interval**: `every 15s` → `every 60s`. Активный фон не нагружает Sheets каждые 15 сек.
- **Update 0.2.0j (02.05.2026):** HTMX polling полностью отключён. Цифры обновляются только при F5 / pull-to-refresh / submit формы. JS-таймер активных сессий продолжает тикать раз в секунду на клиенте (без серверных запросов). Endpoint `GET /status` оставлен в коде для будущего использования (Refresh button — 4.54.0.1, action endpoints — 4.48.3+). Причина: данные на странице меняются редко (только при действиях игрока), таймеров на JS достаточно для UX.
- **`GET /status`** (HTMX-фрагмент) **НЕ** делает reload — обновляется из памяти.
- При сетевой ошибке во время reload — graceful degradation: оставляем кэшированный `game.state`, показываем badge "⚠️ Cloud sync failed at HH:MM:SS, showing cached" в шапке dashboard.
- Reload-логика — отдельный модуль `web/sync.py` с функцией `try_reload_state()` и dataclass'ом `ReloadStatus(ok, at, error)`.

**Без кнопки Refresh в этой задаче** — pull-to-refresh на iPhone и F5 на ноутбуке покрывают основной кейс. Кнопка — отдельная задача **4.54.0.1**.

**Тесты:**
- `GET /` дёргает `GameStateRepo.load()` (mocked).
- `GET /status` НЕ дёргает `GameStateRepo.load()`.
- Сетевая ошибка при reload → возврат 200 с предупреждением, не 500.
- HTMX `hx-trigger="every 60s"` присутствует в template.

**Версия:** `0.2.0g`.

#### 4.54.0.2. Day rollover detection в web `[M / S / done (0.2.1b)]`

**Контекст (02.05.2026, обнаружено при обсуждении 2.4; реализовано 03.05.2026 после симптома "новый день начался — web блокирует ввод свежих шагов"):** в CLI day rollover (смена даты, перенос `today → yesterday`, обновление `daily_bonus`) детектится в `save_game_date_last_enter(state)` на каждом тике main loop. До 0.2.1b в web этой проверки не было. Симптом: вчера CLI закрылся с `today=2478`, утром игрок открывает web → видит вчерашние 2478 → пытается ввести свежие 800 шагов с браслета → валидация `steps > today` отклоняет ("должно быть больше 2478"). Игрок вынужден запускать CLI чтобы тот сделал rollover, и только потом web заработает.

**Реализация (0.2.1b):**
- `_persist_state_to_cloud()` перенесён из `web/main.py` в `web/sync.py` (как `persist_state_to_cloud`) — чтобы `try_reload_state` мог звать его без циркулярного импорта.
- `web/sync.py:try_reload_state()` после успешного `update_from_dict` + `apply_steps_log_max_merge`: запоминает `old_date = state.date_last_enter`, зовёт `save_game_date_last_enter(state)`, и если дата изменилась — `persist_state_to_cloud()` (свежий день в Sheets+CSV+JSON).
- `web/main.py:_dashboard_context()` — defense-in-depth: тоже зовёт `save_game_date_last_enter(state)` (без persist — основной триггер в `try_reload_state`). Покрывает кейс когда GET /status / POST /web/work/* вызываются без F5 (через границу midnight на одной открытой вкладке).
- `web/main.py:_apply_new_steps()` — guard перед валидацией: вкладка не обязана была проходить через GET / (например POST /api/steps от iPhone Shortcut). Если фактический rollover произошёл — persist.
- Активные сессии (`state.work` / `state.training` / `state.adventure`) при rollover **не трогаем** — таймер просто едет через midnight, как в CLI. Реальная смена 23:30 + 2 часа должна корректно завершиться в 01:30, а не обрываться на полночи.

**Тесты (8 новых в test_web_main.py):** rollover-trigger в try_reload_state (со stale датой), no-rollover-no-persist (с актуальной датой), daily_bonus при rollover'е с 12k вчера, _apply_new_steps на свежий день со stale state (примет 800 после today=8000), persist после rollover в _apply_new_steps, _dashboard_context-guard (rollover на GET /status), форма после rollover показывает min="1", активная смена через midnight остаётся.

**Effort:** S (factual: helper move + ~6 строк rollover-кода + 8 тестов). Все 293 теста проходят. Smoke verified live.

#### 4.54.0.1. Кнопка "🔄 Refresh" на web dashboard `[L / S / todo]`

После 4.54.0 reload триггерится только при F5 / pull-to-refresh. Кнопка дополнила бы UX:
- В шапке dashboard (правый угол).
- При клике — full page reload (`<a href="/" role="button">`) или HTMX swap.
- Опциональный visual feedback (disabled state + spinner / "Refreshing..." текст).

Не критично — мобильный pull-to-refresh покрывает основной кейс. Делается, если решим что нажимать F5 на ноутбуке менее удобно.

#### 4.54.0.3. Smoke-test isolation: dry-run или test user_id для live API проверок `[M / S / todo]`

**Контекст (03.05.2026, обнаружено наутро после 0.2.1a/0.2.1b):** smoke-проверки live uvicorn'а через реальные `POST /api/work/start`, `POST /api/steps` и т.п. оставляют production-следы — записи попадают в `steps_log` и `game_state` Sheets под реальным `DEFAULT_USER_ID = 'alex'`. После двух раундов smoke-тестов (0.2.1a Work, 0.2.1b rollover) в `steps_log` за 03.05.2026 накопились артефакты: 5000, 500, 500, 5500, 500. Утром игрок открыл web — max-merge подтянул `today=5500`, `can_use ≈ 8580` (с бонусами), хотя реально за день пройдено только 280 шагов. Чтобы починить — пришлось вручную удалять строки через gspread + перезаписывать `game_state`. Это не баг кода, это прокол процесса smoke-тестирования.

**Опции:**
1. **`SMOKE_USER_ID` env var.** Smoke-скрипты выставляют `WEB_SMOKE_USER_ID=smoke_test`, и `_apply_new_steps` / `_validate_and_apply_work` / `StepsLogRepo.append` подхватывают этот override. Production остаётся под `'alex'`, smoke артефакты не пересекаются. Самый простой вариант, не ломает API.
2. **`X-Smoke-Test: true` HTTP header.** Endpoint смотрит на header'ы и переключается на in-memory state без записи в Sheets/log. Хорошо для CI, но требует ловли header'а в каждом mutation endpoint.
3. **Dry-run режим uvicorn'а.** Запуск через `WEB_DRY_RUN=1 uvicorn ...` — стартует с in-memory state без `try_reload_state` / без `persist_state_to_cloud` / без `StepsLogRepo.append`. Все mutation endpoint'ы возвращают честный ответ, но ничего не пишут в облако. Самый изолированный, но требует if-ов в нескольких местах.
4. **Отдельный smoke-spreadsheet.** `SPREADSHEET_ID` тоже env var; smoke-скрипты используют другой ID. Чистый namespace, но нужно поддерживать второй Sheet и migrate его при изменениях схемы.

**Предварительный выбор:** комбинация (1) + (4) — отдельный user_id для smoke, опционально + отдельный spreadsheet когда смок становится регулярным CI-шагом. Реализовать на момент начала работы над **4.48.6** или **4.48.3** (следующий мутирующий endpoint), чтобы сразу запускать новый код в безопасной песочнице.

**Effort:** S (~10 строк env-override + документация в docs/local_setup.md как запускать smoke).

**Не критично сейчас** — рукотворные smoke бывают редко (раз в релиз), но cost очистки реальный (мне пришлось удалять 5 строк gspread + перезаписать snapshot). Делается перед следующим большим mutation-фичей.

#### 4.54.1. Schema + last_modified + snapshot mechanism `[H / S / todo]`

- `GameState`: добавить `last_modified: float = 0.0` (сериализуется) и `last_loaded_snapshot: Optional[dict] = None` (runtime-only, `field(default=None, repr=False)` — НЕ в `to_dict`).
- `from_dict`: читать `last_modified`, default `0.0`.
- `to_dict`: писать `last_modified` (значение выставляется в save_safe перед serialize).
- Sheets `game_state`: добавить Key/Value строку `last_modified`. Migration: автоматически при первом save после deploy 4.54 — старые saves читаются с `last_modified=0.0`, новый save запишет реальный.
- `init_game_state()` (после успешного load) — обновляет `state.last_loaded_snapshot` через deep-copy `state.to_dict()`.

**Тесты:** round-trip с `last_modified`, snapshot создаётся при init, snapshot НЕ сериализуется в `to_dict()`.

#### 4.54.2. Core repo helpers: load_meta + save_safe `[H / S / todo (blocked by 4.54.1)]`

- `GameStateRepo.load_meta() -> float` — gspread call читает только ячейку `last_modified` (по координатам, без полного load). Default `0.0` если ключ отсутствует.
- `GameStateRepo.save_safe(state_dict, expected_last_modified) -> Literal["OK", "STALE"]`:
  1. `current = load_meta()`.
  2. Если `current > expected_last_modified` (with epsilon ~0.01 sec для float comparison) → return `"STALE"`.
  3. Иначе: `state_dict['last_modified'] = time.time()`, full save, return `"OK"`.
  4. **Retry 1 раз** при STALE если `current - expected < 5 sec` (предположительно race с другим save'ом в ту же микросекунду, retry с обновлённым `expected`).
- Test через mock'нутый gspread: OK на match / STALE на newer-version / retry на race.

#### 4.54.3. diff_states helper + format functions `[H / M / todo (blocked by 4.54.1)]`

- Новый модуль `sync_diff.py`:
  - `diff_states(snapshot: dict, current: dict) -> dict[str, list[DiffEntry]]` — структурированный diff по 11 категориям (money/steps/energy/gym/char_level/work/training/adventure/inventory/equipment/bank/date_last_enter).
  - `DiffEntry` — dataclass или TypedDict: `{field, old, new, delta?, hint?}`.
  - `format_diff_cli(diff) -> str` — multi-line для CLI prompt. Пример: `\n  💰 Wallet: 1,133.20 → 1,733.20 (+600.00, зарплата от смены)\n  🏋 Energy_Optimization_Gym: 3 → 4\n  📅 Day rollover: 2026-05-14 → 2026-05-15`.
  - `format_diff_brief(diff) -> str` — one-line для web toast. Пример: `💰 +600 / 🏋 +1 skill / 🏭 смена окончена / 📅 day rollover`.

**Тесты (`tests/test_sync_diff.py`):**
- Каждая из 11 категорий — happy diff + no-change.
- Edge cases: equipment swap (head: A → B), inventory remove (item не найден), bank deposit accrual.
- format_diff_cli / format_diff_brief — assert на ключевые иконки и числа.

#### 4.54.4. save_characteristic + persist_state_to_cloud wrappers `[H / S / todo (blocked by 4.54.2)]`

- `characteristics.save_characteristic()` — сигнатура `() -> Literal["OK", "STALE"]`:
  - Вызывает `GameStateRepo().save_safe(game.state.to_dict(), expected=game.state.last_modified)`.
  - На `OK`: обновляет `game.state.last_modified` и `game.state.last_loaded_snapshot`. Сейв в CSV.
  - На `STALE`: НЕ обновляет, возвращает `"STALE"` callerу.
- `web/sync.persist_state_to_cloud()` — аналогично.
- Все callers вверх по стеку обновляются для обработки нового return (где critical — `game.py` main loop, `web/main.py` mutation endpoints).

#### 4.54.5. CLI STALE prompt `[H / M / todo (blocked by 4.54.3, 4.54.4)]`

- В `game.py` main loop при `s`/`q` если save вернул `"STALE"`:
  - Загрузить fresh state из Sheets (но не применить к `game.state`).
  - `diff = diff_states(game.state.last_loaded_snapshot, fresh_dict)`.
  - Print: `format_diff_cli(diff)`.
  - Prompt: `\n[r] Reload (потерять свои несохранённые изменения)\n[f] Force overwrite (потерять серверные изменения выше)\n[c] Cancel (продолжить без save, prompt появится снова)\n>>> `.
  - Reload → `init_game_state()` (re-init из Sheets + новый snapshot).
  - Force → confirmation prompt («Точно перезаписать N изменений с сервера? yes/no»), на yes → save_safe с `expected=None` (bypass).
  - Cancel → return без mutation.
- `log_event('sync_conflict', source='cli', summary=format_diff_brief(diff), choice='reload'/'force'/'cancel')`.

#### 4.54.6. Web UI STALE flash + auto-reload `[H / M / todo (blocked by 4.54.3, 4.54.4)]`

- Web mutation endpoints (`_apply_new_steps`, `_validate_and_apply_work`, `_validate_and_apply_training`, и т.д.) — после `persist_state_to_cloud()`:
  - Если status `"STALE"` → load fresh, compute diff, return специальный fragment:
    ```html
    <div id="stale-toast">⚠️ Внешнее обновление: {brief_diff}. Перезагружаю...</div>
    <script>setTimeout(() => window.location.reload(), 2000);</script>
    ```
  - HX-swap на `body` или separate target.
- `log_event('sync_conflict', source='web', summary=format_diff_brief(diff), endpoint=path)`.

#### 4.54.7. Tests `[H / S / done (15.05.2026)]`

- 3 scenarios end-to-end (mocked gspread):
  1. **CLI победил**: CLI save → OK. Web load → видит изменения.
  2. **Web победил**: web save → OK. CLI save → STALE. CLI reload → видит изменения, redo save → OK.
  3. **Параллельные saves**: 2 process'а с одинаковым `expected` → один OK, второй STALE. (Тестим логику, не реальный thread race).
- Migration: legacy save без `last_modified` → load возвращает 0.0 → первый save = OK + ставит реальный timestamp.
- log_event sync_conflict записывается с правильным payload.

**Реализовано (15.05.2026):** новый `tests/test_sync_e2e.py` — 5 сценариев (последний параметризован 3× по choice → 7 test cases). Использует `FakeSheetsBackend` (in-memory dict, общий между «процессами») чтобы реальная логика `save_safe` / `load_meta` / `handle_stale_prompt` гонялась end-to-end без сети. Все unit-тесты низкого уровня (save_safe / load_meta / diff_states / handle_stale_prompt по отдельности) уже жили в `test_sheets_repo.py` / `test_sync_diff.py` / `test_characteristics.py` — здесь только composition.

**Побочно (та же дата):** в `tests/conftest.py` добавлен autouse fixture `_stub_steps_log_for_day` — мокает `StepsLogRepo.for_day` → `[]` для всех тестов кроме `test_sheets_repo.py` (тестирует сам repo) и `test_history.py`. До этого `test_handle_stale_prompt_reload` тратил 2.22 сек на реальный Sheets API call (Reload re-init'ил state → `init_game_state()` зовёт `apply_steps_log_max_merge()` → `StepsLogRepo().for_day()` — silent-fail catches all, поэтому не было видно). Тесты, которым нужно специфическое поведение for_day (`test_steps_max_merge`), переопределяют через свои `monkeypatch.setattr`. Suite ускорился с ~12.7 → ~6.3 сек.

#### 4.54.8. Bake test + docs `[H / XS / done (15.05.2026, 0.2.4p)]`

- 1-2 дня реальной игры через web + CLI.
- Проверить: STALE prompts появляются естественно, diff читается понятно, нет регрессий обычного flow.
- Обновить CLAUDE.md: заменить текущее предупреждение про CLI overwrite на новое поведение (теперь safe + STALE prompt).
- Обновить `docs/local_setup.md`: добавить раздел «Concurrent CLI ↔ web — sync через optimistic timestamp».
- log_event sync_conflict count за bake test → решение по будущим оптимизациям (если STALE слишком часто — может потребоваться доп. UX).

**Реализовано (15.05.2026, 0.2.4p):**
- CLAUDE.md абзац «CLI и web — отдельные процессы…» полностью переписан под optimistic concurrency: новое поведение + STALE prompt + log_event sync_conflict + объяснение почему старый «безопасный паттерн закрывать CLI без сохранения» больше не нужен.
- docs/local_setup.md — старая фраза «В MVP запускаем что-то одно за раз» убрана. Добавлен новый раздел «Concurrent CLI ↔ web — sync через optimistic timestamp» (~50 строк): механика last_modified + snapshot, пример CLI prompt'а с реальным diff'ом, описание web behaviour (auto-reload через 2 сек), формат log_event sync_conflict, edge cases (steps_log не bumpит / multi-tab не конфликт / разные машины с теми же credentials), рекомендации (F5 в web после CLI / `r` в CLI после web — экономит цикл «STALE → Reload → редо»).
- version.py 0.2.4o → 0.2.4p, changelog.txt — единая запись по всему 4.54 epic'у (включая краткий summary всех 8 substep'ов и побочный fix утечки тестов на StepsLogRepo).

**Bake test закрыт (15.05.2026):**
- Live verification: ноут (CLI) + iPhone (web) одновременно. Web сделал `+1ч` к смене Watchman → CLI на `s` показал ровно ожидаемый diff блок: `🏭 Work hours: 325 → 326`, `🏃 Доступно: -168`, `🏃 Использовано: +168`, `🏃 Total used: +168` (XP), `🏃 XP bonus: 2,204 → 2,212` (Inspiration accumulator), `🔋 Energy: -2`. Все 6 строк осмысленные — игрок сразу понимает причину (web сделал +1h) и все её последствия. UX подтверждён.
- Обратное направление (web toast после CLI save) запланировано к проверке в следующих живых сессиях — но архитектурно симметрично уже проверенному CLI prompt'у (тот же `format_diff_brief`, та же `_persist_and_handle_stale` логика, покрыты unit + e2e тестами в test_web_main и test_sync_e2e).
- Steps-only мутации через web корректно НЕ триггерят STALE (по дизайну — Q5 в фикс. решениях): write только в steps_log без бампа `last_modified`, max-merge на следующем load CLI/web подтянет до актуального. Подтверждено в более раннем прогоне: web +N → CLI `s` молча проходит → CLI restart показывает свежий steps. Данные не теряются.

**Follow-up watch (не блокер):**
- `grep '"sync_conflict"' history.jsonl | wc -l` за день — если >5/день стабильно, добавить auto-retry на quick race в save_safe (1-2 раза перед STALE при `current - expected < 5 sec`, было в исходном дизайне 4.54.2 retry-логики, в текущей реализации опущено для простоты).
- Минор UX: в `format_diff_cli` строка `🏃 XP bonus: 2,204 → 2,212` без явной дельты `(+8)`. Все остальные строки показывают delta. Можно унифицировать в follow-up'е, не блокер.

---

### 4.55. Auth для web `[M / S / todo (blocked by 4.48.1)]`

В MVP (4.48.x) URL публичный по IP:PORT. Auth добавляется отдельно — после стабилизации web.

**Варианты:**
- **HTTP Basic** — логин/пароль через браузерный диалог. Простой, без logout UX.
- **Session cookie + login form** — стандартная UX, чуть больше кода.
- **JWT** — обязательно для multi-user (4.53).

Для single-user (после 4.48 MVP) — **HTTP Basic** достаточен. Учётка хранится в env vars (`WEB_USER`, `WEB_PASS_HASH`).

---

### 4.56. Визуальная стилистика web: фоны локаций `[M / M / todo (обсуждение 12.05.2026)]`

Добавить «атмосферу» web-интерфейсу: общий фон дашборда + per-location фон, меняющийся при переходе в Gym / Adventure / Shop / Work / Bank / Home. Чисто эстетика, на геймплей не влияет, но повышает «погружение» когда играешь с телефона.

#### Обсуждение (12.05.2026)

**Главный вопрос — нужен ли Django.** Ответ: **нет**. FastAPI + Starlette уже отдают static файлы production-grade через `StaticFiles`. Картинки-фоны — это чисто CSS-задача, бэкенда менять почти не надо (~5 строк). Переход на Django был бы переписыванием всего (ORM, routing, templating) ради нулевого выигрыша.

**Сложность кода: низкая. Сложность ассетов: высокая.** Главная работа — нарисовать 6+ картинок в согласованном стиле. Это недели работы дизайнера или итерации генерации через Midjourney / SDXL / Sora с подбором промптов. Стилевая консистентность критична — иначе Gym будет в pixelart, Adventure в фотореализме, и игра «рассыплется».

#### План реализации

1. **Backend (5 минут):**
   ```python
   # web/main.py
   from fastapi.staticfiles import StaticFiles
   app.mount("/static", StaticFiles(directory="web/static"), name="static")
   ```
   Создать директорию `web/static/bg/` для ассетов.

2. **Body class по локации** в `web/templates/dashboard.html`:
   ```html
   <body class="loc-{{ state.loc }}">
   ```
   `state.loc` уже принимает `home / gym / shop / work / adventure / bank / garage / auto_dialer` — готовый дискриминатор без новых полей в state.

3. **Per-location CSS** (новый файл `web/static/styles.css`):
   ```css
   body { background-attachment: fixed; background-size: cover; background-position: center; }
   body.loc-home { background-image: url(/static/bg/home.webp); }
   body.loc-gym { background-image: url(/static/bg/gym.webp); }
   body.loc-adventure { background-image: url(/static/bg/adventure.webp); }
   body.loc-shop { background-image: url(/static/bg/shop.webp); }
   body.loc-work { background-image: url(/static/bg/work.webp); }
   body.loc-bank { background-image: url(/static/bg/bank.webp); }
   /* Overlay на article (Pico cards) для читабельности текста: */
   article { background: rgba(20, 20, 30, 0.85); backdrop-filter: blur(2px); }
   ```

4. **Подключить CSS в `dashboard.html`** — один тег `<link rel="stylesheet" href="/static/styles.css">` в `<head>`.

5. **Ассеты** — генерация через Midjourney / SDXL / Sora с единым промптом-стилем. Варианты стиля: cozy pixel-art, watercolor, dark fantasy, low-poly 3D render. Подобрать 1 раз — затем 6+ картинок в одинаковом стиле.

#### Подзадачи

**4.56.0. MVP без ассетов (CSS-градиенты)** `[L / S / todo]`
Дёшево проверить нужен ли вообще per-location фон. Backend mount + body class + 6 CSS-градиентов под локации (`linear-gradient(135deg, #1a2e3a, #0e1822)` под home, тёплые тона под Adventure, и т.д.). Без растровых картинок. Эффект сразу — атмосфера меняется при переходах. Если понравится — переходим к 4.56.1.

**4.56.1. Раcтровые фоны (artwork)** `[M / M / blocked by 4.56.0]`
Сгенерировать 6 BG-картинок в одном стиле, оптимизировать (WebP, ~300-500 KB каждая), подключить через CSS. Тестировать на iPhone (на 4G сеть).

**4.56.2. Responsive backgrounds + reduced-data** `[L / S / blocked by 4.56.1]`
Подключить `<picture>` с медиа-условиями для мобайла (отдельные узкие версии картинок) и `@media (prefers-reduced-data: reduce)` фоллбек на градиенты. Чтобы тяжёлые фоны не жрали трафик / батарею.

**4.56.3. Динамические эффекты (опционально)** `[L / M / todo]`
Идея: time-of-day (день / вечер / ночь по реальному времени), сезонность (зима / лето), погода. Расширяет ассет-бюджет ×2-4. Скорее «когда-нибудь», чем «next sprint».

#### Подводные камни

- **Mobile-first:** ты играешь с iPhone. Большие BG-картинки = трафик + батарея + RAM. Решение в 4.56.2 (WebP + responsive + `prefers-reduced-data`).
- **Контраст текста:** Pico-серый текст на пёстром фоне пропадает. Article-overlay `rgba(0,0,0,0.4-0.85) + backdrop-filter: blur` решает.
- **HTMX-swaps:** POST на `#status-bar` — body class не дёргается, фон стабилен, всё ок.
- **«Локации в web»:** сейчас web-UI «локация-агностичен» — статистика + действия независимо от `state.loc`. `state.loc` фактически всегда `home` в web-сценарии (или то что было перед закрытием CLI). Если хочешь чтобы фон менялся ПРИ переходе в Gym / Adventure — нужно ещё ввести «локации» в web (есть в task **4.48** как часть expand'а, либо отдельный sub-task для loc-switcher в UI). Сейчас можно начать с общего фона (один на всех) — это уже эстетика.

#### Связь с другими задачами

- **4.42 Locations с уникальной механикой** — там идея давать локациям не только визуал, но и геймплейные особенности (например, в Tavern регенерация быстрее). Если планируется 4.42 — фон станет естественной частью оттуда.
- **4.48 Web Interface** — текущая зонтичная. Сейчас web показывает всё на одной странице. Per-location переключение нужно сначала сделать тут.

#### Что НЕ делать

- **Django** — не нужен, не даст ничего полезного. FastAPI + Starlette закрывают static-serving.
- **Three.js / Canvas / WebGL** — другой жанр игры, преждевременно для текущей.
- **Parallax / heavy animations** — преждевременная оптимизация эстетики; сначала статика.

#### Effort и приоритет

- **Код**: S (1 час максимум для базового слоя).
- **Ассеты**: M-L в зависимости от качества (часы итерации с AI-генерацией → дни-недели если рисовать с дизайнером).
- **Total**: M если использовать AI-генерацию, L при ручном дизайне.

**Приоритет M** — не критично для игры, но даёт большой UX-уплифт когда web становится primary интерфейсом (после 4.48). Имеет смысл браться после стабилизации основной web-функциональности.

---

### 4.57. Equipment characteristic `'energy_regen'` (V2 для 4.21) `[M / M / todo (blocked by 4.21)]`

После задачи 4.21 (Speed split) Equipment не влияет на скорость regen — `energy_regen_skill` берёт бонус только из Gym + CharLevel. Эта задача добавляет поддержку Equipment-бонуса для regen через новый тип характеристики предметов.

**Что нужно сделать:**

1. **`drop.py:Drop_Item.characteristic_type`** — сейчас сэмплит 4 типа (stamina / energy_max / speed_skill / luck). Добавить 5-й: `'energy_regen'`. С равной вероятностью все 5 (или подкорректировать веса).

2. **`equipment_bonus.py`** — новая функция `equipment_energy_regen_bonus(state)` — суммирует bonus всех надетых предметов с `characteristic='energy_regen'`.

3. **`bonus.py:energy_regen_interval`** — добавить `equipment_energy_regen_bonus(state)` в сумму:
   ```python
   total = (state.gym.energy_regen_skill 
            + equipment_energy_regen_bonus(state)
            + state.char_level.skill_energy_regen)
   ```

4. **Web dashboard equipment bonuses display** — добавить отображение energy_regen бонуса от экипировки (рядом с stamina / energy_max / speed / luck).

5. **CLI char_info equipment display** — то же.

6. **Tests** — drop type sampling включает `'energy_regen'`, equipment_energy_regen_bonus работает, energy_regen_interval учитывает equipment.

**Зависимость:** blocked by 4.21 (нужен `energy_regen_skill` сначала).

**Backwards-compat:** существующие предметы с другими characteristic-типами не трогаем. Новые типы появляются только в новых drop'ах после релиза.

**Эффект:** игрок может найти предмет с `'energy_regen'` бонусом, надеть его → regen ускоряется. Симметрично с тем, как сейчас работает Speed bonus на длительность активностей.

**Effort:** M — нужно тронуть drop.py, equipment_bonus.py, bonus.py, web/main.py, CLI display, тесты.

---

### 4.58. Active buffs system (state + display + tick + integration) `[M / M / todo (14.05.2026, выделена из 4.7/4.40)]`

**Pre-requisite для 4.7.2** (бустеры в Shop). Выделена в отдельную задачу 14.05.2026 как big-фича — это не просто item, а целая механика временных эффектов с tick'ом, expiration, integration со всеми bonus/skill calculations.

**Контекст:** в игре есть permanent скиллы (Gym), bonuses от equipment, daily_bonus (за 10k+ шагов в день). НЕ хватает: **временных эффектов** — «Speed Boost на 30 минут», «×2 деньги на 2 часа», и т.д. Это база для бустеров из Shop (4.7.2) и потенциально других фич (achievements rewards, story events, и т.д.).

**Что нужно сделать:**

1. **`state.py`:**
   - Новый dataclass `Buff(type: str, value: float, end_ts: float)` или просто `dict[str, Any]`.
   - Поле `state.active_buffs: list[Buff] = field(default_factory=list)`.
   - Round-trip в save (CSV / JSON / Sheets через flat-key serialization).

2. **`bonus.py` — helpers:**
   - `get_active_buff(state, buff_type: str) -> Optional[Buff]` — возвращает активный buff заданного типа (если есть и не expired).
   - `expire_old_buffs(state) -> list[Buff]` — удаляет expired buffs, возвращает список удалённых (для логирования / уведомлений).
   - `apply_buff_multiplier(base, state, buff_type) -> float` — применяет multiplier от active buff к base value (для использования в skill calculations).

3. **Tick / expiration:**
   - `expire_old_buffs(state)` вызывается в `game.py` main loop tick (рядом с `auto_collect_pending_drop` и `energy_time_charge`).
   - Web — в `_dashboard_context()` (рядом с `work_check_done`).
   - Опционально: print «Buff expired: Speed Boost» при transition.

4. **Integration с existing systems** (где buff применяется):
   - **Speed Boost** → в `skill_bonus.speed_skill_equipment_and_level_bonus()` — добавить buff multiplier к total.
   - **Lucky Charm** → в `drop.current_luck()` — добавить временный luck bonus.
   - **Money Fever** → в `bonus.apply_earnings_boost()` или новый wrapper — ×2 к salary.
   - **XP Surge** → в `_effective_xp()` в `level.py` — multiplier к inspiration-bonus.

5. **Display:**
   - CLI `status_bar` — отдельная строка `🧪 Active buffs:` с list of active с countdown timer'ами.
   - Web — секция `<section id="buffs">` в `_status_fragment.html` (collapsed details).

6. **Tests:**
   - `Buff` round-trip.
   - `get_active_buff` — returns active / None for expired.
   - `expire_old_buffs` — removes expired, leaves active.
   - Integration: Speed Boost ускоряет активности; Lucky Charm повышает current_luck; Money Fever удваивает salary.
   - Edge: пустой active_buffs, дублирующие buffs (один тип несколько раз), buff с истёкшим end_ts.

**Зависимости:** не блокируется ничем. Сам блокирует 4.7.2 (бустеры Shop).

**Effort:** **M** — изолированный модуль, но интеграция в 3-4 разные точки calculation pipeline'а.

---

### 4.59. Кузница / Blacksmith (зонтичная — Repair + Crafting + Gems) `[M / L / todo (14.05.2026)]`

**Объединяет 4.26 (Repair Skill) + 4.38 (Crafting / Forging) + Gems system** в одну новую локацию. Концептуально это «обработка предметов» — естественная RPG-локация blacksmith из классических игр (Skyrim, D&D, Diablo). Симметрично с 4.49 / 4.50 — зонтичная с поэтапной реализацией.

**Дизайн (14.05.2026, обсуждение):**

| Решение | Выбор |
|---|---|
| Локация | **Новая отдельная** `forge_location` в `locations.py`. Garage остаётся garage'м. |
| Иконка локации | 🔨 (молот — тематически blacksmith) |
| Resources | Стандартные: шаги + энергия + деньги. Никаких новых ресурсов в V1 (gems — отдельная подзадача 4.59.3). |
| Skill count | **TBD** — обсудим в процессе. Возможные skill'ы экономии: шаги / золото / энергия в Кузнице (3 skill'а). Реализуем по частям. |
| UI | CLI первым, web — потом (по pattern 4.49 → 4.48.9). Меню Кузницы — 5 пунктов (3 для gems как stub'ы «В разработке»). |
| Версия | TBD при реализации каждой подзадачи. |

#### UI меню «🔨 Кузница» (для всех подзадач)

```
--- 🔨 Кузница 🔨 ---
Steps 🏃: N, Energy 🔋: M, Money 💰: K $

В кузнице можно:
    1. Отремонтировать предмет
    2. Улучшить Grade предмета
    3. Сделать дырку в предмете для камня (В разработке)
    4. Вставить камень в предмет (В разработке)
    5. Объединить камни (В разработке)
    0. Назад
```

Пункты 3-5 показывают «В разработке» до реализации 4.59.3 (gems).

#### Подзадачи

##### 4.59.0. Локация Forge: infra + меню `[M / S / done in 0.2.4m (14.05.2026)]`

- Новый `forge_location` в `locations.py` (аналогично `bank_location`).
- Иконка `🔨` в `icon_loc(state)`.
- Пункт меню в `game.py:location_selection` (например `9. 🔨 Кузница`).
- Каркас меню — 5 пунктов (3 как stub'ы «В разработке»).
- Новый модуль `forge.py` с `forge_menu(state)`.
- Skill регистрация в Gym menu — **отложена** до решения по skill count (TBD).

**Тесты:** новая локация резолвится, меню рендерится, stub-пункты не падают.

##### 4.59.1. Repair: восстановление quality `[M / M / done in 0.2.4n (14.05.2026)]`

**Объединяет старую задачу 4.26 (Repair Skill).** Восстанавливает `quality` предмета через траты шаги + золото + энергия.

**Cost формула (1 percentage point ремонта):**
```
1% quality = 1,000 шагов + 100 $ + 10 энергии
```

**Балансовая мотивация (зафиксировано 14.05.2026):** cost намеренно **дорогой для low-grade предметов** (C / B-grade) — игроку **выгоднее заменить** их дропом из Adventure, чем ремонтировать. Repair imeет смысл в основном для **S / S+ предметов**, которые редкие и дорого получить заново. **Никакого scale by grade в V1 не делаем** — пусть низкие grades экономически невыгодны для repair, это естественный gating механизм без дополнительной сложности кода.

**UX flow:**
1. Игрок выбирает в меню Кузницы `1. Отремонтировать предмет`.
2. Видит список **всех** equipment-предметов (надетые + в инвентаре), отсортированных по `100 - quality` desc (самые повреждённые сверху).
3. Выбирает предмет → видит preview:
   ```
   Helmet a-grade (quality: 67.5 / 100, repair cap: +32%)
   На полное восстановление нужно: 32,000 шагов + 3,200 $ + 320 энергии.
   Можешь восстановить: до 32% (хватает ресурсов на 32%).
   ```
4. Вводит сколько процентов восстановить (1..max_по_ресурсам).
5. Списываются ресурсы пропорционально, `quality += chosen_percent`.

**Ограничения:**
- `max_quality = 100` (нельзя превысить).
- Если `quality == 100` — пункт меню в списке disabled / hidden.
- Расчёт `max_по_ресурсам = min(100 - current_quality, steps/1000, money/100, energy/10)`.
- Применимо ко **всем** equipment-предметам (надетые + в инвентаре) — игрок может выбрать любой.

**Архитектура:**
- Pure helper `forge.repair_cost(percent_to_repair) -> (steps, money, energy)`.
- Pure helper `forge.max_repair_percent(state, item) -> int` — min(100-quality, ресурсы//cost).
- Mutation `forge.repair_item(state, item_ref, percent)` — `try_spend` + `item['quality'][0] += percent` + `recalc_item_prices` (через существующий `Wear_Equipped_Items.recalc_item_prices`).
- Log_event `item_repaired` — payload: `item_type, grade, from_quality, to_quality, cost_steps, cost_money, cost_energy`.

**Skill экономии (опциональные, TBD при реализации):**
- 3 потенциальных skill'а — `forge_steps_saving`, `forge_money_saving`, `forge_energy_saving`. Аналогично money_saving / energy_optimization pattern (линейный -1%/level, clamp min=1).
- Эти же skill'ы будут применяться и к Crafting (4.59.2), и к Gem combining (4.59.3) — universal Forge resource savings.
- Решение по skill — после реализации базовой repair-механики. Сейчас MVP без skill'ов.

##### 4.59.2. Crafting: upgrade Grade (2 → 1) `[M / M / done in 0.2.4o (14.05.2026)]`

**Объединяет старую задачу 4.38 (Crafting / Forging).** Из двух **идентичных** предметов одного grade → один предмет следующего grade.

**Recipe (Variant A — строгая идентичность):**

Два source-предмета должны иметь:
- Тот же `item_type` (ring / necklace / helmet / shoes / t-shirt).
- Тот же `characteristic` (luck / stamina / speed_skill / energy_max).
- Тот же `grade` (c-grade / b-grade / a-grade / s-grade — не s+grade т.к. cap).

**Результат:**
- `grade` нового = next grade (c→b, b→a, a→s, s→s+).
- `bonus` = автоматически `Drop_Item.item_bonus_value(new_grade)` (т.е. c→1, b→2, a→3, s→4, s+→5).
- `quality` нового = `(quality_1 + quality_2) / 2` (среднее арифметическое).
- `price` пересчитан через `Drop_Item.item_price(new_grade, new_quality)`.
- `item_type` и `characteristic` наследуются (одинаковые у source).

**Cap:** s+grade → нельзя улучшить (уже max). UI блокирует.

**Success rate:** **100%** в V1 — не наказываем игрока. Failure mechanic (potential loss / partial refund / "осколки") — отложено в V2 если понадобится баланс.

**UX flow (зафиксировано 14.05.2026):**

1. Игрок выбирает `2. Улучшить Grade предмета` в меню Кузницы.

2. **Автоматическое сканирование** equipment + inventory — находим все группы `(item_type, characteristic, grade)` где count ≥ 2. Показываем список:
   ```
   --- 🔨 Улучшение предметов ---
   Доступно для улучшения:
   
   1. Ring b-grade luck (3 шт.) → Ring a-grade luck (+3)
      Cost: 2,000 шагов + 200 $ + 20 энергии
   
   2. Helmet b-grade stamina (5 шт.) → Helmet a-grade stamina (+3)
      Cost: 2,000 шагов + 200 $ + 20 энергии
   
   0. Назад
   ```

3. Игрок выбирает группу → переход к **выбору конкретных 2 предметов**:
   ```
   --- Выбери 2 предмета для крафта ---
   Cost: 2,000 шагов + 200 $ + 20 энергии (хватает: ✓)
   
   #  Quality  Sell price  Status
   1   95       190 $       🟢 finger_01 (надет)
   2   80       160 $       🟢 finger_02 (надет)
   3   60       120 $       инвентарь
   4   45        90 $       инвентарь
   5   30        60 $       инвентарь
   
   Введи 2 номера через запятую (например: 4,5)
   0. Назад
   > 
   ```
   - **Status колонка** показывает где предмет (надет / инвентарь). Если надет — указан слот (finger_01 / head / etc.) для ясности.
   - **Sell price** учитывает **`trader` skill** (4.28) — цена с применённым +%/level бонусом. Это даёт игроку контекст «сколько денег я мог бы получить если бы продал вместо крафта».
   - **Quality** оригинальное (не округлённое).

4. После выбора (например `4,5`) — preview:
   ```
   Ты выбрал:
   - #4 Helmet b-grade stamina (qual 45, inventory)
   - #5 Helmet b-grade stamina (qual 30, inventory)
   
   Результат: Helmet a-grade stamina +3
     quality = (45 + 30) / 2 = 37.5
     price ≈ 56 $ (с учётом trader skill)
   
   Cost: 2,000 шагов + 200 $ + 20 энергии
   
   ⚠️ Внимание: 0 из 2 предметов сейчас надеты.
   
   Подтвердить улучшение? Введи 'yes' для подтверждения:
   > 
   ```
   
   **Если выбраны equipped предметы — explicit warning:**
   ```
   ⚠️ ВНИМАНИЕ: 2 предмета сейчас надеты:
      - #1 finger_01 (Ring b-grade luck, qual 95)
      - #2 finger_02 (Ring b-grade luck, qual 80)
   
   После крафта оба слота (finger_01, finger_02) останутся пустыми
   — ты потеряешь бонус от обоих колец.
   
   Подтвердить улучшение? Введи 'yes' для подтверждения:
   > 
   ```
   
   **Mixed case (1 equipped + 1 inventory):**
   ```
   ⚠️ ВНИМАНИЕ: 1 предмет сейчас надет:
      - #1 head (Helmet b-grade stamina, qual 95)
   
   После крафта слот head останется пустым — ты потеряешь бонус.
   
   Подтвердить улучшение? Введи 'yes' для подтверждения:
   > 
   ```

5. **Explicit confirmation:** игрок должен ввести **`yes`** или `y` целиком (не просто Enter). Это защита от случайного `y` нажатия. Любой другой ввод → отмена операции.

6. После подтверждения:
   - `try_spend(state, steps, energy, money)` — атомарное списание ресурсов.
   - Snyatii equipped предметов (если есть) — `state.equipment.<slot> = None`.
   - Удаление source items из `state.inventory`.
   - Создание нового item (grade+1, quality avg, bonus from item_bonus_value, price from item_price).
   - Кладётся в `state.inventory` (НЕ auto-equip — игрок сам решает).
   - Log_event `item_crafted` — payload: `item_type, characteristic, from_grade, to_grade, qual_1, qual_2, new_quality, new_price, was_equipped: bool`.

**Тонкости:**
- **Inventory full check:** 2 in → 1 out → net inventory -1, всегда безопасно (никогда не overflow).
- **Equipped indicator visible на каждом этапе** — игрок не должен случайно крафтить надетые.
- **Sell price показан** для контекста — игрок может решить продать вместо крафта если price > value of upgrade.
- **Текстовое `yes` подтверждение** — защита от случайного `y` (особенно важно при autocomplete / muscle memory).

**Архитектура:**
- Pure helper `forge.find_craftable_pairs(state) -> list[dict]` — группирует, возвращает groups with count ≥ 2.
- Pure helper `forge.craft_item(state, group_key) -> dict` — выбирает 2 worst, удаляет, создаёт new, append в inventory. Mutation.
- Log_event `item_crafted` — payload: `item_type, characteristic, from_grade, to_grade, qual_1, qual_2, new_quality, new_price`.

**Cost (зафиксирован 14.05.2026):** линейный по grade tier — `cost = tier × (1000 шагов, 100 $, 10 эн)`, где tier(C)=1, tier(B)=2, tier(A)=3, tier(S)=4.

| Source grade → Result | Cost (шаги / $ / эн) |
|---|---|
| C → B | 1,000 / 100 / 10 |
| B → A | 2,000 / 200 / 20 |
| A → S | 3,000 / 300 / 30 |
| S → S+ | 4,000 / 400 / 40 |

**Расчёт «полного крафта» (от 16 C до 1 S+):**

| Стадия | Кол-во крафтов | Cost per craft | Subtotal |
|---|---|---|---|
| C → B | 8 | 1k/100/10 | 8,000 / 800 / 80 |
| B → A | 4 | 2k/200/20 | 8,000 / 800 / 80 |
| A → S | 2 | 3k/300/30 | 6,000 / 600 / 60 |
| S → S+ | 1 | 4k/400/40 | 4,000 / 400 / 40 |
| **Total** |   |   | **26,000 / $2,600 / 260** |

Это ~1 walk_30k worth of steps + значимые деньги/энергия. Плюс нужно иметь 16 идентичных C-grade items — это сам по себе grind через Adventure. **Баланс хороший** — крафт S+ это осмысленная цель, не free upgrade.

**Архитектура cost:**
- Helper `forge.crafting_cost(source_grade: str) -> tuple[int, int, int]` — pure, возвращает `(steps, money, energy)`.
- Использует константу `GRADE_TIER = {'c-grade': 1, 'b-grade': 2, 'a-grade': 3, 's-grade': 4, 's+grade': 5}` (s+grade нужен для cap-check).
- Тратится через `actions.try_spend(state, steps, energy, money)` перед merge.
- Skill'ы экономии (forge_*_saving — TBD) будут единообразно применяться через `apply_*` обёртки, симметрично с money_saving / energy_optimization pattern.

##### 4.59.3. Gems system `[L / L / todo (deferred — large sub-feature, blocked by 4.59.0)]`

**⚠️ Большая sub-фича, deferred с низким приоритетом.** Концепция inspired by Diablo 2 — камни как редкий ресурс, вставляются в предметы через сокеты для постоянного bonus'а.

**Дизайн (черновик):**

**Drop механика:**
- Gems — редкий drop из Adventure. **Не каждое приключение** — низкий probability (TBD, например 1-5%).
- Какие adventures дают gems — TBD. Возможные варианты:
  - Только walk_20k+ (high-tier).
  - Связано с luck — высокий luck открывает шанс gem.
  - Только в weekend (4.45 Weekend Quests).
  - Только из multi-day expeditions (4.46 Story Mode Phase 4 — Карпаты / Говерла).

**Grade камней (3 уровня):**
- 💎 **Small Gem** — базовый, выпадает из adventure.
- 💎💎 **Medium Gem** — создаётся combining (3 small → 1 medium).
- 💎💎💎 **Large Gem** — создаётся combining (3 medium → 1 large).

**Типы бонуса (3 вида):**
- 🔋 Energy gem — +N max energy при вставке.
- 🏃 Stamina gem — +N% к шагам при вставке.
- ⚡ Speed gem — +N% к скорости активностей при вставке.

(Можно расширить — luck, regen, money — но V1 ограничен 3 типами.)

**Combining (3→1):**
- 3 одинаковых gem'а (один type + один grade) → 1 gem уровнем выше того же type.
- 100% success rate.
- Cost — TBD (шаги/энергия/деньги через Forge resource savings skills).
- Cap = Large gem.

**Sockets механика:**
- Новое поле `item['sockets']: list[Optional[gem]]` — список сокетов с opt-gem'ом.
- Изначально предметы без сокетов (`sockets = []`).
- В Кузнице операция «Сделать дырку» — добавляет пустой socket к предмету. Cost — TBD (шаги/энергия/деньги, дорого).
- Cap по сокетам: максимум 3 на предмет? TBD.
- Операция «Вставить камень» — переносит gem из инвентаря в пустой socket.
- Извлечение gem'а из socket'а — TBD (обратимо или нет?).

**Integration с bonus calculations:**
- При надевании предмета с gem'ами — gem'ы добавляют bonus к equipment_*_bonus helpers.
- Например: ring с small energy gem → +1 energy_max в `equipment_energy_max_bonus`.

**Связи с другими задачами:**
- **4.45 Weekend Quests** — gems как rare reward за weekend Adventures.
- **4.46 Story Mode (Phase 3-4 — Карпаты / Говерла)** — gems как гарантированная награда за multi-day expeditions.
- **4.7.5 Косметика** — концептуально близка, но gems = mechanical, косметика = visual.
- **1.6 Items as dataclass** — желательно сделать ДО gems (поле `sockets`, `gems` лучше как typed dataclass поля).

**Подзадачи (когда возьмёмся):**
- 4.59.3.0 — Drop из Adventure (state поле `state.inventory_gems: list[Gem]`).
- 4.59.3.1 — Combining 3→1 UI.
- 4.59.3.2 — Sockets infra (`item['sockets']`) + UI «Сделать дырку».
- 4.59.3.3 — Insertion / extraction UI.
- 4.59.3.4 — Integration в equipment_*_bonus calculations.

**Effort всей gems sub-feature:** L (новая система с UI, state, bonus integration).

**Сложность баланса:** gems должны быть **очень редкими** (по запросу пользователя). На luck=0 — drop rate ≤ 1% за adventure. Combining требует 9 small → 1 large (3×3). На полный комплект экипировки с large gems нужно много grinding.

**TODO при реализации (open question):** подобрать конкретный drop rate gems из Adventure. Текущая оценка ≤ 1% при luck=0 — но это эвристика. Нужны **Monte-Carlo проходы** аналогично 4.29-replacement (compute_grade_probabilities) для тонкой настройки баланса: чтобы за 1 неделю игры собрать ~3-5 small gems (для combine в 1 medium), за месяц — 1 large gem. Учитывать влияние luck (повышает chance), weekend / multi-day expedition multipliers (4.45 / 4.46) — там drop rate выше. Это **критическое** balance decision — при правильной редкости gems становятся «event», при неправильной — либо мусор (слишком часто), либо недостижимы (слишком редко).

#### Effort всей зонтичной 4.59

**L** — три большие подзадачи (Repair M, Crafting M, Gems L) + infra (S). Реализация поэтапная, каждая подзадача — отдельный коммит. Без gems можно закрыть как M-effort (только repair + crafting + infra).

#### Архитектурные размышления

**Принципы реализации (для всех подзадач):**

1. **Pure helpers + thin UI.** По pattern Bank (4.49) и Shop (4.7) — бизнес-логика в `forge.py` pure-функциях, UI loop в `forge_menu(state)`. Это даёт легкую тестируемость и web-зеркало (когда дойдём до 4.48.X).

2. **Log_event для всех мутаций.** Каждая операция (repair / craft / combine / insert) — отдельный event_type. Это даёт history.jsonl track всех Forge-действий.

3. **Reuse existing helpers.**
   - `actions.try_spend` для списания шаги+энергия+деньги.
   - `Drop_Item.item_bonus_value` / `Drop_Item.item_price` для пересчёта при crafting.
   - `Wear_Equipped_Items.recalc_item_prices` после repair.
   - `bonus.inventory_full` check (хотя для crafting net negative, не нужно).

4. **Web mirror — отдельная задача (4.48.X).** Сейчас CLI-only. Когда CLI стабилизируется — добавим web версию по pattern 4.48.9 (Bank).

5. **Skills вынесем в конце.** Сначала MVP без skill'ов экономии. Потом, когда поймём как baseline баланс работает, добавим 3 skill'а (steps/money/energy saving) которые единообразно применяются ко всем операциям Forge.

#### Risks / Открытые вопросы

1. ~~**Repair баланс.** 1k шагов / 1% — это много для C-grade.~~ **Решено 14.05.2026:** оставляем как есть. Это намеренный gating — игроку выгоднее **заменить** low-grade предметы дропом, чем ремонтировать. Repair имеет смысл только для S/S+ (дорогие, редкие).

2. ~~**Crafting cost.** В V1 нет cost.~~ **Решено 14.05.2026:** линейный по grade tier — `tier × (1000 шагов / 100 $ / 10 эн)`. C→B 1k/100/10, B→A 2k/200/20, A→S 3k/300/30, S→S+ 4k/400/40. См. таблицу выше в 4.59.2. Полный крафт C→S+ ≈ 26k шагов / $2,600 / 260 эн + 16 идентичных C-grade items.

3. ~~**Crafting equipment auto-unequip.**~~ **Решено 14.05.2026:** auto-unequip с warning + explicit `yes` confirmation. Status equipped/inventory виден на каждом этапе UI. Полная UX-механика в 4.59.2 (см. UX flow).

4. ~~**Choice какие 2 из N.**~~ **Решено 14.05.2026:** **manual selection** (игрок сам выбирает 2 из всех кандидатов). Показывается quality + sell price (с учётом trader skill 4.28) для каждого. См. UX flow в 4.59.2.

5. ~~**Skills как они work**.~~ **Решено 14.05.2026:** в V1 **без skill'ов** — MVP базовой механики Forge без экономии. Skill'ы экономии (3 раздельных по pattern energy_optimization_*) — вынесены в **отдельную задачу 4.60** с low priority. Реализуем по мере необходимости после оценки баланса.

6. **Gem rarity tuning** ⚠ **TODO на момент реализации 4.59.3.** Drop rate gems из Adventure — нужно подобрать через Monte-Carlo проходы (аналогично 4.29-replacement / `compute_grade_probabilities`). Целевая «редкость»: ~3-5 small gems за неделю, ~1 large за месяц. Учитывать luck multiplier + weekend / multi-day expedition boost. **Критическое balance decision** — при правильной редкости gems становятся «event», при неправильной — мусор или недостижимы.

---

### 4.60. Forge resource saving skills (3 навыка экономии для Кузницы) `[L / S / todo (14.05.2026, выделена из 4.59 — реализация после MVP)]`

**Низкоприоритетный follow-up для 4.59.** В MVP Кузницы (4.59.0 / 4.59.1 / 4.59.2) — операции Repair и Crafting используют фиксированные cost'ы без skill'ов экономии. Эта задача добавляет 3 раздельных skill'а в pattern существующих `energy_optimization_*` / `move_optimization_*`.

**Решение реализовывать после MVP** — нужно сначала увидеть как baseline баланс Forge играется, потом подобрать формулу skill'ов чтобы не сломать экономику.

**Новые скиллы:**

- `forge_steps_saving` — `-1%/level` к **шагам** во всех Forge операциях (repair / crafting / gem combining / gem sockets).
- `forge_money_saving` — `-1%/level` к **золоту** во всех Forge операциях.
- `forge_energy_saving` — `-1%/level` к **энергии** во всех Forge операциях.

Все три по pattern `energy_optimization_*` (4.22):
- Линейная формула: `max(1, int(base × (1 − skill/100)))`.
- Clamp `min=1` (никогда не бесплатно).
- Match с existing reduction-skills (move_optimization / money_saving / energy_optimization).

**Реализация:**

1. **`state.GymSkills`** — 3 новых поля `forge_steps_saving / forge_money_saving / forge_energy_saving: int = 0` + round-trip.
2. **`bonus.py`** — 3 helper'а `apply_forge_steps_saving / apply_forge_money_saving / apply_forge_energy_saving(value, state) -> int`. Структурно идентичны `apply_energy_optimization_*`.
3. **`forge.py`** (из 4.59) — обернуть все cost-расчёты:
   - Repair: `repair_cost(percent)` → `(apply_forge_steps_saving(steps), apply_forge_money_saving(money), apply_forge_energy_saving(energy))`.
   - Crafting: то же на `crafting_cost(source_grade)`.
   - Gem combining (если 4.59.3 реализован): то же.
4. **Gym menu** — добавить 3 skill'а в `_SKILL_DESCRIPTIONS` + `gym_menu skill_options`. Position TBD (логично рядом с другими reduction skills — после `energy_optimization_*`).
5. **Web `_GYM_SKILL_DISPLAY`** — 3 entries с иконками 🔨🏃 / 🔨💰 / 🔨⚡ (или другие).

**Тесты:** sanity / linear / clamp min=1 / integration с Forge cost calculations. Аналогично test_bonus.py для energy_optimization_*.

**Effort:** **S** — паттерн знакомый, повторение existing pattern. Скоуп: 3 поля в state + 3 helper'а + 3 entries в Gym + tests.

**Зависимость:** blocked by 4.59.0 + 4.59.1 + 4.59.2 (нужны базовые Forge cost-расчёты которые потом обёртываются helper'ами). 4.59.3 (Gems) — не обязательное условие, можно подключить позже.

---

### 4.61. Поломка предметов: реальный эффект quality на gameplay `[L / M / done MVP (20.05.2026, 0.2.4x)]`

**Реализован MVP (20.05.2026, 0.2.4x) — binary cliff вместо ранее обсуждавшихся вариантов A-E:**
- **Quality > 0** → полный bonus (как раньше). **Quality == 0** → 0 bonus, предмет «сломан».
- Wear formula без изменений (100k шагов = -1% quality, neatness_in_using_things замедляет).
- Auto-unequip НЕ делается — broken остаётся в слоте, игрок решает.
- Migration: respect current quality (без free reset).
- Crafted items: avg(qualities) (4.59.2 без изменений).
- Visual feedback: status_bar warning при equipped < 20% quality (broken красный, low amber); «🔨 СЛОМАН» marker в Equipment menu/web с «+0» bonus.
- 19 новых тестов. 991 passed total, mypy 0 issues.

Решение MVP было «максимально упростить логику» (вместо обсуждавшихся ранее A/B/D/E variants). Tiered partial bonus вынесен в follow-up 4.61.1.

---

### 4.61 (ОРИГИНАЛЬНЫЙ ANALYSIS, для истории — оставлен ниже)

**Идея.** Сейчас quality предмета — почти косметика: визуальный индикатор + цена при продаже. На бонус характеристик и работоспособность экипировки quality **не влияет вообще**. Это значит, что Repair (4.59.1) экономически имеет смысл только если игрок планирует продавать предметы — для активной игры нет давления ремонтировать. Добавить «настоящую» механику поломки чтобы:

1. Дать смысл существующему скиллу `neatness_in_using_things` (сейчас он замедляет деградацию, которая ни на что не влияет).
2. Создать экономический pressure на Repair / Crafting в Кузнице.
3. Добавить новую механику игрового напряжения «следить за состоянием экипировки».

**Анализ текущего состояния (14.05.2026, что обнаружено при review 4.59):**

**Triggers износа** (списывается СРАЗУ при старте активности, не на завершении):
- `gym.py:298` — после `start_skill_training()`, передаёт `apply_move_optimization_gym(steps)`.
- `work.py:113` + `web/main.py:187` — после `check_requirements`, передаёт `hours × steps_per_hour` (**без** move_optimization!).
- `adventure.py:228` — после `_enter_adventure`, передаёт `adv_steps` (с move_optimization применённой в `Adventure.__init__`).
- `web/main.py:464` — Gym training через web (с оптимизацией).

**Формула износа** (`inventory.py:299-323`, класс `Wear_Equipped_Items`):
```
max_durability = 10_000_000  (константа)
neatness_factor = 1 - state.gym.neatness_in_using_things / 100
adjusted_steps = steps × neatness_factor

для каждого занятого слота equipment (7 слотов):
    item_durability = max_durability × (current_quality / 100)
    item_durability -= adjusted_steps
    if item_durability < 0: item_durability = 0   # clamp
    new_quality = (item_durability / max_durability) × 100
```

**Калибровка:** при `neatness = 0` каждые **100,000 шагов активности = −1% quality**. Полный износ 100→0% = **10М шагов активности**. На `neatness = 50` урон делится пополам; на `neatness = 100` экипировка не теряет quality вообще.

**Что quality реально влияет на (сейчас):**

| Влияет | НЕ влияет |
|---|---|
| `item['price']` после каждой активности (через `recalc_item_prices`) | `equipment_bonus`, `equipment_stamina_bonus`, `equipment_energy_max_bonus`, `equipment_speed_skill_bonus`, `equipment_luck_bonus` — все эти функции в `equipment_bonus.py` берут `item['bonus'][0]` НАПРЯМУЮ, **без чтения quality** |
| Sort key в `forge.repair_candidates` | Любые игровые расчёты (drop chance, energy regen, и т.д.) |
| Display: Inventory / Equipment / Forge menu | Auto-unequip / поломка / штраф — **отсутствует как класс** |

**Главный вывод анализа:** на `quality = 0` предмет **НЕ ломается, НЕ исчезает, НЕ снимается со слота** и **продолжает давать ПОЛНЫЙ бонус** к статам как новый. Сломанный `s+grade stamina-helmet` (qual=0, price=0) даёт те же `+5 stamina` что и новый. То есть никакой «поломки» в игре сейчас не существует.

**Варианты реализации поломки (для будущего обсуждения):**

| Вариант | Описание | Pros | Cons |
|---|---|---|---|
| **A — Linear penalty** | Бонус = `base_bonus × (quality / 100)`. На qual=0 → 0 эффективного бонуса. | Простая формула, плавная кривая | Серьёзно меняет баланс: игрок постоянно теряет бонус, нужно реремонтировать. |
| **B — Threshold cliff** | Бонус 100% пока `quality > threshold` (например 25), потом резко 0% / 50%. | Более прощающий — поломка только когда совсем плохо | Резкий перепад, игрок может «застрять» с broken-предметом неожиданно. |
| **C — Auto-unequip at 0** | Предмет работает на 100% до qual=0, потом **автоматически снимается** в инвентарь (или пропадает). | Чёткий event, ясный trigger | Сложно: что если инвентарь полон? Disrupt active session? |
| **D — Tiered penalty** | 100-75% → бонус 100%, 75-50% → 90%, 50-25% → 75%, 25-0% → 50%. | Компромисс A+B | Магические числа, нужно балансировать таблицу |
| **E — Smooth + soft floor** | `bonus × max(0.5, quality/100)` — даже сломанный даёт минимум 50% | Никогда не «бесполезный», но penalty виден | Может быть слишком мягко (broken = всё ещё OK) |

**Связи с другими задачами:**
- **4.59.1 Repair** — становится осмысленным: ремонт не «для перепродажи», а «для функциональности». Resource pressure растёт.
- **4.59.2 Crafting** — новый crafted предмет начинает с avg quality, что при variant A может быть болезненно (получил a-grade с qual 37 → 37% эффективности). Возможно нужен «полировка» (≈ Repair after Craft) или Crafting сразу даёт qual 100.
- **`neatness_in_using_things`** — наконец становится критически важным skill'ом.
- **1.6 Items as dataclass** — желательно сделать ДО этой задачи (рассчёт effective_bonus(item) cleaner на typed Item, чем на legacy dict).

**Открытые вопросы (для дизайн-сессии):**

1. Какой из вариантов A-E? **Не решено.**
2. Грэйс-период / migration: старые сейвы с qual=50 предметами — сразу теряют 50% бонуса (variant A) или есть grace? **Не решено.**
3. Adventure session-in-progress: если предмет «сломался» во время приключения, что происходит с финальной наградой? (износ списывается на старте — может стать sub-zero к концу). **Не решено.**
4. Visual feedback: warning в status_bar когда любой слот opasно низкий? **Не решено.**
5. Crafted предметы: avg quality (текущая логика) vs auto-100 quality после Crafting? **Не решено.**

**Эффорт:** **M** — формула в `equipment_bonus.py` + thread через все callers + миграция баланса (Stamina-калибровка может сдвинуться). Не тривиальная задача, нужна осторожная балансировка и тесты на economy regression.

**Зависимость:** **blocked by 4.59.1 Repair** (уже done в 0.2.4n — игрок должен иметь способ ремонтировать ДО введения поломки). Желательно после **1.6 Items as dataclass**.

---

#### 4.61.1. Tiered partial bonus для quality (post-MVP) `[L / S / todo (20.05.2026, follow-up к 4.61)]`

**Контекст.** 4.61 MVP (0.2.4x) ввёл **binary cliff**: quality > 0 → полный bonus, quality == 0 → 0 bonus. Игрок зафиксировал что в будущем хочет более плавную градацию. Эта подзадача — собрать данные о feel binary cliff после bake-test'а 4.61, потом ввести tiered penalty.

**Предлагаемая шкала (зафиксировано в дизайн-сессии 20.05.2026):**

| Quality | Бонус (% от full) | Психология |
|---|---|---|
| 75-100% | 100% | «Новый / в хорошем состоянии» — никакого штрафа |
| 25-75% | 75% | «Подношен» — заметный, но не критичный штраф |
| 0-25% (>0) | 50% | «Сильно повреждён» — игрок видит motivation к ремонту |
| 0% | 0% (broken) | «Сломан» (как MVP сейчас) |

**Implementation:** заменить `if _is_broken(item): continue` в 5 функциях `equipment_bonus.py` на `effective_bonus(item, base)` helper:

```python
def _quality_multiplier(item) -> float:
    qual_list = item.get('quality')
    if not qual_list:
        return 1.0  # legacy без quality = full bonus
    q = qual_list[0]
    if q == 0:
        return 0.0
    if q < 25:
        return 0.5
    if q < 75:
        return 0.75
    return 1.0

def effective_bonus(item, base_bonus) -> int:
    return round(base_bonus * _quality_multiplier(item))
```

Display: «🔨 СЛОМАН» marker остаётся для quality=0; для tier'ов 25/75 — мягче маркер («📉 Подношен 75%», «📉 Повреждён 50%»). Status_bar warning остаётся для < 20%, но добавится counter «изношено: N» для items в 25-75% диапазоне.

**Зависимость:** **blocked by 4.61 MVP done (✓)**. Также bake-test 4.61 (1-2 недели) — посмотреть реакцию игрока на binary cliff.

**Тесты:** symmetric к 4.61 — для каждого tier проверить multiplier × bonus. Edge cases: 24.99% (50%), 25% (75%), 74.99% (75%), 75% (100%).

**Effort:** **S** (~1-2 часа) — изменения локализованы в `equipment_bonus.py` + display tweaks. Pure-helper changes, тесты адаптируются легко.

---

### 4.62. Triumphs / Достижения (зонтичная — объединяет 4.4 + 4.44) `[L / L / todo (15.05.2026)]`

**Объединяет 4.4 (базовый список) + 4.44 (расширенная система с бонусами + Goals)** в одну механику, концептуально вдохновлённую **Destiny 2 Triumphs**. Достижения = система-наградитель за milestones игрока с tiered структурой, категориями, score-метрикой, опциональными бонусами на части триумфов и pin/tracked-механикой (заменяет custom Goals из 4.44).

**Концепция (зафиксировано 15.05.2026):**

| Элемент Destiny 2 | Применение в 2Walks |
|---|---|
| **Tiered triumphs** | Один триумф = несколько ступеней (10/50/100/500/1000 приключений). Прогресс к next tier виден всегда. |
| **Categories** | Шаги / Adventures / Дропы / Gym / Work / Bank / Forge / Энергия / Уровень — каждая категория = группа триумфов |
| **Triumph Score** | Каждый unlock даёт N points. Total = «уровень коллекционера», простая статус-метрика |
| **Bonus только на части триумфов** | ~80% — trophy + score. ~20% — реальный gameplay-эффект (постоянный bonus.py или временный через 4.58 Active buffs). |
| **Seal / Title** | Полная категория unlock → титул в `state.title` (косметика, отображается в status_bar / web). Названия: «Marathoner» / «Treasure Hunter» / «Banker» / «Blacksmith» / etc. |
| **Pinned / Tracked** | Игрок может «закрепить» 1-3 триумфа для приоритетного показа (status_bar / меню Home). **Заменяет custom Goals из 4.44** — нет нужды в free-form input. |

**Что НЕ переносим из Destiny 2:**
- **Lore triumphs** — у нас нет lore-pages (может появиться вместе с 4.46 Story Mode).
- **PvP / Crucible** — у нас нет PvP.
- **Time-limited / seasonal** — отложено до 4.12 (Сезонные события).
- **Hidden / secret** — в MVP не делаем (added complexity, отложено в 4.62.5).

**Связь с другими задачами:**
- **4.6 History** (done) — `log_event` с 24 типами events = естественный hook source для триггеринга триумфов.
- **4.58 Active buffs** (todo) — нужна для временных bonus-эффектов на части триумфов. Блокирует 4.62.2 для **временных** бонусов, но не для постоянных.
- **4.31 Collector** (todo, обсудить) — natural fit для категории «Коллекции».
- **4.37 Pets** (todo) — natural fit для категории «Питомцы».
- **4.5 Daily / weekly quests** (todo) — overlap минимальный: quests = time-limited tasks, triumphs = permanent milestones. Не дублирует.

#### Подзадачи

##### 4.62.0. Infra: state schema + log_event hooks + меню skeleton `[L / M / todo (blocked by nothing)]`

**Создаёт базовый движок триумфов без catalog'а.**

- `state.triumphs: dict[str, dict]` — id → `{tier: int (current unlocked, 0 = none), unlocked_at: dict[tier→datetime]}`. Round-trip в `from_dict` / `to_dict`.
- `state.pinned_triumphs: list[str]` (≤ 3) — id'шники закреплённых триумфов.
- `state.title: Optional[str]` — текущий выбранный титул (None = без).
- Triumph engine — модуль `triumphs.py`:
  - `register_event(state, event_type, **payload)` — на каждый `log_event` вызывается parallel, проверяет какие триумфы триггерятся этим event'ом и инкрементирует прогресс. Идемпотентный (повторный event не двигает tier).
  - `check_unlock(state, triumph_id)` — возвращает (newly_unlocked_tier or None, new_total_score).
  - Pure helpers: `get_progress(state, triumph_id) -> dict` (current_tier, next_tier_threshold, current_count).
- Меню «Triumphs» — каркас (пустой каталог). Pattern: новая location или sub-menu в Home?
- Score calc — sum points по unlocked tiers (constant POINTS_PER_TIER в MVP).
- Persist через round-trip flat keys в Sheets / CSV.

**Тесты:** infra без catalog'а — round-trip, idempotency, score sum, pin/unpin (≤ 3).

##### 4.62.1. MVP catalog (20-30 триумфов, без бонусов) `[L / M / todo (blocked by 4.62.0)]`

**Заполняет каталог реальным контентом.** Только trophy + score, **никаких gameplay-эффектов** — поэтапная реализация.

**Categories MVP (6):**
- 🏃 **Шаги** — 10k / 100k / 1M / 10M total used
- 🗺️ **Adventures** — 10 / 50 / 100 / 500 / 1000 (любые adventures)
- 💎 **Дропы** — первый B / первый A / первый S / первый S+ + 10 / 100 S-grade items
- 🏋️ **Gym** — прокачать любой skill до 5 / 10 / 20 / 30
- 🏭 **Work** — отработать 10 / 100 / 1000 часов
- 📈 **Уровень** — char_level 5 / 10 / 25 / 50 / 100

Caталог = static dict в `triumphs_data.py` (по pattern `adventure_data.py` / `skill_training_data.py`):

```python
TRIUMPHS = {
    'steps_total': {
        'name': 'Marathoner',
        'category': 'steps',
        'tiers': [10_000, 100_000, 1_000_000, 10_000_000],
        'metric': 'state.steps.total_used',
        'event_hooks': ['steps_spent'],  # триггеры из log_event
    },
    ...
}
```

**Тесты:** для каждой категории — happy path (накопил, tier unlock), idempotency, score increments.

##### 4.62.2. Bonus integration на части триумфов `[L / M / todo (blocked by 4.62.1, partial-blocked by 4.58 Active buffs)]`

**На ~5-10 триумфах вешаем gameplay-эффекты.** Стратегия — **бонус только на капстоунах** (max tier категории) — это даёт ощущение «закрыл всю категорию = получил награду».

**Типы бонусов:**
- **Постоянные** — добавляются как `bonus_<name>(state)` функции, читают `state.triumphs` и возвращают +N. Интегрируются в существующие helper'ы (например `total_bonus_steps(state)` суммирует и triumph-bonus).
- **Временные** — через **4.58 Active buffs** (зависимость). Если 4.58 не готов — реализуем только постоянные, временные defer.

**Примеры (для обсуждения):**
- Marathoner капстоун (10M шагов) → +5% к Stamina навсегда.
- Adventurer капстоун (1000 приключений) → +1 max инвентаря.
- Treasure Hunter (10 S-grade items) → +1% к luck постоянно.
- Veteran Worker (1000 часов) → +5% к зарплате (стек с earnings_boost).

**Тесты:** unlock триггерит bonus, бонус виден в status_bar, save/load preserves.

##### 4.62.3. Seals + Titles (мета-триумфы) `[L / S / todo (blocked by 4.62.1)]`

**Закрыл все триумфы категории → получил титул** (косметика).

- `state.title: Optional[str]` — выбранный титул (из unlocked).
- Меню Triumphs: подсекция «Titles» — список доступных, выбор активного.
- Display: status_bar строка «Вы находитесь в локации» расширяется до «<титул> в локации X» если title != None. Web: badge рядом с user.
- Список (MVP, 6 категорий → 6 титулов): Marathoner / Adventurer / Treasure Hunter / Athlete / Hard Worker / Veteran.

**Тесты:** все tiers категории unlock → seal triggers, title в state.

##### 4.62.4. Pinned / Tracked triumphs `[L / S / todo (blocked by 4.62.1)]`

**Заменяет custom Goals из 4.44.** Игрок выбирает 1-3 триумфа для приоритетного показа.

- `state.pinned_triumphs: list[str]` (cap = 3).
- UI: в меню Triumphs — кнопка `📌 Pin / Unpin` на каждом триумфе.
- Display: pinned триумфы видны крупнее в начале меню; опционально — секция в status_bar или Home location.
- При unlock pinned-триумфа toast становится более заметным.

**Тесты:** pin / unpin, cap=3, persistence.

##### 4.62.5. Hidden / Secret triumphs `[L / S / todo (defer, опционально)]`

**Triumphs которые видны только после unlock'а** — для surprise discovery. Defer до конца MVP.

- `TRIUMPHS[id]['hidden'] = True` — в меню показывается как `???` с count `0/?`.
- При unlock — visible с full name.

#### Открытые вопросы (для дизайн-сессии при реализации)

1. **Triggering**: event-driven через `log_event` (естественно, 24 типа events уже есть) **vs** polling каждый тик. **Рекомендация:** event-driven, polling fallback только для счётчиков-агрегатов где нет events (например `state.steps.total_used`).

2. **Persistence schema**: `dict[str, dict]` с `tier + unlocked_at[tier→datetime]` (rich) **vs** просто `dict[str, int]` (id → max_tier). **Рекомендация:** rich — нужен timestamp для display «unlocked: 15.05.2026», для history-интеграции и для future stats.

3. **Visibility в MVP**: все триумфы видны со счётчиком прогресса (Destiny default) **vs** mix с hidden (surprise) **vs** все hidden до первого tier'а. **Рекомендация:** все видны в MVP, hidden — отдельная 4.62.5.

4. **Уведомления при unlock**: только toast в CLI / persistent badge в status_bar «🏆 New triumph unlocked!» если есть unclaimed / только в меню. **Рекомендация:** toast + badge (badge clears после захода в меню).

5. **Score points**: фиксированный (10 за tier 1 / 25 / 50 / 100 / 250 для 5 ступеней) **vs** scale by category (Boss-категории дают больше) **vs** scale by difficulty triumph'а. **Рекомендация:** фиксированный в MVP, scale в V2 после получения feedback.

6. **Catalog size в MVP**: 20 / 30 / 50 триумфов в первой версии? И **точный список**. **Рекомендация:** 25-30 (5 на категорию × 6 категорий), чтобы было достаточно контента и не перегружено.

7. **Bonus стратегия**: бонус только на капстоуне категории / на каждом tier'е / на отдельных fancy-триумфах. **Рекомендация:** капстоуны (закрыл всю категорию = power-up).

8. **Title display**: всегда видимый в status_bar (показывает активный титул) **vs** только в меню Profile **vs** опционально (игрок включает в settings). **Рекомендация:** всегда видимый — даёт ценность косметике, мотивирует закрывать категории.

9. **Связь Titles ↔ Seal completeness**: что если в будущем добавим триумф в категорию которая у игрока уже Seal'нута — отзывать титул до закрытия нового? **Рекомендация:** **не отзывать** (locked-in эффект, fair) — иначе игрок будет демотивирован.

10. **Web mirror**: нужно ли сразу для MVP? **Рекомендация:** **CLI-only для MVP** (как Кузница 4.59), web — follow-up задача после стабилизации каталога. Pin / Title display проще делать когда формат финален.

**Effort всей зонтичной 4.62: L** — большая система с UI, контентным дизайном (каталог 25+ триумфов), интеграцией в существующие event hooks, опциональной integration с 4.58. Реализация поэтапная — каждая подзадача — отдельный коммит.

**Зависимость:**
- `4.62.0 Infra` — blocked by nothing, начинать можно с этого.
- `4.62.1 MVP catalog` — blocked by 4.62.0.
- `4.62.2 Bonus integration` — blocked by 4.62.1; **временные бонусы** блокируются также 4.58.
- `4.62.3 Seals + Titles` — blocked by 4.62.1.
- `4.62.4 Pinned` — blocked by 4.62.1.
- `4.62.5 Hidden` — defer, опционально.

**Приоритет Low** — система мотивирующая, но не критичная для core gameplay. Реализация — когда появится свободный bandwidth между основными механиками.

---

### 4.63. Equipment Auto-Optimizer + Presets (зонтичная) `[M / M / done — Phase 1+2 (18.05.2026, 0.2.4q-r) + Phase 3 (19.05.2026, 0.2.4v) ✓ полностью закрыта]`

**Контекст / проблема:** некоторые операции требуют resource'ов выше того, что игрок может выдать в текущем loadout'е. Пример: Stamina lvl 19 = 95 эн / Stamina lvl 23 = 115 эн при energy_max=65. Игрок физически не может тренировать дальше пока не наденет equipment с +energy_max бонусом. Сейчас это требует ~7 ручных команд (unwear × 3-4 + wear × 3-4), даже если все нужные предметы есть в инвентаре. Аналогичная ситуация перед Adventure'ом (хочется max luck для дропа) и перед Work (хочется max stamina для большего числа часов).

**Решение:** две связанные фичи поверх существующих `equipment._equip_from_inventory` / `_unequip`:

1. **Auto-Optimizer** — single command «оптимизируй под X», сканирует equipment + inventory, выбирает лучшие предметы по слотам, применяет swap. Reactive, под текущую цель.
2. **Equipment Presets** — игрок сохраняет именованные loadout'ы вручную, переключается одной командой. Manual, под долгосрочные стратегии.

Эти фичи не конкурируют — оптимизатор для quick fixes, presets для повторяющихся стратегий.

#### Зафиксированные дизайн-решения (18.05.2026)

| # | Вопрос | Решение |
|---|---|---|
| 1 | Optimizer: одна characteristic или весовая комбинация | **Одна characteristic за раз** (stamina / energy_max / speed_skill / luck_skill). Простота и явность выбора. Balanced setup — через presets. |
| 2 | Порядок реализации | **Optimizer → Presets → Web.** Phase 1 решает заявленную проблему быстро; Phase 2 — когда у игрока появятся осознанные стратегии; Phase 3 — web mirror. |
| 3 | Lost item в preset (продан / сломан / улучшен в Кузнице) | **Skip missing slot + warning.** На apply: если предмет из preset больше не найден в equip+inventory — слот остаётся пустым, в конце print `⚠ N слотов пропущено: <slot1, slot2> (предметы отсутствуют)`. Не ломается, не пытается подобрать замену. |
| 4 | Characteristic base для optimizer | **4 базовых экип-бонуса: `stamina`, `energy_max`, `speed_skill`, `luck_skill`.** Те что реально встречаются на equipment items. Без `energy_regen` (V2 после 4.57) / `sell value` / `avg quality` (out of scope). |
| 5 | Identity для preset items | По reference / position в inventory snapshot'е на момент save (через `is`-comparison или index). На apply сравнивается по `(item_name, item_type, grade, bonus value)` — если найден идентичный → match. |
| 6 | Inventory full при apply optimizer | Net-zero для swap'ов внутри одного слота, но при reshuffle между слотами может быть transient overflow. Решение: apply делает all unwear → all wear, на промежуточной фазе все 7 слотов в инвентаре. Capacity check **перед началом**: если `len(inventory) + currently_equipped_count > capacity` → reject с понятным сообщением. |
| 7 | Сравнение quality vs bonus | Optimizer выбирает по **bonus** (характеристика), не quality. Quality влияет только на price (текущий 0.2.4o); если в 4.61 появится реальный quality effect — пересмотреть. |
| 8 | Сохранение pending_drop при apply | Auto-optimizer **не трогает** state.pending_drop. Resolve pending — отдельный flow (inventory_menu prompt). |

#### Архитектурный план

**Pure helpers (новый файл `loadout.py` или extend `equipment.py`):**

```python
def find_optimal_loadout(state, characteristic: str) -> dict[str, dict | None]:
    """Для каждого слота — лучший item по characteristic из equipped + inventory.

    Returns: dict slot_name → item (or None если для этого слота нет ни одного
    предмета с этой characteristic во всём pool'е).
    """

def preview_loadout_diff(state, target: dict[str, dict | None]) -> list[tuple[str, dict | None, dict | None]]:
    """Diff текущего и target — для confirmation prompt.

    Returns: list of (slot_name, old_item, new_item) только для изменившихся слотов.
    """

def apply_loadout(state, target: dict[str, dict | None]) -> tuple[bool, list[str]]:
    """Атомарно: unwear все changed slots → wear target.

    Returns: (success, warnings). Warnings — список пропущенных слотов
    (для presets с lost items). Capacity-check перед началом.
    """
```

**State extension (только для Phase 2 Presets):**

```python
# state.py
equipment_presets: dict[str, dict[str, dict]] = field(default_factory=dict)
# Key: preset name (e.g., "training", "adventure").
# Value: dict slot_name → item snapshot (на момент save).
```

Round-trip через flat-key `'equipment_presets'` в Sheets (JSON-сериализация как для inventory).

#### 4.63.1. Auto-Optimizer для CLI `[H / S / done (18.05.2026, 0.2.4q)]`

**Объём:**
- Pure helpers `find_optimal_loadout` / `preview_loadout_diff` / `apply_loadout` в `loadout.py` (новый файл) или extend `equipment.py`.
- CLI integration: Equipment menu → новый пункт «Оптимизировать loadout» → выбор characteristic (1-4) → preview + confirm → apply.
- log_event'ы: `'loadout_optimized'` с payload `{characteristic, slots_changed, total_bonus_before, total_bonus_after}`.
- Тесты: pure helpers (corner cases: пустой инвентарь, не для всех слотов есть items, swap внутри слота не меняется), UI flow (cancel / apply / capacity check).

**Эффорт:** **S** (~2-3 часа, ~5 коммитов).

**Прецеденты:** pattern apply (atomic mutation + log_event + persist) как в `equipment._equip_from_inventory`.

**Реализовано (18.05.2026, 0.2.4q):**
- Новый файл `loadout.py` — все pure helpers: `find_optimal_loadout` / `preview_loadout_diff` / `total_bonus` / `apply_loadout` + helper `_bonus_for` (future-proof для multi-char items через `characteristic[].index()` → `bonus[idx]`).
- **Keep-current semantics** — критичный нюанс не описанный изначально в плане: optimizer для X не снимает existing items с другими characteristic'ами если в pool нет matching X-item для слота. Без этого optimizer был бы destructive (target[slot]=None → apply делает unwear → потеря бонусов без причины). Test: `test_find_optimal_loadout_no_candidates_keeps_current_items` + `test_find_optimal_loadout_keeps_non_matching_ring_when_only_one_matching`.
- Ring-слоты: top-2 X-rings → finger_01 (best) / finger_02 (second). Если matching ring только один — finger_01 = он, finger_02 = current keep.
- Capacity check ПЕРЕД apply: peak_inventory_size = current + items_to_unequip > cap → reject без мутаций + warning. Pre-check защищает от частично-применённого state на середине unwear фазы.
- CLI integration в `equipment.py`: пункт `7. 🎯 Оптимизировать loadout (auto-equip)` в Equipment menu → submenu выбора characteristic (1-4 с иконками 🏃 🔋 ⚡ 🍀) → preview с before/after total → `yes`/`no` confirm → apply.
- log_event payload (5 fields): `characteristic`, `slots_changed`, `bonus_before`, `bonus_after`, `warnings_count`.
- Persist НЕ делается — следует существующему equipment pattern (wear/unwear тоже не зовут save_characteristic, игрок жмёт `s`).
- Тесты: 34 новых (27 pure + 7 UI), 803 passed total, mypy 0 issues.

**Открытое для Phase 2 / 3:**
- "Aggressive trade-off" edge case: если 2 X-rings в pool + current finger_02 = non-X ring → optimizer replace'ит non-X на second X-ring (потеря non-X bonus). Это by design ("одна characteristic за раз" из Q1), но может удивить. Mitigation — игрок видит в preview diff и подтверждает yes/no. Если потребуется more conservative behavior — добавить флаг "не трогать слоты с другими characteristic'ами" в Phase 2/3.

#### 4.63.2. Equipment Presets для CLI `[M / M / done (18.05.2026, 0.2.4r)]`

**Объём:**
- State: `state.equipment_presets: dict` + round-trip flat-key.
- Pure helpers `save_preset(state, name)` / `load_preset(state, name)` / `delete_preset(state, name)` / `list_presets(state)`.
- CLI integration: Equipment menu → «Управление пресетами» → submenu (1. Save current / 2. Load / 3. Delete / 4. List).
- Apply переиспользует `apply_loadout` из 4.63.1 (с warnings для lost items).
- log_event'ы: `'preset_saved'`, `'preset_applied'`, `'preset_deleted'`.
- Тесты: round-trip persist, save/load consistency, lost item handling (skip + warning), apply переиспользует тестовое покрытие из 4.63.1.

**Эффорт:** **M** (~3-4 часа, ~5 коммитов). Больше нового state + CRUD UI.

**Открытое:** именование (фиксированные `training`/`adventure`/`default` или user-defined). Решение откладывается до начала работы — может быть user-defined проще (одно поле input vs hardcoded list).

**Реализовано (18.05.2026, 0.2.4r):**
- **Именование:** user-defined (string input). Решение — простой UX, одно поле input vs hardcoded list. Игрок сам решает naming convention.
- **state.equipment_presets** добавлен: `dict[preset_name, dict[slot_attr, item_snapshot|None]] = field(default_factory=dict)`. Round-trip через flat-key 'equipment_presets'. Snapshots — deep-copy items (preset переживает продажу original).
- **Identity matching** в _match_preset_item: item_name + item_type + grade + characteristic[0] + bonus[0]. Quality/price НЕ учитываются (могут меняться от Repair/wear). Точное matching — не пытается подобрать «похожий» item.
- **Lost item handling (Q3)**: skip + warning + keep current equipped в этом слоте (не unwear). Игрок видит warning ДО apply confirm.
- **CLI submenu в Equipment** (пункт 8 «💼 Управление preset'ами»): list (с summary по 4 chars) + save (с overwrite confirm) + load (preview diff + apply confirm) + delete (с confirm).
- log_event: preset_saved (name, slots_filled), preset_applied (name, slots_changed, lost_items_count, apply_warnings_count), preset_deleted (name).
- 27 новых тестов (16 pure + 10 UI + 1 round-trip). 830 passed total, mypy 0 issues.

**Открытое для Phase 3:**
- Naming validation: сейчас только strip + non-empty. Можно добавить max length / special chars validation если станет issue.
- Preset migration на Item dataclass (1.6): когда items станут dataclass'ом — preset snapshots тоже придётся мигрировать. Пока legacy dict-format.

#### 4.63.3. Web UI для optimizer + presets `[M / S / done (19.05.2026, 0.2.4v)]`

**Объём:**
- В Equipment блоке `_status_fragment.html` — новая sub-секция «🎯 Loadout»:
  - Optimizer: dropdown с 4 characteristics + кнопка «Оптимизировать» (`hx-confirm` с preview diff).
  - Presets: список с кнопками «Apply» / «Delete» + кнопка «Save current as…» (form input для имени).
- Endpoints (mirror CLI):
  - `POST /web/loadout/optimize` (Form: characteristic) + `POST /api/loadout/optimize` (JSON).
  - `POST /web/preset/save` + `/load` + `/delete` + `POST /api/preset/*` (mirror).
- Blocked by **4.48.6** — нужны базовые wear/unwear endpoints как фундамент (atomic apply через них).

**Эффорт:** **S** (~1-2 часа после 4.63.1 + 4.63.2 + 4.48.6).

**Реализовано (19.05.2026, 0.2.4v):**
- **Двухэтапный preview UX** (зафиксировано в дизайне): сначала preview-endpoint (`/web/loadout/preview` / `/web/preset/preview_load`) возвращает fragment с banner показывающим diff slot-by-slot + bonus before/after + lost-item warnings. Затем «✅ Применить» → apply-endpoint (`/optimize` / `/preset/load`) re-вычисляет (idempotent) + применяет. «❌ Отмена» — простой `hx-get /status`. Apply re-compute защищает от stale preview (если между preview и apply state изменился).
- **6 web endpoints + 4 API endpoints** (без preview для API — JSON клиенты сами рассчитывают diff). Все через `_persist_and_handle_stale`.
- Helpers: `_build_loadout_view(state)`, `_build_optimize_preview/preset_preview(state, ...)`, `_validate_and_apply_{optimize, save_preset, load_preset, delete_preset}`. Pure helpers из `loadout.py` (4.63.1+4.63.2) переиспользованы как есть.
- **UI** в `_status_fragment.html`: новая `<section id="loadout">` после Equipment с Auto-Optimizer block (select 4 chars + Preview button) и Presets block (list saved с Load/Delete + Save form всегда видимая). Preview banner — таблица diff + bonus before/after / slots_changed_count + warnings блок.
- 4 Pydantic models: `LoadoutOptimizeRequest`, `PresetSaveRequest`, `PresetLoadRequest`, `PresetDeleteRequest`.
- 29 новых тестов. 938 passed total, mypy 0 issues.
- **Зонтичная 4.63 closed полностью.**

#### Связи с другими задачами

- **4.48.6** Web: Inventory + Equipment — фундамент для 4.63.3. Phase 1 + 2 (CLI) не зависят.
- **4.61** Поломка предметов — если quality начнёт влиять на bonus, optimizer должен учитывать quality. Пересмотр когда 4.61 будет реализован.
- **4.57** Equipment energy_regen V2 — добавит 5-ю characteristic, optimizer тривиально расширится.
- **history.jsonl** — `loadout_optimized` / `preset_applied` events могут стать ценным data point для будущей балансировки (показывает, как часто игрок переодевается).

#### Watch / Risks

- **Sort stability при equal bonus.** Если два предмета дают одинаковый bonus в одном слоте — что выбрать? Решение: сохранить текущий equipped если он среди optimal (no-op swap), иначе первый из inventory по item_name. Документировать.
- **Ring slots ambiguity.** `ring` item-type может занять `ring_1` или `ring_2`. Optimizer должен корректно мэппить два кольца в два слота (не дублировать одно).
- **State.last_modified bump.** Apply optimizer = mutation → bump → может вызвать STALE в параллельных CLI/web. Это OK, по дизайну 4.54.

---

Ниже — идеи без официальных номеров. Если решим брать — выделим в формальные task'и.

1. **Bulk Action** — открывает возможность запускать несколько активностей подряд одной командой (например, "5 раз walk_easy за раз"). Сложнее в реализации, требует UI-поддержки. Не навык в строгом смысле — скорее QoL-фича.

4. **Bulk Action** — открывает возможность запускать несколько активностей подряд одной командой (например, "5 раз walk_easy за раз"). Сложнее в реализации, требует UI-поддержки.

### 5.1. Type hints на новый код и постепенно на старый (зонтичная) `[L / L / done (0.2.1j-r, 05.05.2026)]`

**Цель:** добавить аннотации типов параметров и возврата ко всем функциям и методам кодобазы. Покрытие 100%, постепенно по файлам.

**Польза:**
1. **IDE autocomplete / inline-warnings** — `state.<dot>` сразу выдаёт поля без чтения `state.py`.
2. **Документация в сигнатуре** — `def f(work: str, hours: int) -> bool` понятнее чем `def f(work, hours)`.
3. **Защита при рефакторинге** — статанализатор (если подключим mypy позже) ловит забытые места при переименованиях.
4. **Ловля опечаток** — `state.energy_mx` вместо `state.energy_max` — IDE подчеркнёт.

**Что НЕ делается в скоупе 5.1:**
- **mypy не подключаем** — hint-only режим. Аннотации пишутся для IDE и читателя, статанализ не enforced. Подключение mypy + конфиг — отдельная задача 5.4 на будущее.
- **TypedDict для item-словарей** не вводим — структура `{'item_name': [str], 'bonus': [int], ...}` (списки в полях) выглядит уродливо в TypedDict. Ждём задачу **1.6** (Items as dataclass), там и аннотируем как нормальный dataclass.
- **Generic legacy-методы вроде `Adventure.adventure_check_done(self=None, state)`** — оставляем со странной сигнатурой как есть; нормализуется в рамках 1.1 follow-up.

**Текущее покрытие** (return-types для функций модуля):

| Файл | Coverage | Заметки |
|---|---|---|
| `web/sync.py` | 4/4 (100%) | ✓ |
| `web/main.py` | 13/16 (81%) | Хорошо |
| `google_sheets_db.py` | 11/14 (79%) | Хорошо |
| `gym.py` | 6/12 (50%) | Helpers — да, методы класса — нет |
| `actions.py` | 1/4 (25%) | params хинты есть, return-types нет |
| `state.py` | 1/5 (20%) | Dataclass-fields типизированы, методы — нет |
| `bonus.py` | 1/7 (14%) | Большинство `def f(state: GameState):` без `->` |
| `functions.py` | 1/15 (7%) | Слабо |
| `inventory.py` | 0/11 (0%) | Не покрыто |
| `equipment.py` | 0/7 (0%) | Не покрыто |
| `adventure.py` | 0/10 (0%) | Не покрыто |
| `level.py` | 0/15 (0%) | Не покрыто |

**Параметры `state: GameState` уже есть везде** (после Phase 4 в 1.1) — основная работа теперь в return-types и аннотации остальных параметров.

**Pattern для типов:**
- Параметры: `state: GameState`, `work: str`, `hours: int`, `item: dict`, `inventory: list[dict]` (item dicts — `dict` без TypedDict пока).
- Optional: `Optional[str]`, `Optional[datetime]` (datetime поля — уже типизированы в state.py).
- Return: `-> bool / int / str / None / dict / list / tuple[X, Y]`.
- Forward refs: `'Adventure'` в кавычках если circular.
- Для функций которые ничего не возвращают (только print/mutate) — `-> None`.

**Версионирование:** каждая подзадача — отдельный коммит, версия наращивается буквой (`0.2.1j`, `0.2.1k`, ...). Альтернатива — батчевые коммиты по 2-3 файла; `0.2.2` как маркер закрытия зонтичной 5.1.

**Тесты:** не добавляем — type hints не runtime, существующие 381 тестов должны продолжать проходить.

**Порядок выполнения:** от core (state, actions, bonus) к UI (inventory, equipment, shop). Разбивка на 10 подзадач ниже:

#### 5.1.1. `state.py` — методы dataclass классов `[L / S / done (0.2.1j)]`

`GameState`, `StepsState`, `CharLevel`, `GymSkills`, `TrainingSession`, `WorkSession`, `AdventureSession`, `Equipment` — dataclass-fields уже типизированы. Не хватает аннотаций для методов: `default_new_game()` → `'GameState'` (forward ref), `from_dict(d: dict) -> 'GameState'`, `update_from_dict(self, d: dict) -> None`, `to_dict(self) -> dict`. Также вспомогательные `_deser_datetime(value) -> Optional[datetime]`, `json_serial(obj) -> Any`. ~5 функций.

**Сделано (05.05.2026, 0.2.1j):** анализ показал что 4 method-аннотации (`default_new_game`, `from_dict`, `update_from_dict`, `to_dict`) уже типизированы в коде. Добавлено: (1) `_deser_datetime(v: Any) -> Optional[datetime]` (раньше принимал нетипизированный v); (2) `AdventureSession.counters: dict[str, int]` (раньше был просто `dict`); (3) `GameState.inventory: list[dict]` (раньше `list`) с комментарием что TypedDict откладывается до 1.6 Items as dataclass. `json_serial` живёт в characteristics.py (вне scope 5.1.1) — будет в 5.1.5. Тесты не добавлялись (type hints не runtime). All 381 tests pass.

#### 5.1.2. `actions.py` — mutation helpers `[L / S / done (без code changes, проверено в 0.2.1j)]`

Маленький файл (100 строк). 4 функции: `try_spend(state, steps, energy, money) -> bool` (return уже есть, params полностью типизированы), `start_work(...) -> None`, `start_training(...) -> None`, `start_adventure(...) -> None`. Только добавить `-> None` к 3 функциям + проверить params.

**Результат проверки (05.05.2026):** все 4 функции **уже полностью покрыты** type hints. Все параметры с хинтами, все return types указаны (`-> bool` для `try_spend`, `-> None` для трёх start_*). Видимо файл был создан с хинтами с самого начала (Phase 4 of 1.1 GameState rollout). Code changes не потребовались, version не bump'ался — отметка о проверке записана в changelog к 0.2.1j.

#### 5.1.3. `bonus.py` + `equipment_bonus.py` + `skill_bonus.py` — формулы `[L / S / done (0.2.1k)]`

3 файла, всего ~15 функций. Все принимают `state: GameState`, возвращают `int / float / dict / tuple[int, int, int, int]` (для `equipment_bonus_summary`). Простой набор:
- `bonus.py`: `compute_energy_max(state) -> int`, `equipment_bonus_stamina_steps(state) -> int`, `daily_steps_bonus(state) -> int`, `level_steps_bonus(state) -> int`, `apply_move_optimization_*(steps, state) -> int/dict`.
- `equipment_bonus.py`: 5 функций возвращают `int`.
- `skill_bonus.py`: 2 функции, `int`.

**Сделано (05.05.2026, 0.2.1k):** добавлены return-types и параметр-типы ко всем функциям. (1) `bonus.py` — 6 функций обновлены: `equipment_bonus_stamina_steps`, `daily_steps_bonus`, `level_steps_bonus` → `-> int`; `apply_move_optimization_adventure(steps: dict, state) -> dict`; `apply_move_optimization_gym/work(steps: int, state) -> int`. `compute_energy_max` уже был типизирован. (2) `equipment_bonus.py` — 6 функций: `_equipment_slots(state) -> list[Optional[dict]]` (импорт Optional из typing); `equipment_bonus(state) -> tuple[int, int, int, int]`; 4 single-stat функции `equipment_*_bonus(state) -> int`. (3) `skill_bonus.py` — 2 функции: `stamina_skill_bonus_def(state) -> int`; `speed_skill_equipment_and_level_bonus(x: int, state) -> int`. Code changes 14 строк аннотаций. All 381 tests pass.

#### 5.1.4. `level.py` — `CharLevel` class methods `[L / S / done (0.2.1l)]`

15 функций / методов в одном классе `CharLevel`. Большинство — getters/setters без return value (`-> None`), несколько считают (`-> int / str / float`):
- `total_used_steps` (property), `level` (property + setter), `view_total_used_steps()`, `view_char_level()`, `update_level_char_characteristic() -> None`, `update_level_up_skills_char_characteristic(level_up_difference: int) -> None`, `calculate_level_from_total_used_steps() -> int`, `update_level() -> None`, `progress_to_next_level() -> float`, `progress_bar(length: int = 33) -> str`, `progress_bar_lvl_up_message() -> str`, `menu_skill_point_allocation() -> None`, `level_status_bar() -> None`.

**Сделано (05.05.2026, 0.2.1l):** добавлены аннотации ко всем 13 методам класса `CharLevel` + 2 property + 1 setter (`__init__`, properties `total_used_steps -> int` / `level -> int`, setter `level(value: int) -> None`, view-методы `-> None`, mutation-методы с параметрами `level_up_difference: int`, calc-методы `-> int / float`, formatting `progress_bar(length: int = 33) -> str` / `progress_bar_lvl_up_message() -> str`, UI-меню `menu_skill_point_allocation() -> None`, `level_status_bar() -> None`). Code changes 14 строк аннотаций, поведение не изменено. All 381 tests pass.

#### 5.1.5. `characteristics.py` — load/save функции + helpers `[L / M / done (0.2.1m)]`

8 функций. `init_game_state(state: Optional[GameState] = None) -> GameState`, `apply_steps_log_max_merge(state: GameState) -> None`, `load_characteristic() -> dict`, `save_characteristic() -> None`, `get_energy_training_data(level: int) -> dict`. Файл крупный (468 строк), но функции относительно простые.

**Сделано (05.05.2026, 0.2.1m):** 2 функции (`init_game_state`, `apply_steps_log_max_merge`) уже были типизированы. Добавлено 6 аннотаций: `load_characteristic() -> dict`, `load_data_from_google_sheet_or_csv() -> dict`, `get_skill_training(level: int) -> dict`, `get_energy_training_data(level: int) -> dict`, `json_serial(obj: Any) -> str` (с уточняющим docstring про json.dump default-callback контракт), `save_characteristic() -> None`. Импорт `Any` из typing добавлен. Code changes 6 строк, runtime не изменён. All 381 tests pass.

#### 5.1.6. `gym.py` — `Skill_Training` class methods `[L / S / done (0.2.1n)]`

12 функций, частично типизировано. Дополнить остальные:
- `_render_gym_menu(state, skill_options) -> None`
- `gym_menu(state) -> None`
- `display_skill_description(skill_name: str, state) -> None`
- `Skill_Training.__init__(self, state: GameState, name: Optional[str] = None) -> None`
- `Skill_Training.check_requirements(self) -> bool` (уже есть)
- `Skill_Training.start_skill_training(self) -> None`
- `skill_training_check_done(state: GameState) -> None` (уже типизирован параметр).

**Сделано (05.05.2026, 0.2.1n):** 6 методов уже были типизированы (`_next_skill_level`, `_training_cost`, `_apply_speed_bonus`, `format_lvl_up_info`, `_render_gym_menu`, `Skill_Training.check_requirements`). Добавлено 6 аннотаций: `get_lvl_up_info(skill_name: str, level: int, state) -> str`, `display_skill_description(skill_name: str, state) -> None`, `gym_menu(state) -> None`, `skill_training_check_done(state) -> None`, `Skill_Training.__init__(state, name: Optional[str] = None) -> None` (импорт Optional), `Skill_Training.start_skill_training() -> GameState` (метод фактически возвращает state — это видно из `return state` в конце). Code changes 6 строк аннотаций + импорт Optional. All 381 tests pass.

#### 5.1.7. `work.py` — `Work` class methods + work_check_done `[L / S / done (0.2.1o)]`

7 функций. `Work.__init__(self, state: GameState) -> None`, `Work.work_choice(self) -> Optional[str]`, `Work.ask_hours(self, work: str) -> None`, `Work.add_working_hours(self, work: str) -> None`, `Work.check_requirements(self, work: str, working_hours: int) -> bool`, `_speed_bonus_pct(state: GameState) -> int` (уже есть), `work_check_done(state: GameState) -> GameState`.

**Сделано (05.05.2026, 0.2.1o):** `_speed_bonus_pct` уже был типизирован. Добавлено 6 аннотаций: `Work.__init__(state) -> None`, `Work.work_choice() -> Optional[str]` (импорт Optional — возвращает строку '0' / 'watchman' / 'factory' / etc., либо None при возврате через add_working_hours), `Work.ask_hours(work: str) -> None`, `Work.add_working_hours(work: str) -> None`, `Work.check_requirements(work: str, working_hours: int) -> bool`, `work_check_done(state) -> GameState` (метод фактически возвращает state из обеих веток). Code changes 6 строк + импорт Optional. All 381 tests pass.

#### 5.1.8. `adventure.py` — `Adventure` class methods + Drop_Item interaction `[L / M / done (0.2.1p)]`

10 функций / методов. Особенность: `Adventure.adventure_check_done(self=None, state)` — странная сигнатура. Хинт: `def adventure_check_done(self: Optional['Adventure'], state: GameState) -> None`. Также `Adventure.__init__(self, adventure_data_table: list, state: GameState) -> None`, `get_adventure_requirement(self, name: str) -> str`, `adventure_choice_confirmation(self, ...) -> bool`, `check_requirements(self, ...) -> bool`.

**Сделано (05.05.2026, 0.2.1p):** добавлены аннотации ко всем 10 методам класса `Adventure`. Главные: `__init__(adventure_data_table: dict, state) -> None` (data_table — dict из adventure_data.py, не list), `adventure_check_done(state: Optional[GameState] = None) -> None` (legacy default, импорт Optional), UI `_render_adventure_menu / adventure_menu / adventure_choice() -> None`, `adventure_choice_confirmation(adv_name: str, adv_req: str, adv_steps: int, adv_energy: int, adv_time: int) -> bool`, `check_requirements(adv_name: str, adv_steps: int, adv_energy: int, adv_time: int) -> bool`, `_enter_adventure(...) -> GameState`, `start_adventure(...) -> GameState` (legacy alias), `get_adventure_requirement(adventure_key: str) -> str`. Code changes 9 строк аннотаций + импорт Optional. All 381 tests pass.

#### 5.1.9. `inventory.py` + `equipment.py` + `shop.py` — UI-обёртки `[L / M / done (0.2.1q)]`

UI-функции с `input()` / `print()`. 26 функций суммарно:
- `inventory.py`: 11 функций. Pure helpers `_sort_inventory(inventory: list[dict]) -> list[dict]`, `_sell_item_at_index(state: GameState, index: int) -> tuple[dict, int]`. UI: `inventory_menu(state) -> None`, `sold_item(state) -> None`, `inventory_view(state) -> list[dict]`. Class `Wear_Equipped_Items` с методами.
- `equipment.py`: 7 функций. Pure: `_equip_from_inventory(state, slot_attr: str, idx: int) -> tuple[dict, Optional[dict]]`, `_unequip(state, slot_attr: str) -> Optional[dict]`. UI: `Equipment.equipment_view(self, state)`, etc.
- `shop.py`: 8 функций. Pure: `_buy_item(state, item: dict, cost: int) -> bool` (уже есть). UI: `Shop.shop_menu(self, state) -> None`, etc.

**Сделано (05.05.2026, 0.2.1q):** все 26 функций в трёх UI-файлах получили аннотации. (1) `inventory.py` (11 функций): pure `_sort_inventory(inventory: list[dict]) -> list[dict]`, `_sell_item_at_index(state, index: int) -> tuple[dict, int]`; UI `inventory_menu / sold_item -> None`, `inventory_view -> list[dict]`; class `Wear_Equipped_Items` (`__init__ -> None`, `_slots() -> dict`, `decrease_durability(steps: int) -> None`, `recalc_item_prices() -> None`, `reduce_wear(steps: int) -> None`, `view_wear_reduce_change(item_name: str, initial_quality: float, steps: int, adjusted_steps: float, final_quality: float, wear_without_skill: float, wear_with_skill: float) -> None`). (2) `equipment.py` (7 функций): pure `_equip_from_inventory(state, slot_attr: str, idx: int) -> tuple[dict, Optional[dict]]`, `_unequip(state, slot_attr: str) -> Optional[dict]`; class `Equipment` методы `-> None` с string-параметрами (item_name/item_type/item_slot) и `list_cnt: list[int]`. (3) `shop.py` (8 функций): `_money_line(state) -> str` (уже типизирован), `_empty_item() -> dict`, `_buy_item` (уже типизирован), class `Shop` методы `-> None` с `item: dict, money: str` (money — colorized line); вложенные `_clothes_stub(label: str, header: str) -> None` и `clothes_shoes(money: str) -> None`. Импорты `Optional` добавлены в inventory.py и equipment.py. Code changes ~25 строк аннотаций. All 381 tests pass.

#### 5.1.10. `functions.py` + `functions_02.py` — cross-cutting helpers `[L / S / done (0.2.1r)]`

15 + 2 функций. `functions.py`: status_bar, energy_time_charge, save_game_date_last_enter, today_steps_to_yesterday_steps, total_bonus_steps, bonus_percentage, format_steps, location_change_map, energy_timestamp, char_info, steps, steps_today_set, _max_merge_today_from_log, timestamp_now, steps_today_manual_entry. `functions_02.py`: `time(x: int) -> str`, `format_timedelta(td) -> str` (уже есть).

**Сделано (05.05.2026, 0.2.1r):** все 15 функций functions.py + 1 в functions_02.py получили аннотации. functions.py: `timestamp_now() -> float`, `energy_time_charge(state) -> None`, `status_bar(state) -> None`, `save_game_date_last_enter(state) -> int` (returns can_use), `steps_today_set(entered: int, state) -> None`, `steps_today_manual_entry(state) -> None`, `char_info(state) -> None`, `steps(state) -> int`, `location_change_map(state) -> None`, `energy_timestamp(state) -> float`, `today_steps_to_yesterday_steps(state) -> tuple[int, int]`, `total_bonus_steps(state) -> int`, `bonus_percentage(state) -> float`, `format_steps(steps: int) -> str`. `_max_merge_today_from_log` уже типизирована. functions_02.py: `time(x: int) -> str` (расширён docstring c явным указанием use case — minutes для cost-displays, не для countdown'ов; для countdown'ов есть `format_timedelta`). `format_timedelta` уже типизирована (с 0.2.1i). Code changes ~14 строк аннотаций, runtime не изменён. **Зонтичная 5.1 закрыта полностью** — все 10 подзадач 5.1.1-5.1.10 done. All 381 tests pass.

---

**Порядок коммитов:** строго 5.1.1 → 5.1.10. Каждая подзадача — отдельный коммит, версия `0.2.1j` → `0.2.1s`. Между ними прогон pytest (381 тест → должно остаться столько же, тесты не добавляются).

**Альтернатива (батч):** объединить 5.1.1 + 5.1.2 + 5.1.3 в один коммит (core formulas), 5.1.4 + 5.1.5 — другой (level + characteristics), и т.д. Решается при реализации. По умолчанию — по подзадаче на коммит.

---

### 5.2. Убрать жёстко зашитые ID и пути в код `[L / S / done]`

**Сделано (частично, Google Sheets):** создан `config.py` с тремя константами: `SPREADSHEET_ID`, `GAME_STATE_SHEET_NAME`, `CREDENTIALS_PATH`. `google_sheets_db.py` импортирует их и использует как дефолты в обоих функциях — сигнатуры не менялись, обратная совместимость сохранена.

Имя `GAME_STATE_SHEET_NAME` (вместо `SHEET_NAME`) выбрано с заделом на задачу 4.14, где появится `STEPS_LOG_SHEET_NAME`. В файле оставлена закомментированная строка-напоминание.

**Вне скоупа (отложено):** пути локальных файлов (`characteristic.csv`, `characteristic.txt`, `save.txt`) — если понадобится, отдельная задача в будущем. Fitness API path-константы перестали быть актуальны после 4.16 (модули удалены).

---

### 5.3. Удалить мёртвый код `[L / S / todo]`

- `characteristics.py:483-508` — стек неиспользуемых переменных (`flat_walking`, `resistance_cold`, и т.д.)
- `functions.py:221` — `steps_today_update_manual_nocodeapi_old()`
- Закомментированные блоки в `game.py`, `shop.py`, `inventory.py`.

---

### 5.4. `requirements.txt` консольной версии `[done]`

Создан с зависимостями только для консольной версии: `colorama`, `requests`, `gspread`, `oauth2client`, `google-auth`, `google-auth-oauthlib`.

---

### 5.5. Удалить Kivy/Android наработки `[L / S / done]`

**Сделано (24.04.2026):** удалены `buildozer.spec`, `main_kivy_gui.py`, `main_kivy_console.py`, папки `screens/` и `widgets/` — всего ~1040 строк. Обновлены разделы `CLAUDE.md` (Project context, Entry points, Common commands, Kivy GUI specifics, Android packaging) и шапка `docs/game_console.md`. `icons/` оставлены для задачи 4.17 (PyInstaller). Консольный путь (`game.py`) не затронут — `py_compile` всех оставшихся модулей проходит. Git сохраняет историю удалённых файлов, при необходимости восстановление через `git log --all --diff-filter=D` + `git checkout`.

---

### 5.6. Подключить mypy + конфиг + cleanup ошибок (зонтичная) `[M / S / done (0.2.1u)]`

Follow-up к 5.1 (Type hints — done в 0.2.1j-r). После добавления аннотаций сами хинты не enforce'аются — mypy их проверяет статически и ловит несоответствия типов. Эта задача — про **подключение mypy** в проект и **fix всех ошибок** на permissive baseline.

**Подключение (done в 0.2.1u):**
- Создан `requirements-dev.txt` с `mypy>=1.8.0` (отделили dev-deps от runtime).
- Создан `mypy.ini` с permissive базой: python 3.13, `warn_return_any`, `warn_unused_configs`, `warn_redundant_casts`, `warn_unused_ignores`, `ignore_missing_imports=True` (gspread/colorama без stubs), `disallow_untyped_defs=False`, `strict_optional=False` (item dicts ждут 1.6).
- `pip install -r requirements-dev.txt` → mypy 1.20.2 установлен.

**Первый прогон (`mypy .`):** 29 ошибок в 9 файлах. Категории:
- 🔴 Реальный баг типизации `state.adventure.end_ts` (5 ошибок) — поле объявлено как `Optional[datetime]`, но в коде везде используется как `Optional[float]` (Unix timestamp). Save format уже хранит float. Выделено в подзадачу **5.6.1**.
- 🟡 `int *= float` в bonus.py / gym.py / inventory.py / characteristics.py — runtime ОК (есть `int(x)` в return), но mypy ругается на присвоение float в int-переменную. Локальная переменная-float фиксит.
- 🟡 `getattr(state.gym, name) -> Any` в gym.py / equipment.py / web/main.py — mypy не знает что state.gym имеет только int-поля. Fix: `cast(int, getattr(...))` или `# type: ignore[no-any-return]`.
- 🟢 `load_characteristic -> dict` polymorphic value types — fix `dict[str, Any]`.
- 🟢 gspread `value_input_option="USER_ENTERED"` ожидает enum `ValueInputOption`, не str — выделено в подзадачу **5.6.2**.
- 🟢 Прочие single-line (drop.py annotation для local var, и т.п.).

**После cleanup ожидаем:** 0 ошибок mypy на permissive baseline. Дальше можно ужесточить (`disallow_untyped_defs`, `strict_optional`) — но это отдельная задача.

**Вне scope:**
- TypedDict для item dicts (ждёт 1.6).
- CI integration (нет CI в проекте — отдельная задача когда понадобится).
- Strict mode (`--strict`) — после permissive baseline.

#### 5.6.1. Fix `state.adventure.end_ts` type mismatch `[L / XS / done (0.2.1u)]`

В `state.py:AdventureSession`:
```python
end_ts: Optional[datetime] = None       # was adventure_end_timestamp
```

Но в коде везде используется как float (Unix timestamp):
- `adventure.py:64,75`: `state.adventure.end_ts <= datetime.now().timestamp()` — сравнение datetime с float.
- `adventure.py:77`: `datetime.fromtimestamp(state.adventure.end_ts)` — `fromtimestamp()` ожидает float.
- `adventure.py:194`: `actions.start_adventure(state, ..., end_ts=now_ts + adv_time*60)` — передаётся int.
- `adventure.py:206`: `state.adventure.end_ts - datetime.now().timestamp()` — datetime - float.
- `web/main.py:557`: тот же datetime <= float.

Save format (`state.from_dict`) уже читает `adventure_end_timestamp` как float **без** `_deser_datetime`. То есть runtime тип всегда float, dataclass-аннотация неверна.

**Fix:** заменить `end_ts: Optional[datetime]` → `Optional[float]` в `AdventureSession`, обновить `Adventure.start_adventure(end_ts: float)` сигнатуру (сейчас `: datetime`). Save round-trip не ломается — поле уже float в сейвах.

**Migration:** не нужна — данные уже float, только аннотация была неправильной.

#### 5.6.2. Mypy: gspread `ValueInputOption` enum `[L / XS / done (0.2.1u)]`

В `google_sheets_db.py:216`:
```python
ws.append_row(entry, value_input_option='USER_ENTERED')
```

Mypy ругается: `Argument "value_input_option"... has incompatible type "str"; expected "ValueInputOption"`. Это типовое ужесточение API gspread в новых версиях.

**Fix варианты:**
- (A) Импортировать enum: `from gspread.utils import ValueInputOption` → `value_input_option=ValueInputOption.user_entered`.
- (B) `# type: ignore[arg-type]` если хотим оставить string-литерал (gspread runtime принимает обе формы).

**Решить при реализации.** Подкаст в отдельную подзадачу — изменение касается только gspread API.

**Сделано (05.05.2026, 0.2.1u):** выбран вариант (A) — импорт enum: `from gspread.utils import ValueInputOption` + использование `value_input_option=ValueInputOption.user_entered`. Чище чем `# type: ignore`, mypy теперь проходит. Test mock'ам в test_sheets_repo.py не пострадали — мы мокаем worksheet, а не enum.

---

## Большая цель

**Текущий фокус (апрель 2026):** наладить надёжную синхронизацию шагов iPhone -> Google Sheet + закрыть накопленные баги.

Порядок работ:
1. **4.1** — ручной ввод шагов (1 час, независимый, разблокирует всё).
2. Дешёвые баги: **2.2** (округление энергии), **2.5** (голые `except:`), **2.7** (`>=` в уровнях). Суммарно ~2-3 часа.
3. **4.14** + **4.13** + **4.15** — конвейер шагов через Apps Script и iOS Shortcut. 4-8 часов. (4.16 закрыта 2026-04-27 — Fitness API удалён.)
4. **4.17** — PyInstaller-сборка `.app` для Mac. 2-3 часа.

Долгосрочно, если решишь развивать дальше: **1.1 (GameState)** — корневой рефакторинг, разблокирующий тесты, мультисейв и большинство остальных задач. Три бага из `bugs.txt` умирают сами после него.

---

## Как работать с этим файлом

- Статусы правь прямо в заголовке задачи: `[H / L / in-progress]`, `[H / L / done]`.
- Когда задача сделана — `done` + 1-2 строки итога под ней (что изменилось, какие файлы, в какую сторону).
- Новые задачи добавляй в соответствующий раздел с той же схемой `[Impact / Effort / Status]`.
- Если задача блокирована другой — `blocked by N.N` в статусе.
