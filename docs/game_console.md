# Консольная версия 2Walks — документация по запуску и игровому процессу

Этот документ описывает работу игры при запуске через `game.py`.

---

## 1. Запуск

### Команда

```bash
source .venv/bin/activate
python game.py
```

### Требования окружения

- Python 3.x с установленными зависимостями из `requirements.txt` (`colorama`, `gspread`, `oauth2client`).
- Терминал с UTF-8 (для эмодзи и русского текста). В `game.py:159` под Windows вызывается `os.system("chcp 65001")`.
- Опционально для облачного сохранения:
  - `credentials/2walks_service_account.json` — сервис-аккаунт для Google Sheets.

Без этого файла игра всё равно запустится: Google Sheets упадёт в фолбэк на CSV (`characteristic.csv`), основной цикл продолжит работать.

### Что происходит в момент запуска (до появления меню)

Порядок выполнения опирается на то, что Python исполняет код модулей при первом импорте. Важно помнить: **значительная часть "инициализации игры" — это побочные эффекты импорта `characteristics.py`**, а не вызов функции `game()`.

1. `game.py:158` выводит `Version: 0.1.2a` и переключает codepage.
2. Вызывается `game()` (`game.py:19`).
3. Первое, что делает `game()` — импортирует из `characteristics` всё через `from characteristics import *` (`game.py:9`). На этом импорте происходит:
   - `characteristics.py:101` — `load_data_from_google_sheet_or_csv()` пытается скачать сейв с Google Sheets (`google_sheets_db.py:51`), при неудаче читает `characteristic.csv`.
   - `characteristics.py:107` — строится основной словарь `char_characteristic` из загруженных полей и текущего `timestamp()`.
   - `steps_today` берётся из загруженного сейва (через `steps_today()` в `characteristics.py:12`). Сетевые запросы для шагов отсутствуют — поле обновляется только командой `+` или сбрасывается в 0 при смене даты.
   - `characteristics.py:204-206` дописывают к `energy_max` бонусы от экипировки, навыков и уровня.
4. Создаётся объект `Adventure(adventure_data_table)` (`game.py:24`) — нужен для меню приключений и предвычисленных бонусов.
5. Определяется внутренняя функция `location_selection()` (`game.py:26`). Главный цикл игры — именно она, не `game()`.
6. Проверяется `char_characteristic['loc']` из сохранения (`game.py:131`) и вызывается соответствующая локация (`home_location`, `gym_location`, `work_location`, `adventure_location`, ...), после чего запускается `location_selection()`.

### Глобальное состояние `char_characteristic`

Весь игровой процесс держится на одном общем словаре — `characteristics.char_characteristic`. Его импортируют напрямую почти все модули; мутация поля в одном модуле мгновенно видна во всех остальных.

Ключевые группы полей:

| Группа | Поля |
|---|---|
| Идентификатор дня и шаги | `date_last_enter`, `timestamp_last_enter`, `steps_today`, `steps_can_use`, `steps_today_used`, `steps_yesterday`, `steps_daily_bonus`, `steps_total_used` |
| Уровень и очки | `char_level`, `char_level_up_skills`, `lvl_up_skill_stamina`, `lvl_up_skill_energy_max`, `lvl_up_skill_speed`, `lvl_up_skill_luck` |
| Ресурсы | `energy`, `energy_max`, `energy_time_stamp`, `money` |
| Прокачиваемые навыки (Gym) | `stamina`, `energy_max_skill`, `speed_skill`, `luck_skill`, `neatness_in_using_things`, `move_optimization_adventure`, `move_optimization_gym`, `move_optimization_work` |
| Текущая тренировка | `skill_training`, `skill_training_name`, `skill_training_timestamp`, `skill_training_time_end` |
| Работа | `work`, `work_salary`, `working`, `working_hours`, `working_start`, `working_end` |
| Приключение | `adventure`, `adventure_name`, `adventure_start_timestamp`, `adventure_end_timestamp` + 7 счётчиков `adventure_walk_*_counter` |
| Инвентарь и экипировка | `inventory` (список словарей), `equipment_head`, `equipment_neck`, `equipment_torso`, `equipment_finger_01`, `equipment_finger_02`, `equipment_legs`, `equipment_foots` |
| Локация | `loc` (`home` / `gym` / `shop` / `work` / `adventure` / `garage` / `auto_dialer` / `bank`) |

При добавлении нового поля его нужно сохранить в трёх местах: `characteristic.csv`, `characteristic.txt` и Google Sheets (см. раздел "Сохранение и загрузка").

---

## 2. Главный цикл `location_selection()`

Функция `game.location_selection()` — бесконечный `while True`, который выводит глобальное меню, читает команду от игрока и делегирует действие локации. Итерация цикла состоит из трёх частей:

### 2.1 Tick-проверки перед выводом меню

В начале каждой итерации последовательно вызываются:

1. `energy_time_charge()` (`functions.py:18`) — регенерация энергии. Сравнивает текущий timestamp с `energy_time_stamp` и, если прошло достаточно секунд (по умолчанию 60, умноженное на модификатор скорости), начисляет по одной единице за каждый полный интервал. Остаток сохраняется в стампе (`stamp = now - remainder`), чтобы дробные секунды не терялись. При `energy >= energy_max` стамп сразу синкается к `now` — регенерация "не копится" пока энергия на максимуме, после траты отсчёт интервала начинается заново.
2. `work_check_done()` (`work.py:169`) — если персонаж на работе и `working_end <= now`, начисляет зарплату, тратит шаги и энергию, сбрасывает `working` и связанные поля.
3. `skill_training_check_done()` (`gym.py:201`) — если идёт тренировка и `skill_training_time_end <= now`, повышает уровень соответствующего навыка на 1, сбрасывает `skill_training*`.
4. `status_bar()` (`functions.py:42`) — печатает шаги, энергию, деньги, уровень, текущую локацию, а также информацию о текущей тренировке/работе/приключении с таймером до завершения.

Если активно `adventure=True`, `status_bar` вызовет `Adventure.adventure_check_done()` (`adventure.py:32`), которая при завершении прогулки дропнет предмет в `inventory` и поднимет соответствующий `adventure_walk_*_counter`.

Итог: **пока игрок не нажимает Enter, ничего не происходит**. Чтобы "получить" заработанные деньги или готовую экипировку, нужно вернуться в главное меню (отдать управление `location_selection()`).

### 2.2 Меню глобальной карты (`game.py:103-121`)

Игрок видит номера локаций и короткий список горячих клавиш:

| Ввод | Действие |
|---|---|
| `1` | 🏠 Домой (заглушка — `home_location()` только печатает текст) |
| `2` | 🏋️ Спортзал — `gym_location()` → `gym_menu()` |
| `3` | 🛒 Магазин (в тестовом режиме) — `shop_location()` → `Shop.shop_menu()` |
| `4` | 🏭 Работа — `work_location()` → `Work(char_characteristic).work_choice()` |
| `5` | 🗺️ Приключение — `adventure_location(adventure_instance)` → `adventure_menu()` |
| `+` | Ручной ввод количества шагов (`steps_today_manual_entry()`) — перезаписывает `steps_today` максимумом из текущего и введённого |
| `m` / `ь` | Раздел "Меню" (заглушка) |
| `i` / `ш` | `inventory_menu()` — просмотр/продажа инвентаря |
| `e` / `у` | `Equipment.equipment_view()` — просмотр экипировки |
| `c` / `с` | `char_info()` — подробные характеристики |
| `u` / `г` | `CharLevel(char_characteristic).menu_skill_point_allocation()` — распределение очков навыков |
| `l` / `д` | Загрузка сейва из Google Sheets (обновляет `char_characteristic` через `.update()`) |
| `s` / `ы` | Сохранение в CSV + Google Sheets |
| `q` / `й` | Сохранение и выход (`sys.exit()`) |
| любое другое | Сообщение "Неизвестная команда. Попробуй ещё раз." |

Все буквенные команды дублируются в русской раскладке (одна и та же кнопка на клавиатуре). Дубли подтягиваются автоматически из таблицы `LAYOUT_RU_TO_EN` внутри `location_selection()` — одна точка правды для раскладки.

Диспатч построен на словаре `COMMANDS: dict[str, Callable]` (`game.py:60-85`) + helper `enter_location(loc, enter_fn, can_reopen, call_map_on_switch)` (`game.py:31-40`), инкапсулирующий логику смены локации. Каждый вызов — `COMMANDS.get(user_input, unknown_command)()`.

### 2.3 Смена локации и `char_characteristic['loc']`

Когда игрок впервые выбирает локацию отличную от текущей, `loc` обновляется, а затем вызывается `location_change_map()` (`functions.py:291`). Сейчас эта функция заглушка (без трат), но проектировалась как "стоимость перехода между локациями". Повторный вход в ту же локацию `loc` не меняет — это используется для Gym и Work (при повторном выборе сразу открывается меню, без стартового текста).

Логика живёт в helper-функции `enter_location(loc, enter_fn, can_reopen=False, call_map_on_switch=True)`:

```python
def enter_location(loc, enter_fn, can_reopen=False, call_map_on_switch=True):
    current = char_characteristic['loc']
    if current != loc:
        char_characteristic['loc'] = loc
        enter_fn()
        if call_map_on_switch:
            location_change_map()
    elif can_reopen:
        enter_fn()
```

Флаги по командам:
- `1`, `3`, `6`, `7`, `8` — дефолт (смена + `location_change_map`, без повторного захода).
- `2`, `4` — `can_reopen=True` (повторный вход снова открывает меню локации).
- `5` — `call_map_on_switch=False` (Adventure не вызывает `location_change_map()`) + колбэк `lambda: adventure_location(adventure_instance)` для передачи замкнутого `adventure_instance`.

---

## 3. Локации — как в них играется

### 3.1 Gym (Спортзал) — `gym.py`

Меню (`gym_menu`, `gym.py:83`) позволяет запустить тренировку одного из навыков. На каждый навык рассчитана стоимость следующего уровня по общей таблице `skill_training_table` (`characteristics.py:209`): `steps`, `energy`, `money`, `time` (в секундах).

Пункты меню Gym:

1. Stamina — +1 % к общему количеству шагов.
2. Energy Max — +1 ед. к максимуму энергии.
3. Speed — +1 % к скорости всех активностей (работа, тренировки, приключения).
4. Luck — +1 % к удаче (дропы).
5. Оптимизация движений Adventure — -1 % требуемых шагов для приключений.
6. Оптимизация движений Gym — -1 % шагов для тренировок.
7. Оптимизация движений Work — -1 % шагов для работы.
8. Аккуратность при использовании вещей — -1 % к износу экипировки.

При выборе списываются `steps_today_used += steps`, `energy -= energy`, `money -= money`, ставится `skill_training = True`, `skill_training_name`, `skill_training_time_end = now + time * speed_modifier`. Фактический прирост уровня навыка случится в `skill_training_check_done()` на следующем тике главного цикла.

`Energy Max` идёт через отдельную таблицу `get_energy_training_data()` (`characteristics.py`), потому что `energy_max` начинается с 50 и его "уровень" вычитается из текущего значения минус бонусы экипировки и Daily.

### 3.2 Work (Работа) — `work.py`

`Work(char_characteristic).work_choice()` (`work.py:22`):

- Если персонаж ещё не работает — показывает вакансии (сторож, завод, курьер, экспедитор), каждая со своей стоимостью в шагах/энергии за час и почасовой зарплатой. Стоимость шагов модифицируется `apply_move_optimization_work()` (бонус от скилла).
- После выбора вакансии — `ask_hours()` рассчитывает максимум часов как `min(steps//req_steps, energy//req_energy, 8)` и спрашивает у игрока количество. Выставляет `working=True`, `work_salary`, `working_hours`, `working_start`, `working_end = now + hours*60s*speed_modifier`.
- Если персонаж уже работает — позволяет добавить часы к текущей смене (`add_working_hours`).

Фактическое начисление денег происходит в `work_check_done()` (`work.py:169`), когда `working_end <= now`: `money += salary * hours`, плюс списываются итоговые `steps` и `energy`, сбрасываются поля работы.

### 3.3 Adventure (Приключение) — `adventure.py`

Реализовано через `Adventure(adventure_data_table)` (`adventure.py:14`). `__init__` строит словарь `self.adventures` со семью прогулками, применяя `apply_move_optimization_adventure()` к требуемым шагам.

Прогулки открываются ступенчато — для разблокировки следующей нужно пройти предыдущую 3 раза (счётчики `adventure_walk_*_counter`):

| # | Название | Награда (grade) |
|---|---|---|
| 1 | walk_easy — Прогулка вокруг озера | C |
| 2 | walk_normal — Прогулка по району | C, B |
| 3 | walk_hard — Прогулка в лес | C, B, A |
| 4 | walk_15k — 15к шагов | B, A, S |
| 5 | walk_20k — 20к шагов | A, S, S+ |
| 6 | walk_25k — 25к шагов | S, S+ |
| 7 | walk_30k — 30к шагов | S+ |

Выбор приключения проходит через `adventure_choice` → `adventure_choice_confirmation` → `check_requirements`. В случае успеха: списываются ресурсы, `adventure=True`, `adventure_name`, `adventure_end_timestamp = now + time*speed_modifier`.

Дроп выполняется в `adventure_check_done()` (`adventure.py:32`) при возврате в главное меню после истечения таймера. `Drop_Item.item_collect(hard)` (`drop.py`) генерирует предмет со случайным `grade`, `item_type` (ring/necklace/…), `characteristic`, `bonus`, `quality`, `price`, и добавляет в `char_characteristic['inventory']`. Удача игрока (`luck_skill + equipment_luck_bonus + lvl_up_skill_luck`) влияет и на шанс дропа, и на качество.

### 3.4 Shop (Магазин) — `shop.py`

`Shop.shop_menu()` в тестовом режиме. Имеет подразделы: еда и вода (`shop_menu_food_and_water`), одежда (`shop_menu_clothes`), экипировка (`shop_menu_equipment`, заглушка), продажа вещей (`shop_menu_sell_items`, заглушка). Содержимое неполное, часть функций не реализована.

### 3.5 Home / Garage / Auto-dialer / Bank

В коде присутствуют (`locations.py`), но каждая из них печатает "Содержимое локации находится в разработке" и ничего не меняет.

---

## 4. Инвентарь, экипировка, уровень

### 4.1 Inventory (`i` в главном меню)

`inventory_menu()` (`inventory.py:5`) выводит список `char_characteristic['inventory']`, отсортированный по `item_type → characteristic → -bonus`. Доступные действия: `s` — продажа (`sold_item()`), `0` — выход.

Особенность: в текущей реализации почти все поля предмета хранятся как **списки** (`item['grade'][0]`, `item['bonus'][0]`, `item['quality'][0]` и т.п.) — это нужно, чтобы одна вещь могла иметь более одной характеристики. Если что-то показывается "не так" — первым делом проверь `[0]`.

### 4.2 Equipment (`e` в главном меню)

`Equipment.equipment_view()` (`equipment.py:9`) печатает 7 слотов (`head`, `neck`, `torso`, `finger_01`, `finger_02`, `legs`, `foots`) и позволяет надевать/снимать предметы через `Wear_Equipped_Items`. Надетые предметы вычитаются из инвентаря и записываются в соответствующий `equipment_*` ключ. Бонусы считаются функциями из `equipment_bonus.py`: `equipment_stamina_bonus`, `equipment_energy_max_bonus`, `equipment_speed_skill_bonus`, `equipment_luck_bonus`.

### 4.3 Level и распределение очков (`u` в главном меню)

`CharLevel(char_characteristic)` (`level.py`) считает уровень персонажа по суммарным `steps_total_used` (формула в `update_level`), рисует прогресс-бар через `progress_bar()`, и при `char_level_up_skills > 0` даёт пункт `menu_skill_point_allocation()` — распределить очки на один из: `lvl_up_skill_stamina`, `lvl_up_skill_energy_max`, `lvl_up_skill_speed`, `lvl_up_skill_luck`.

---

## 5. Шаги — откуда берутся и как тратятся

### 5.1 Источник: ручной ввод (команда `+`)

Единственный способ ввести количество пройденных шагов — команда `+` в главном меню. Вызывает `steps_today_manual_entry()` (`functions.py`): спрашивает число, валидирует, и записывает `max(текущее, введённое)` в `char_characteristic['steps_today']`. Использование `max(...)` — защита от случайного ввода меньшего значения (Mi Fitness может отстать; ручные показания с браслета обычно свежее).

Исторически существовал автообновлятор через Google Fit REST API (`api.py`, `get_token_fitnes_api.py`); удалён в задаче **4.16** (2026-04-27). Будущий конвейер iPhone → Google Sheets через iOS Shortcut запланирован в задачах **4.13–4.15**.

### 5.2 Агрегат `steps_can_use`

`save_game_date_last_enter()` (`functions.py:96`) на каждом тике:

1. **На новый день** (`now_date != date_last_enter`): пишет дату в `save.txt`, переносит `steps_today → steps_yesterday`, увеличивает `steps_daily_bonus` если `steps_yesterday >= 10k` (иначе обнуляет), сбрасывает `steps_today_used = 0`, сбрасывает `steps_today = 0` (игрок вводит фактическое значение через `+`), обновляет `date_last_enter`.
2. **Всегда** (в обеих ветках) пересчитывает `steps_can_use = steps_today - steps_today_used + stamina_skill_bonus + equipment_bonus_stamina_steps + daily_steps_bonus + level_steps_bonus`. Это нужно, чтобы первый кадр статус-бара после смены даты не показывал stale-значение из сейва (баг 2.9, закрыт 2026-04-27).

Функция вызывается неявно через `steps()` (`functions.py`), когда `status_bar()` и локации спрашивают "сколько шагов осталось".

### 5.3 Как локации их списывают

Локации (Gym, Work, Adventure) увеличивают `char_characteristic['steps_today_used']` на стоимость активности. Это неявно уменьшает `steps_can_use` на следующем пересчёте. Одновременно `steps_total_used` копится для расчёта уровня.

---

## 6. Сохранение и загрузка

Сейв существует в трёх местах. Загрузка приоритезирует Google Sheets, сохранение пишет везде.

### 6.1 Локально (CSV + JSON)

- `characteristic.csv` — плоский CSV, пишется `save_characteristic()` (`characteristics.py:458`), читается `load_characteristic()` (`characteristics.py:22`). Вложенные словари/списки сериализуются через `repr()` и читаются обратно через `ast.literal_eval`. Поля `skill_training_time_end`, `working_end`, `adventure_end_timestamp` специально парсятся как `datetime` в формате `%Y-%m-%d %H:%M:%S.%f`.
- `characteristic.txt` — JSON-зеркало, используется `google_sheets_db.py` для выгрузки в облако.
- `save.txt` — дата последнего входа в игру (одна строка).

### 6.2 Google Sheets

`google_sheets_db.py` использует `gspread` и сервис-аккаунт:

- Spreadsheet ID: `1l1SfzodtHAAIVsmsQjZPK2YEltilVzu5psv0_2p4MLM`, sheet `Sheet1`.
- Файл ключей: `credentials/2walks_service_account.json`.
- `save_char_characteristic_to_google_sheet()` — читает `characteristic.txt` (JSON), сериализует списки/словари/datetime и заливает в лист Key/Value.
- `load_char_characteristic_from_google_sheet()` — читает лист, восстанавливает типы, отдельно парсит datetime-поля.

### 6.3 Команды игрока

- `s` — сохранить в CSV + Sheets.
- `l` — загрузить из Sheets. Обновляет `char_characteristic` через `.update()` — все модули, импортировавшие его, видят новые данные сразу, без рестарта.
- `q` — то же, что `s`, плюс `sys.exit()`.
- `Ctrl+C` / `Ctrl+D` — выход **без сохранения**. На верхнем уровне `game.py:161-164` обёрнут в `try/except (KeyboardInterrupt, EOFError):`, который печатает "Выход без сохранения. Пока!" и завершает процесс. Прогресс, не сохранённый через `s`/`q`, теряется — это сознательное поведение.

Реализация всех трёх игровых команд (`s`, `l`, `q`) — небольшие helper-функции внутри `location_selection()` (`game.py:42-54`).

---

## 7. Энергия, скорость, бонусы — формулы коротко

- **Регенерация энергии:** 1 единица за `speed_skill_equipment_and_level_bonus(60)` секунд. Это `60 * (1 - (speed_skill + equipment_speed_bonus + lvl_up_skill_speed)/100)`. То есть при +50 % скорости одна энергия восстанавливается за 30 секунд. На максимуме (`energy == energy_max`) регенерация приостановлена — стамп двигается к `now`, время не банкуется.
- **Время активностей (Gym/Work/Adventure):** `time * (1 - speed_bonus/100)` секунд.
- **Шаги за активность:** `base_steps * (1 - move_optimization_<area>/100)` через `apply_move_optimization_*()` из `bonus.py`.
- **Daily bonus:** +1 к `steps_daily_bonus` каждый день, если вчера было ≥ 10k шагов; иначе сброс в 0. Применяется и к `steps_can_use`, и к `energy_max`.
- **Level bonus:** `level_steps_bonus()` добавляет шаги в зависимости от `char_level`.
- **Luck (для дропа):** `luck_skill + equipment_luck_bonus + lvl_up_skill_luck`. Встроен в `drop.Drop_Item` как глобальная переменная `luck_chr`, рассчитывается при импорте модуля. Если удача меняется в рантайме, модуль `drop` её не пересчитывает до перезапуска — существующая ловушка.

---

## 8. Где смотреть исходники

- Игровой цикл: `game.py`.
- Tick-проверки и меню глобальной карты: `game.py:26-128`.
- Регенерация и статус-бар: `functions.py:18`, `functions.py:42`.
- Навыки и тренировки: `gym.py` + таблицы в `characteristics.py:209`.
- Работа: `work.py`.
- Приключения и дроп: `adventure.py`, `drop.py`, `adventure_data.py`.
- Инвентарь и экипировка: `inventory.py`, `equipment.py`, `equipment_bonus.py`.
- Уровень и очки: `level.py`.
- Сохранение/загрузка: `characteristics.py:22`, `characteristics.py:458`, `google_sheets_db.py`.
- Общие бонусы/формулы: `bonus.py`, `skill_bonus.py`.
- Настройки: `settings.py` (`debug_mode = True` добавляет много диагностики в `status_bar`, `energy_time_charge` и т.д.).

Исторический лог версий — `changelog.txt`. Открытые баги — `bugs.txt`. Идеи — `ideas.txt`, `tasks.txt`.
