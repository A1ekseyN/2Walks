#pyinstaller --onefile --icon=icons/2walks.ico game.py

import os
import platform
import sys
from datetime import datetime

from colorama import init

from characteristics import (
    game,
    init_game_state,
)
from persistence import (
    handle_stale_prompt,
    save_characteristic,
)
from adventure import Adventure
from adventure_data import adventure_data_table
from bonus import auto_collect_pending_drop
from equipment import Equipment
from functions import (
    char_info,
    location_change_map,
    steps_today_manual_entry,
    steps_today_set,
    energy_time_charge,
    status_bar,
)
from google_sheets_db import GameStateRepo, StepsLogRepo
from gym import skill_training_check_done
from inventory import inventory_menu
from level import CharLevel
from triumphs_menu import open_triumphs_menu
from locations import (
    home_location,
    gym_location,
    shop_location,
    work_location,
    adventure_location,
    garage_location,
    auto_dialer_location,
    bank_location,
    forge_location,
)
from work import work_check_done


def play():
    """Главный игровой цикл. Требует, чтобы game.state был инициализирован
    через init_game_state() — обычно из __main__."""
    state = game.state
    if state is None:
        raise RuntimeError("game.state не инициализирован — вызови init_game_state() до play().")

    # 4.2 — «Пока тебя не было» report. Печатается единожды перед main loop'ом
    # если в Sheets `history` есть события с `ts >= prior_timestamp_last_enter`.
    # Очищает list после печати чтобы не повторяться.
    if state.startup_report:
        from report import format_report_cli
        print('\n' + format_report_cli(state.startup_report, state.startup_report_since_ts))
        state.startup_report = []

    while True:
        # Adventure пересоздаётся каждый цикл, чтобы adventure_requirements увидели
        # актуальную прокачку move_optimization_adventure (см. TASKS.md 2.3).
        adventure_instance = Adventure(adventure_data_table, state=state)

        def location_selection():
            def enter_location(loc, enter_fn, can_reopen=False, call_map_on_switch=True):
                """Смена локации: если уже там — молчим либо повторно показываем меню."""
                if state.loc != loc:
                    state.loc = loc
                    enter_fn()
                    if call_map_on_switch:
                        location_change_map(state)
                elif can_reopen:
                    enter_fn()

            def _sync_to_cloud() -> str:
                """Save game_state (CSV + Sheets save_safe) + лог замера шагов.

                4.54.4 — `save_characteristic()` теперь сам делает CSV+Sheets через
                save_safe (optimistic concurrency). Возвращает "OK"/"STALE".

                4.54.5 — на STALE вызывается `handle_stale_prompt()` с интерактивным
                Reload/Force/Cancel. После Force/Reload — повторный attempt:
                Force перезаписал Sheets (state синкан), Reload re-init'нул state.
                Cancel — возвращаем "STALE" вверх (caller сам решает что делать).
                """
                status = save_characteristic()
                if status == "STALE":
                    choice = handle_stale_prompt()
                    if choice == 'reload':
                        # Reload синкнул state с Sheets, но нашего save'а так и не
                        # произошло. Игрок может попробовать снова — но steps_log
                        # append не делаем (новые шаги уже потеряны, останутся
                        # только те что в Sheets).
                        return "STALE"
                    if choice == 'force':
                        # Force уже записал Sheets и обновил snapshot.
                        # steps_log append — для consistency с обычным OK flow.
                        StepsLogRepo().append(
                            ts=datetime.now().timestamp(),
                            steps=state.steps.today,
                            source='manual',
                        )
                        return "OK"
                    # cancel — возвращаем STALE наверх.
                    return "STALE"
                # OK — обычный append в steps_log.
                StepsLogRepo().append(
                    ts=datetime.now().timestamp(),
                    steps=state.steps.today,
                    source='manual',
                )
                return status

            def save_game_local_and_cloud():
                _sync_to_cloud()

            def save_and_exit():
                status = _sync_to_cloud()
                if status == "STALE":
                    # На STALE НЕ выходим — игрок ещё не разрешил конфликт
                    # (выбрал Cancel или Reload без последующего save). Лучше
                    # оставить в main loop, чтобы он мог попробовать снова
                    # или явно `q` ещё раз после Reload.
                    print('Save не выполнен. Вернись в меню и попробуй снова.')
                    return
                print('🚪 Спасибо за игру. До встречи.')
                sys.exit()

            def load_from_cloud():
                # update_from_dict мутирует существующий state — все импортёры,
                # удерживающие ссылку, видят новые данные без rebind.
                state.update_from_dict(GameStateRepo().load())

            def unknown_command():
                print('\nНеизвестная команда. Попробуй ещё раз.')

            COMMANDS = {
                # Локации
                '1': lambda: enter_location('home', lambda: home_location(state)),
                '2': lambda: enter_location('gym', lambda: gym_location(state), can_reopen=True),
                '3': lambda: enter_location('shop', lambda: shop_location(state)),
                '4': lambda: enter_location('work', lambda: work_location(state), can_reopen=True),
                '5': lambda: enter_location('adventure',
                                            lambda: adventure_location(adventure_instance),
                                            call_map_on_switch=False),
                '6': lambda: enter_location('garage', lambda: garage_location(state)),
                '7': lambda: enter_location('auto_dialer', lambda: auto_dialer_location(state)),
                '8': lambda: enter_location('bank', lambda: bank_location(state)),
                '9': lambda: enter_location('forge', lambda: forge_location(state)),
                # Шаги
                '+': lambda: steps_today_manual_entry(state),
                # Меню персонажа
                'm': lambda: print('\nРаздел "Меню" - (Пока не работает).'),
                'i': lambda: inventory_menu(state),
                'e': lambda: Equipment.equipment_view(self=None, state=state),
                'c': lambda: char_info(state),
                'u': lambda: CharLevel(state).menu_skill_point_allocation(),
                # 4.62.0.3 — Triumphs menu
                't': lambda: open_triumphs_menu(state),
                # Сохранение / загрузка
                'l': load_from_cloud,
                's': save_game_local_and_cloud,
                'q': save_and_exit,
            }

            LAYOUT_RU_TO_EN = {
                'ь': 'm', 'ш': 'i', 'у': 'e', 'с': 'c', 'г': 'u',
                'д': 'l', 'ы': 's', 'й': 'q', 'е': 't',
            }
            for cyr, lat in LAYOUT_RU_TO_EN.items():
                if lat in COMMANDS:
                    COMMANDS[cyr] = COMMANDS[lat]

            while True:
                energy_time_charge(state)
                work_check_done(state)
                skill_training_check_done(state)

                # 4.50.1 — Auto-collect pending drop если место освободилось
                # (например, прокачали backpack_skill в Gym или продали предмет).
                # На каждом тике дешёво: helper no-op'ит когда pending=None.
                # Печатаем уведомление только в момент перехода (helper вернул item).
                auto_collected = auto_collect_pending_drop(state)
                if auto_collected is not None:
                    print(f'\n🎁 Освободилось место в рюкзаке. Находка '
                          f'{auto_collected["grade"][0]} {auto_collected["item_type"][0].title()} '
                          f'+ {auto_collected["bonus"][0]} {auto_collected["characteristic"][0].title()} '
                          f'добавлена в инвентарь.')

                status_bar(state)

                print(f'Вы можете пройти в локацию:'
                      f'\n\t1. 🏠 Домой (Не работает)'
                      f'\n\t2. 🏋️ Спортзал'
                      f'\n\t3. 🛒 Магазин (В тестовом режиме)'
                      f'\n\t4. 🏭 Работа'
                      f'\n\t5. 🗺️ Приключение (В тестовом режиме)'
                      f'\n\t8. 🏛 Банк'
                      f'\n\t9. 🔨 Кузница (Каркас, MVP в работе)'
                      f'\n\t+. Ввести шаги вручную')
                print(f'\tm. Меню // '
                      f'i. 🎒 Инвентарь // '
                      f'e. 🎒 Экипировка // '
                      f'c. Характеристики // '
                      f'u. Level // '
                      f't. 🏆 Triumphs'
                      f'\n\tl. ☁ Load from Cloud'
                      f'\n\ts. 💾 Save Game'
                      f'\n\tq/e. 💾 + 🚪 Save & Exit')
                temp_number = input('Куда вы хотите пойти?:\n>>> ')

                # Inline-команда: "+1232" или "+ 1312" применяет шаги сразу.
                if temp_number.startswith('+') and temp_number != '+':
                    rest = temp_number[1:].strip()
                    if not rest:
                        steps_today_manual_entry(state)
                    else:
                        try:
                            steps_today_set(int(rest), state)
                        except ValueError:
                            print('Неверный формат. Ожидается "+N", где N — целое число.')
                else:
                    COMMANDS.get(temp_number, unknown_command)()

        # Запуск функции, которая относится к локациям.
        loc_dispatch = {
            'home': lambda: home_location(state),
            'gym': lambda: gym_location(state),
            'shop': lambda: shop_location(state),
            'work': lambda: work_location(state),
            'adventure': lambda: adventure_location(adventure_instance),
            'garage': lambda: garage_location(state),
            'auto_dialer': lambda: auto_dialer_location(state),
            'bank': lambda: bank_location(state),
            'forge': lambda: forge_location(state),
        }
        loc_handler = loc_dispatch.get(state.loc)
        if loc_handler is not None:
            loc_handler()
            location_selection()


if __name__ == "__main__":
    from version import VERSION
    print(f"Version: {VERSION}")
    # `chcp 65001` — Windows-only команда, переключает cmd.exe на UTF-8.
    # Без неё на Windows кириллица / эмодзи отображаются как «???».
    # На macOS / Linux команды нет — давала бы `sh: chcp: command not found`.
    if platform.system() == "Windows":
        os.system("chcp 65001")
    init()

    init_game_state()  # Загрузка из Sheets / CSV — отложена с импорта (1.2).

    try:
        play()
    except (KeyboardInterrupt, EOFError):
        print('\n\nВыход без сохранения. Пока!')
