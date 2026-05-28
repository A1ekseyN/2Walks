# Консольная версия 2Walks — документация по запуску и игровому процессу

Этот документ описывает работу игры при запуске через `game.py` — **первичный интерфейс**. Веб-интерфейс (FastAPI backend + браузер) запланирован как параллельный путь — см. задачу **4.48** в `TASKS.md`. CLI остаётся primary, web нарастает incrementally; единый source of truth для обоих — Google Sheets.

---

## 1. Запуск

### Команда

```bash
source .venv/bin/activate
python game.py
```

### Требования окружения

- Python 3.x с установленными зависимостями из `requirements.txt` (`colorama`, `gspread`, `oauth2client`).
- Терминал с UTF-8 (для эмодзи и русского текста). В `game.py` под Windows вызывается `os.system("chcp 65001")`.
- Опционально для облачного сохранения:
  - `credentials/2walks_service_account.json` — сервис-аккаунт для Google Sheets.

Без этого файла игра всё равно запустится: Google Sheets упадёт в фолбэк на CSV (`characteristic.csv`), основной цикл продолжит работать.

### Что происходит в момент запуска (до появления меню)

Порядок выполнения чёткий и явный: импорты модулей чистые (без сетевых вызовов после задачи 1.2), вся инициализация состояния происходит в `init_game_state()`, который вызывается из `__main__` перед `play()`.

1. `game.py:__main__` выводит `Version: 0.2.0d` и переключает codepage.
2. Вызывается `init_game_state()`:
   - `GameStateRepo().load()` тянет лист `game_state` из Google Sheets, при неудаче — читает `characteristic.csv`.
   - Из загруженного flat-dict собирается `game.state = GameState.from_dict(...)`. `timestamp_last_enter`, `loc='home'`, `state.energy_max = compute_energy_max(state)` (50 + все бонусы) применяются как post-load fixups. Поле `state.energy_max` — кэш для save-format; в логике игры читается через `bonus.compute_energy_max(state)` (после 0.2.1g).
   - `game.state` теперь живой instance, видимый всем модулям через `from characteristics import game; game.state`.
3. Вызывается `play()`. Внутри:
   - Локальная переменная `state = game.state` для удобства.
   - Создаётся `Adventure(adventure_data_table, state=state)` — нужен для меню приключений и предвычисленных бонусов с учётом текущей прокачки.
   - Определяется внутренняя функция `location_selection()`. Главный цикл игры — именно она.
   - Проверяется `state.loc` из сохранения и вызывается соответствующая локация (`home_location(state)`, `gym_location(state)`, `work_location(state)`, `adventure_location(adventure_instance)`, ...), после чего запускается `location_selection()`.

### Игровое состояние: `GameState`

Весь игровой процесс держится на одной структуре — `state.GameState` (dataclass с nested подклассами). Живой instance — `game.state` через container `game = _GameContainer()` в `characteristics.py`. Заполняется через `init_game_state()` (CLI вызывает в начале `__main__`, FastAPI — в startup hook). Каждая функция геймплея принимает `state: GameState` явно. Мутация поля в одном модуле мгновенно видна во всех — все держат ссылку на тот же объект через `game.state`.

Группы полей и их адреса в state:

| Группа | Поле в state |
|---|---|
| Идентификатор дня и шаги | `state.date_last_enter`, `state.timestamp_last_enter`, `state.steps.{today,used,yesterday,total_used,can_use,daily_bonus}` |
| Уровень и очки | `state.char_level.{level,up_skills,skill_stamina,skill_energy_max,skill_speed,skill_energy_regen,skill_luck}` |
| Ресурсы | `state.energy`, `state.energy_max` (cache; canonical = `bonus.compute_energy_max(state)`), `state.energy_time_stamp`, `state.money` |
| Прокачиваемые навыки (Gym) | `state.gym.{stamina,energy_max_skill,energy_regen_skill,speed_skill,luck_skill,neatness_in_using_things,move_optimization_adventure,move_optimization_gym,move_optimization_work,energy_optimization_adventure,energy_optimization_gym,energy_optimization_work,...,forge_steps_saving,forge_money_saving,forge_repair_quality}` (23 навыка total после 0.2.6a / 4.60) |
| Текущая тренировка | `state.training.{active,skill_name,timestamp,time_end}` |
| Работа | `state.work.{work_type,active,hours,salary,start,end}` |
| Приключение | `state.adventure.{active,name,start_ts,end_ts}` + `state.adventure.counters` (dict с 7 ключами `walk_easy/walk_normal/.../walk_30k`) |
| Инвентарь и экипировка | `state.inventory` (список словарей-предметов), `state.equipment.{head,neck,torso,finger_01,finger_02,legs,foots}` |
| Локация | `state.loc` (`home` / `gym` / `shop` / `work` / `adventure` / `garage` / `auto_dialer` / `bank`) |

CSV / JSON / Google Sheets хранят flat-формат с прежними ключами; конвертация в обе стороны через `GameState.from_dict()` / `state.to_dict()`. При добавлении нового поля обнови оба маппинга.

Историческая справка: до версии 0.2.0 это был один module-level dict `char_characteristic`. Удалён при завершении задачи 1.1; в старых коммитах/доках имя ещё встречается.

---

## 2. Главный цикл `location_selection()`

Функция `game.location_selection()` — бесконечный `while True`, который выводит глобальное меню, читает команду от игрока и делегирует действие локации. Итерация цикла состоит из трёх частей:

### 2.1 Tick-проверки перед выводом меню

В начале каждой итерации последовательно вызываются:

1. `energy_time_charge(state)` (`functions.py`) — регенерация энергии. Сравнивает текущий timestamp с `state.energy_time_stamp` и, если прошло достаточно секунд (по умолчанию 60, умноженное на модификатор скорости), начисляет по одной единице за каждый полный интервал. Остаток сохраняется в стампе (`stamp = now - remainder`), чтобы дробные секунды не терялись. При `state.energy >= compute_energy_max(state)` стамп сразу синкается к `now` — регенерация "не копится" пока энергия на максимуме, после траты отсчёт интервала начинается заново. Кап читается через `bonus.compute_energy_max(state)` (после 0.2.1g), не через stale-поле.
2. `work_check_done(state)` (`work.py`) — если персонаж на работе и `state.work.end <= now`, начисляет зарплату, сбрасывает `state.work.*`.
3. `skill_training_check_done(state)` (`gym.py`) — если идёт тренировка и `state.training.time_end <= now`, повышает уровень соответствующего навыка на 1, сбрасывает `state.training.*`.
4. `status_bar(state)` (`functions.py`) — печатает шаги, энергию, деньги, уровень, текущую локацию, а также информацию о текущей тренировке/работе/приключении с таймером до завершения. Таймер форматируется через `functions_02.format_timedelta(td)` (с 0.2.1i) — `Yг Mмес Wнед Dд H:MM:SS`. Тот же формат используется и в web (`formatRemaining` в `dashboard.html`) — константы синхронизированы (год=365д, месяц=30д, неделя=7д) чтобы CLI и web показывали идентичные строки для одного state.

Если `state.adventure.active`, `status_bar` вызовет `Adventure.adventure_check_done(self=None, state=state)`, которая при завершении прогулки дропнет предмет в `state.inventory` и поднимет соответствующий счётчик `state.adventure.counters[walk_*]`.

Итог: **пока игрок не нажимает Enter, ничего не происходит**. Чтобы "получить" заработанные деньги или готовую экипировку, нужно вернуться в главное меню (отдать управление `location_selection()`).

### 2.2 Меню глобальной карты

Игрок видит номера локаций и короткий список горячих клавиш:

| Ввод | Действие |
|---|---|
| `1` | 🏠 Домой (заглушка — `home_location()` только печатает текст) |
| `2` | 🏋️ Спортзал — `gym_location()` → `gym_menu()` |
| `3` | 🛒 Магазин (в тестовом режиме) — `shop_location()` → `Shop.shop_menu()` |
| `4` | 🏭 Работа — `work_location(state)` → `Work(state).work_choice()` |
| `5` | 🗺️ Приключение — `adventure_location(adventure_instance)` → `adventure_menu()` |
| `+` | Ручной ввод количества шагов (`steps_today_manual_entry()`) — перезаписывает `steps_today` максимумом из текущего и введённого |
| `m` / `ь` | Раздел "Меню" (заглушка) |
| `i` / `ш` | `inventory_menu()` — просмотр/продажа инвентаря |
| `e` / `у` | `Equipment.equipment_view()` — просмотр экипировки |
| `c` / `с` | `char_info()` — подробные характеристики |
| `u` / `г` | `CharLevel(state).menu_skill_point_allocation()` — распределение очков навыков |
| `l` / `д` | Загрузка сейва из Google Sheets (обновляет `game.state` in-place через `update_from_dict()` от `GameStateRepo().load()`) |
| `s` / `ы` | Сохранение: local CSV/JSON всегда, потом `GameStateRepo().save()` + `StepsLogRepo().append()` (источник `'manual'`) |
| `q` / `й` | Сохранение и выход (`sys.exit()`) |
| любое другое | Сообщение "Неизвестная команда. Попробуй ещё раз." |

Все буквенные команды дублируются в русской раскладке (одна и та же кнопка на клавиатуре). Дубли подтягиваются автоматически из таблицы `LAYOUT_RU_TO_EN` внутри `location_selection()` — одна точка правды для раскладки.

Диспатч построен на словаре `COMMANDS: dict[str, Callable]` + helper `enter_location(loc, enter_fn, can_reopen, call_map_on_switch)` внутри `location_selection()` (`game.py`), инкапсулирующий логику смены локации. Каждый вызов — `COMMANDS.get(user_input, unknown_command)()`.

### 2.3 Смена локации и `state.loc`

Когда игрок впервые выбирает локацию отличную от текущей, `state.loc` обновляется, а затем вызывается `location_change_map(state)`. Сейчас эта функция заглушка (без трат), но проектировалась как "стоимость перехода между локациями". Повторный вход в ту же локацию не меняет `state.loc` — это используется для Gym и Work (при повторном выборе сразу открывается меню, без стартового текста).

Логика живёт в helper-функции `enter_location(loc, enter_fn, can_reopen=False, call_map_on_switch=True)`:

```python
def enter_location(loc, enter_fn, can_reopen=False, call_map_on_switch=True):
    if state.loc != loc:
        state.loc = loc
        enter_fn()
        if call_map_on_switch:
            location_change_map(state)
    elif can_reopen:
        enter_fn()
```

Флаги по командам:
- `1`, `3`, `6`, `7`, `8` — дефолт (смена + `location_change_map`, без повторного захода).
- `2`, `4` — `can_reopen=True` (повторный вход снова открывает меню локации).
- `5` — `call_map_on_switch=False` (Adventure не вызывает `location_change_map()`) + колбэк `lambda: adventure_location(adventure_instance)` для передачи замкнутого `adventure_instance`.

---

## 3. Локации — как в них играется

**Pattern меню (после 0.2.1h / задача 1.5):** все локационные меню (Gym, Work, Adventure, Inventory, Equipment, Shop) обёрнуты в `while True` loop'ы. Невалидный ввод → `continue` (рендер меню повторяется), валидный выбор → `return`. Длинные меню (gym ~60 строк, adventure ~45 строк) выделены в helper-функции `_render_gym_menu(state, options)` / `Adventure._render_adventure_menu(self)` — чтобы тело loop'а оставалось читаемым. Раньше при невалиде функции вызывали себя рекурсивно (`return func(state)`), что строило стек и загрязняло трейсбэки; теперь чистая итеративная логика, идиоматическая для Python. Категория B (навигация между разными меню через прямой вызов соседней функции — `inventory_menu → sold_item → inventory_menu`) — отложена до задачи 1.1 (state machine).

### 3.1 Gym (Спортзал) — `gym.py`

Меню `gym_menu(state)` позволяет запустить тренировку одного из навыков. На каждый навык рассчитана стоимость следующего уровня по общей таблице `skill_training_table` (`skill_training_data.py`): `steps`, `energy`, `money`, `time` (в секундах).

Пункты меню Gym (23 навыка после 0.2.6a / 4.60):

1. Stamina — +1 % к общему количеству шагов.
2. Energy Max — +1 ед. к максимуму энергии.
3. Регенерация энергии — +1 % к скорости regen (0.2.4i / task 4.21 — отдельно от Speed).
4. Speed — +1 % к скорости активностей (работа, тренировки, приключения). НЕ влияет на regen с 0.2.4i.
5. Luck — +1 % к удаче (дропы).
6. Оптимизация движений Adventure — -1 % требуемых шагов для приключений.
7. Оптимизация движений Gym — -1 % шагов для тренировок.
8. Оптимизация движений Work — -1 % шагов для работы.
9. **Экономия энергии в Adventure** — -1 % энергии (мин 1) на приключения (0.2.4j / task 4.22).
10. **Экономия энергии в Gym** — -1 % энергии на тренировки (0.2.4j).
11. **Экономия энергии в Work** — -1 % к **total** энергии (per_hour × hours), не per-hour. Это убирает плато на low-base работах (0.2.4j).
12. Аккуратность при использовании вещей — -1 % к износу экипировки.
13-15. Money trilogy (Экономия денег / Бонус к зарплате / Торговец).
16-18. Bank-skills (Банковская ставка / Кредитный лимит / Снижение ставки по кредиту).
19. Обучение (Inspiration) — +1 % к XP.
20. Размер инвентаря — +1 слот к рюкзаку.
21. **Кузница: экономия шагов** (`forge_steps_saving`) — -1 % к шагам в ремонте/крафте (0.2.6a / task 4.60).
22. **Кузница: экономия золота** (`forge_money_saving`) — -1 % к золоту в ремонте/крафте.
23. **Кузница: качество ремонта** (`forge_repair_quality`) — множитель ×(1+lvl/100) к восстановленному quality за ремонт. Любой из навыков 21-23 ≥1 разблокирует локацию Кузница.

При выборе ресурсы списываются через `actions.try_spend(state, steps, energy, money)` (атомарно: либо все хватит и спишется, либо ничего), затем `actions.start_training(state, skill_name, time_end, ...)` выставляет `state.training.active=True`, `state.training.skill_name`, `state.training.time_end = now + time * speed_modifier`. Фактический прирост уровня навыка случится в `skill_training_check_done(state)` на следующем тике главного цикла.

`Energy Max`: после 0.2.1g (4.48.4.1) идёт через тот же общий путь, что остальные навыки — ключ переименован в `'energy_max_skill'` (соответствует field-name в `state.gym`). `state.energy_max` теперь — derived value: вычисляется через `bonus.compute_energy_max(state) = 50 + gym.energy_max_skill + equipment + daily_bonus + char_level.skill_energy_max`. Поле в dataclass осталось для save-format совместимости, но в логике игры читается только функция.

**Web (4.48.4 / 0.2.1e + 0.2.1g):** тот же модуль работает через 2 endpoint'а в `web/main.py` — `POST /web/gym/start` (Form → HTML fragment), `POST /api/gym/start` (JSON через `GymStartRequest`). Общий helper `_validate_and_apply_training(state, skill_name)` делает pre-flight проверку ресурсов и вызывает существующий `Skill_Training(state, name).start_skill_training()` + `Wear_Equipped_Items.decrease_durability` + `persist_state_to_cloud()`. Auto-finalize: `skill_training_check_done(state)` теперь вызывается в `_dashboard_context` — на каждый рендер web проверяет, не истёк ли таймер тренировки. UI: `<section id="gym">` свёрнута по умолчанию; внутри — 15 карточек навыков (после 0.2.4b: 4 базовых + 3 move_optimization + neatness + money_saving + earnings_boost + 3 банк-навыка + inspiration + backpack_skill) с pre-computed cost (`🏃 -N 🔋 -M 💰 -K 🕑 ~Xm`), кнопки disabled при нехватке ресурсов, `hx-confirm` перед стартом.

### 3.2 Work (Работа) — `work.py`

`Work(state).work_choice()`:

- Если персонаж ещё не работает (`state.work.active` is False) — показывает вакансии (сторож, завод, курьер, экспедитор), каждая со своей стоимостью в шагах/энергии за час и почасовой зарплатой. Стоимость шагов модифицируется `apply_move_optimization_work(steps, state)` (бонус от скилла).
- После выбора вакансии — `ask_hours(work)` рассчитывает максимум часов как `min(steps//req_steps, energy//req_energy, 8)` и спрашивает у игрока количество. `check_requirements` использует `try_spend` для списания и `actions.start_work(state, work_type, salary, hours, start, end)` — `state.work.end = now + hours*60s*speed_modifier`.
- Если персонаж уже работает — позволяет добавить часы к текущей смене (`add_working_hours`). Сменить вакансию посреди смены нельзя (ни в CLI, ни в web).

Фактическое начисление денег происходит в `work_check_done(state)`, когда `state.work.end <= now`: `state.money += state.work.salary * state.work.hours`, сбрасываются поля `state.work.*`. CLI вызывает `work_check_done` на каждом тике main loop'а; web — на каждом рендере `_dashboard_context()` (любой GET/POST автоматически закроет смену).

**Web (4.48.5):** тот же модуль работает через 4 endpoint'а в `web/main.py` — `POST /web/work/start` (Form), `POST /web/work/add_hours` (Form), `POST /api/work/start` (JSON), `POST /api/work/add_hours` (JSON). Все четыре проходят через общий helper `_validate_and_apply_work(state, work_type, hours)`, который под капотом дёргает тот же `Work.check_requirements()` + `Wear_Equipped_Items.decrease_durability()` что и CLI, и в конце вызывает `persist_state_to_cloud()` (CSV+JSON+Sheets, helper в `web/sync.py`). Без последнего шага смена жила бы только в RAM uvicorn'а — баг был обнаружен и исправлен в 0.2.1a. UI: блок `<details id="work">` в dashboard, свёрнут по умолчанию в обоих состояниях; внутри — меню вакансий или форма `+Nh` для активной смены. Кнопки часов содержат pre-computed формулу `Nh 🕑 real_time · 🏃 -steps · 🔋 -energy · 💰 +salary` (helper'ы `_build_hour_options(state, req, max_hours)` и `_format_real_time(minutes)` — переиспользуют `_speed_bonus_pct(state)` из work.py). Active sessions для work показывают только таймер до конца смены (без progress-bar и без % текста — упрощено в 0.2.1c).

### 3.3 Adventure (Приключение) — `adventure.py`

Реализовано через `Adventure(adventure_data_table, state)`. `__init__` строит словарь `self.adventures` со семью прогулками, применяя `apply_move_optimization_adventure()` к **копиям** записей (не мутируя статическую таблицу).

Прогулки открываются ступенчато — для разблокировки следующей нужно пройти предыдущую 3 раза (счётчики в `state.adventure.counters[walk_*]`):

| # | Название | Награда (grade) |
|---|---|---|
| 1 | walk_easy — Прогулка вокруг озера | C |
| 2 | walk_normal — Прогулка по району | C, B |
| 3 | walk_hard — Прогулка в лес | C, B, A |
| 4 | walk_15k — 15к шагов | B, A, S |
| 5 | walk_20k — 20к шагов | A, S, S+ |
| 6 | walk_25k — 25к шагов | S, S+ |
| 7 | walk_30k — 30к шагов | S+ |

Выбор приключения проходит через `adventure_choice` → `adventure_choice_confirmation` → `check_requirements`. В случае успеха: ресурсы списываются через `try_spend`, далее `actions.start_adventure(state, name, start_ts, end_ts)` выставляет `state.adventure.active=True`, `state.adventure.name`, `state.adventure.end_ts = now + time*speed_modifier`.

С 0.2.4f (4.29-replacement) каждый грейд в меню отображается с реальной вероятностью выпадения с учётом текущего luck: `(Награда: C-Grade [37.20%], B-Grade [33.36%])` (проценты в квадратных скобках). Расчёт — аналитический pure-helper `drop.compute_grade_probabilities(adv_name, state)` (без рандома). Item-type инфо («могут выпасть: ring · necklace · helmet · shoes · t-shirt по ~20% каждый») вынесена во вступительный текст т.к. одинакова для всех приключений. Тиры (grade, threshold) хранятся в `adventure_data.py['drops']` — единый источник правды для аналитики и реальной `one_item_random_grade()`.

С 0.2.4g (balance follow-up) S+ thresholds различаются по приключениям: walk_20k использует базовый `drop_percent_item_s_=15` (S+ — редкий бонус среди 3 тиров), walk_25k → `drop_percent_item_s_walk_25k=20`, walk_30k → `drop_percent_item_s_walk_30k=35`. Без этого walk_30k был неоправдан экономически (на luck=12 давал S+ 15.50% при цене +20% шагов/энергии/времени vs walk_25k S+ 14.09% + S 25.53%); теперь walk_30k явно позиционируется как endgame walk «специально за S+» (~36% S+ vs walk_25k ~18% при luck=12).

Дроп выполняется в `Adventure.adventure_check_done(self, state)` при возврате в главное меню после истечения таймера. `Drop_Item.item_collect(self=None, hard=name, state=state)` (`drop.py`) генерирует предмет со случайным `grade`, `item_type` (ring/necklace/…), `characteristic`, `bonus`, `quality`, `price`. Куда уходит предмет — зависит от состояния инвентаря (с 0.2.4c / задача 4.50.1): (1) есть место → `state.inventory.append(item)`; (2) полный + `state.pending_drop is None` → находка переносится в `state.pending_drop`, печатается одноразовое уведомление, resolve через `inventory_menu`; (3) полный + pending уже занят → forced sale (`state.money += new.price`, старый pending не трогается). Удача игрока считается через `current_luck(state) = state.gym.luck_skill + equipment_luck_bonus(state) + state.char_level.skill_luck` — пересчитывается на каждом дропе, прокачка применяется без рестарта.

### 3.4 Shop (Магазин) — `shop.py`

`Shop.shop_menu()` в тестовом режиме. Имеет подразделы: еда и вода (`shop_menu_food_and_water`), одежда (`shop_menu_clothes`), экипировка (`shop_menu_equipment`, заглушка), продажа вещей (`shop_menu_sell_items`, заглушка). Содержимое неполное, часть функций не реализована.

### 3.5 Home / Garage / Auto-dialer / Bank

В коде присутствуют (`locations.py`), но каждая из них печатает "Содержимое локации находится в разработке" и ничего не меняет.

---

## 4. Инвентарь, экипировка, уровень

### 4.1 Inventory (`i` в главном меню)

`inventory_menu(state)` (`inventory.py`) выводит список `state.inventory` (заголовок «Инвентарь N/cap» с 0.2.4b — где `cap = bonus.backpack_capacity(state) = 10 + state.gym.backpack_skill`), отсортированный по `item_type → characteristic → -bonus`. Доступные действия: `s` — продажа (`sold_item(state)`), `0` — выход. Чистая логика выделена: `_sort_inventory(inventory)` и `_sell_item_at_index(state, index)` тестируются напрямую.

С 0.2.4c (задача 4.50.1): если `state.pending_drop != None`, при заходе в Inventory сначала срабатывает `_pending_drop_prompt(state)` — показывает выпавшую находку и предлагает 3 опции: `1..N` (продать предмет №N из инвентаря, положить находку на освободившийся слот через `_resolve_pending_drop_sell_existing`), `s` (продать находку за base price через `_resolve_pending_drop_sell_new`), `0` (skip — pending остаётся, prompt появится при следующем заходе). Auto-collect: при освобождении слота между ходами (продажа / прокачка `backpack_skill` в Gym / снятие экипировки) `bonus.auto_collect_pending_drop(state)` в главном loop'е `game.py` без prompt'а кладёт находку в инвентарь и печатает «🎁 Освободилось место в рюкзаке...».

Покупка в Shop и снятие экипировки блокируются при полном рюкзаке: `shop._buy_item` и `equipment._unequip` возвращают False/None, UI печатает «Рюкзак полон (N/cap). Освободи слот: продай предмет или прокачай навык «Размер инвентаря».» Equip-swap (`_equip_from_inventory`) — net-zero, проверка пропускается.

Особенность: в текущей реализации почти все поля предмета хранятся как **списки** (`item['grade'][0]`, `item['bonus'][0]`, `item['quality'][0]` и т.п.) — это нужно, чтобы одна вещь могла иметь более одной характеристики. Если что-то показывается "не так" — первым делом проверь `[0]`.

### 4.2 Equipment (`e` в главном меню)

`Equipment.equipment_view(self=None, state=state)` (`equipment.py`) печатает 7 слотов (`state.equipment.{head, neck, torso, finger_01, finger_02, legs, foots}`) и позволяет надевать/снимать предметы. Чистая логика — `_equip_from_inventory(state, slot_attr, idx)` и `_unequip(state, slot_attr)` — тестируется напрямую. Износ при активностях (Gym/Work/Adventure) считается классом `Wear_Equipped_Items(state)` в `inventory.py`. Бонусы экипировки считаются функциями `equipment_stamina_bonus(state)`, `equipment_energy_max_bonus(state)`, `equipment_speed_skill_bonus(state)`, `equipment_luck_bonus(state)` (`equipment_bonus.py`).

### 4.3 Level и распределение очков (`u` в главном меню)

`CharLevel(state)` (`level.py`) считает уровень персонажа по `state.steps.total_used` (формула в `update_level`), рисует прогресс-бар через `progress_bar()`, и при `state.char_level.up_skills > 0` даёт пункт `menu_skill_point_allocation()` — распределить очки на один из: `state.char_level.{skill_stamina, skill_energy_max, skill_speed, skill_energy_regen, skill_luck}` (5 опций после 0.2.4i / 4.21 — добавлен skill_energy_regen).

**Web (4.48.8 / 0.2.1d):** тот же модуль работает через 2 endpoint'а в `web/main.py` — `POST /web/level/allocate` (Form → HTML fragment), `POST /api/level/allocate` (JSON через `SkillAllocateRequest`). Общий helper `_validate_and_apply_skill_allocation(state, skill)` валидирует skill name и наличие очков, мутирует `state.char_level.{skill_<X>, up_skills}` и зовёт `persist_state_to_cloud()`. UI: `<section id="skills">` рендерится только если `up_skills > 0` (или есть `skill_error` для race condition'а), свёрнута по умолчанию. 5 кнопок (с 0.2.4i / 4.21 — добавлена Energy Regen) с подтверждением через нативный browser confirm (HTMX `hx-confirm` атрибут) — игрок подтверждает каждый клик до отправки запроса. Без отмены (как в CLI). Важный prerequisite-фикс: `_dashboard_context` теперь зовёт `CharLevel(state).update_level()` на каждом рендере с persist'ом при фактическом level-up — до 0.2.1d web-only игрок никогда не апал уровень и не получал очков.

---

## 5. Шаги — откуда берутся и как тратятся

### 5.1 Источник: ручной ввод (команда `+`)

Единственный способ ввести количество пройденных шагов — команда `+` в главном меню. Вызывает `steps_today_manual_entry(state)` (`functions.py`): спрашивает число, валидирует, и записывает `max(текущее, введённое)` в `state.steps.today`. Использование `max(...)` — защита от случайного ввода меньшего значения (Mi Fitness может отстать; ручные показания с браслета обычно свежее).

Исторически существовал автообновлятор через Google Fit REST API (`api.py`, `get_token_fitnes_api.py`); удалён в задаче **4.16** (2026-04-27). Конвейер iPhone Shortcut → Sheets (задача **4.13**) был в плане, но отложен (01.05.2026) — ввод теперь идёт через CLI / Web / API (`POST /api/steps`, задача **4.48.2**). Max-merge для нескольких источников — задача **4.15**.

### 5.2 Агрегат `steps_can_use`

`save_game_date_last_enter(state)` (`functions.py`) на каждом тике:

1. **На новый день** (`now_date != date_last_enter`): переносит `steps_today → steps_yesterday`, увеличивает `steps_daily_bonus` если `steps_yesterday >= 10k` (иначе обнуляет), сбрасывает `steps_today_used = 0`, сбрасывает `steps_today = 0` (игрок вводит фактическое значение через `+`), обновляет `date_last_enter`. Legacy `save.txt` удалён в 0.2.0k (задача 2.1) — теперь единственный источник правды для day rollover это `state.date_last_enter`.
2. **Всегда** (в обеих ветках) пересчитывает `steps_can_use = steps_today - steps_today_used + stamina_skill_bonus + equipment_bonus_stamina_steps + daily_steps_bonus + level_steps_bonus`. Это нужно, чтобы первый кадр статус-бара после смены даты не показывал stale-значение из сейва (баг 2.9, закрыт 2026-04-27).

Функция вызывается неявно через `steps()` (`functions.py`), когда `status_bar()` и локации спрашивают "сколько шагов осталось".

### 5.3 Как локации их списывают

Локации (Gym, Work, Adventure) тратят ресурсы через `actions.try_spend(state, steps, energy, money)` — он атомарно увеличивает `state.steps.used` и `state.steps.total_used` на стоимость, уменьшает `state.steps.can_use`, `state.energy`, `state.money`. На следующем пересчёте через `save_game_date_last_enter` `state.steps.can_use` восстанавливается из `today - used + bonuses`.

---

## 6. Сохранение и загрузка

Сейв существует в трёх местах. Загрузка приоритезирует Google Sheets, сохранение пишет везде. Локальное (CSV/JSON) пишется всегда первым — даже если Sheets-вызов упадёт сетевой ошибкой, прогресс сохранён локально (offline-mode).

### 6.1 Локально (CSV + JSON)

- `characteristic.csv` — плоский CSV, пишется `save_characteristic()` (`characteristics.py`) через `game.state.to_dict()`, читается `load_characteristic()` и затем `GameState.from_dict()`. Вложенные словари/списки сериализуются через `json.dumps` и читаются обратно через `ast.literal_eval`. Поля `skill_training_time_end`, `working_end`, `adventure_end_timestamp` специально парсятся как `datetime` в формате `%Y-%m-%d %H:%M:%S.%f`.
- `characteristic.txt` — JSON-зеркало, тот же `to_dict()` формат.
- ~~`save.txt` — дата последнего входа~~ — удалён в 0.2.0k (задача 2.1). Источник правды для day rollover — `state.date_last_enter`.

### 6.2 Google Sheets

`google_sheets_db.py` использует `gspread` и сервис-аккаунт. После задачи **4.14** (01.05.2026) — два специализированных листа в одной таблице:

- Spreadsheet ID: `1l1SfzodtHAAIVsmsQjZPK2YEltilVzu5psv0_2p4MLM`.
  - Лист `game_state` — snapshot состояния (Key/Value layout). Переименован из `Sheet1`.
  - Лист `steps_log` — append-only лог замеров шагов. Колонки: `ts | user_id | steps | source`. `ts` — Unix timestamp (`float`), `source` — `'manual'` (CLI) / `'auto'` (отложено для iPhone) / `'web'` (будущий POST /api/steps).
- Файл ключей: `credentials/2walks_service_account.json`.
**API через классы:**
- `GameStateRepo.save(state_dict)` — пишет flat-dict (от `state.to_dict()`) на лист `game_state`. Перед записью делает `clear()`, потом `update(rows)`.
- `GameStateRepo.load() -> dict` — читает лист, восстанавливает типы (int/float/bool/None/list/dict/datetime), возвращает flat dict для `GameState.from_dict()` / `state.update_from_dict()`.
- `StepsLogRepo.append(ts, steps, source, user_id='alex')` — добавляет одну строку в `steps_log` (через gspread `append_row`).
- `StepsLogRepo.for_day(date_str, user_id='alex') -> list[dict]` — возвращает все записи за день для пользователя.
- **Max-merge (4.15)**: `characteristics.apply_steps_log_max_merge(state)` поднимает `state.steps.today` до максимума по записям лога за сегодня. Вызывается в `init_game_state()` (CLI start) и `web.sync.try_reload_state()` (web F5). Гарантирует, что ввод из любого канала (CLI / Web / API) виден на следующий старт даже если `game_state` snapshot ещё не обновлён.

**Lazy singleton client:** `_get_client()` авторизует gspread один раз за процесс (вместо ~0.5 сек на каждый save/load). Все Repo-классы переиспользуют один client.

**Migration:** при первом deploy на новое окружение — `python migrate_sheets.py` (idempotent: переименовывает `Sheet1`, создаёт `steps_log`).

**Когда пишется `steps_log`:**
- **CLI:** при явном `s` / `q` (Save / Save&Exit) — одна запись за сессию с актуальным `state.steps.today`. Сохраняет offline-mode (можно ввести шаги, передумать и выйти без save).
- **Web / API:** на каждый успешный `POST /web/steps` или `POST /api/steps` — мгновенная запись в момент ввода.

**Что делает max-merge при load:** игрок открывает CLI / делает F5 в браузере → загружается `game_state` snapshot + `apply_steps_log_max_merge` подтягивает максимум из `steps_log` за сегодня. Если CLI сохранился час назад с `today=872`, потом через web ввели `1500` — на следующем CLI start `state.steps.today` сразу будет `1500`, без необходимости сначала переоткрыть game_state в Sheets.

### 6.3 Команды игрока

- `s` — сохранить в CSV + Sheets.
- `l` — загрузить из Sheets. `GameStateRepo().load()` тянет лист `game_state`, потом `state.update_from_dict(...)` мутирует instance in-place — все модули, импортировавшие `game.state`, видят новые данные сразу, без рестарта.
- `q` — то же, что `s`, плюс `sys.exit()`.
- `Ctrl+C` / `Ctrl+D` — выход **без сохранения**. На верхнем уровне `game.py` обёрнут в `try/except (KeyboardInterrupt, EOFError):`, который печатает "Выход без сохранения. Пока!" и завершает процесс. Прогресс, не сохранённый через `s`/`q`, теряется — это сознательное поведение.

Реализация всех трёх игровых команд (`s`, `l`, `q`) — небольшие helper-функции внутри `location_selection()` (`game.py`).

---

## 7. Энергия, скорость, бонусы — формулы коротко

- **Регенерация энергии (после 0.2.4i / 4.21):** 1 единица за `bonus.energy_regen_interval(60, state)` секунд. Это `60 * (1 - (state.gym.energy_regen_skill + state.char_level.skill_energy_regen)/100)`. Equipment **не** учитывается в V1 (V2 / задача 4.57 добавит characteristic='energy_regen'). При +50 % бонуса одна энергия восстанавливается за 30 секунд. На максимуме (`state.energy == compute_energy_max(state)`) регенерация приостановлена — стамп двигается к `now`, время не банкуется. Длительность активностей (Gym/Work/Adventure) рассчитывается отдельно через `skill_bonus.speed_skill_equipment_and_level_bonus(time, state)` (использует speed_skill + equipment + char_level.skill_speed) — две независимые механики начиная с 0.2.4i.
- **Energy max (после 0.2.1g):** `bonus.compute_energy_max(state) = 50 + state.gym.energy_max_skill + equipment_energy_max_bonus(state) + state.steps.daily_bonus + state.char_level.skill_energy_max`. Поле `state.energy_max` — кэш для save-format, в логике игры читается только через эту функцию.
- **Время активностей (Gym/Work/Adventure):** `time * (1 - speed_bonus/100)` секунд.
- **Шаги за активность:** `base_steps * (1 - state.gym.move_optimization_<area>/100)` через `apply_move_optimization_*(steps, state)` из `bonus.py`.
- **Daily bonus:** +1 к `state.steps.daily_bonus` каждый день, если вчера было ≥ 10k шагов; иначе сброс в 0. Применяется и к `state.steps.can_use`, и к `compute_energy_max(state)` (через слагаемое в формуле).
- **Level bonus:** `level_steps_bonus(state)` добавляет шаги в зависимости от `state.char_level.skill_stamina`.
- **Luck (для дропа):** `current_luck(state) = state.gym.luck_skill + equipment_luck_bonus(state) + state.char_level.skill_luck`. Считается на каждом дропе — прокачка применяется без рестарта (закрыто в задаче 1.1).

---

## 8. Где смотреть исходники

- Игровой цикл и меню глобальной карты: `game.py` (функция `location_selection()`).
- Структура состояния: `state.py` (GameState + nested dataclasses), live instance — `characteristics.game.state` (через container `game = _GameContainer()`, заполняется `init_game_state()`).
- Регенерация и статус-бар: `functions.py` (`energy_time_charge`, `status_bar`).
- Навыки и тренировки: `gym.py` + таблицы `skill_training_table` / `get_energy_training_data` в `skill_training_data.py` (с 0.2.3e — раньше жили в `characteristics.py`).
- Работа: `work.py`.
- Приключения и дроп: `adventure.py`, `drop.py`, `adventure_data.py`.
- Инвентарь и экипировка: `inventory.py`, `equipment.py`, `equipment_bonus.py`.
- Уровень и очки: `level.py`.
- Сохранение/загрузка: `characteristics.py` (`load_characteristic`, `save_characteristic`, `init_game_state`), `google_sheets_db.py` (классы `GameStateRepo`, `StepsLogRepo`), `migrate_sheets.py` (one-shot миграция Sheets-листов).
- Helper'ы для не-тривиальных мутаций: `actions.py` (`try_spend`, `start_work`, `start_training`, `start_adventure`).
- Общие бонусы/формулы: `bonus.py`, `skill_bonus.py`.
- Настройки: `settings.py` (`debug_mode = True` добавляет много диагностики в `status_bar`, `energy_time_charge` и т.д.).
- Тесты: `tests/` — 156 юнит-тестов (`pytest tests/`).

Исторический лог версий — `changelog.txt`. Открытые баги — `bugs.txt`. Идеи — `ideas.txt`, `tasks.txt`.
