"""Adventure — приключения, проверка таймера, дроп предметов."""

from datetime import datetime
from colorama import Fore, Style

from adventure_data import adventure_data_table
from colors import steps_color, energy_color
from drop import Drop_Item
from functions_02 import time
from skill_bonus import speed_skill_equipment_and_level_bonus
from settings import debug_mode
from bonus import apply_move_optimization_adventure
from inventory import Wear_Equipped_Items
from actions import try_spend, start_adventure as actions_start_adventure
from state import GameState


# Маппинг adventure_name → ключ adventure.counters в state.
_ADV_COUNTER_KEYS = {
    'walk_easy': 'walk_easy',
    'walk_normal': 'walk_normal',
    'walk_hard': 'walk_hard',
    'walk_15k': 'walk_15k',
    'walk_20k': 'walk_20k',
    'walk_25k': 'walk_25k',
    'walk_30k': 'walk_30k',
}


class Adventure:
    """Приключения: меню, выбор, старт, финализация."""

    def __init__(self, adventure_data_table, state: GameState):
        self._state = state
        self.adventure_data_table = adventure_data_table
        self.adventures = {
            '1': {'name': 'walk_easy', 'data': apply_move_optimization_adventure(dict(adventure_data_table['walk_easy']), self._state)},
            '2': {'name': 'walk_normal', 'data': apply_move_optimization_adventure(dict(adventure_data_table['walk_normal']), self._state)},
            '3': {'name': 'walk_hard', 'data': apply_move_optimization_adventure(dict(adventure_data_table['walk_hard']), self._state)},
            '4': {'name': 'walk_15k', 'data': apply_move_optimization_adventure(dict(adventure_data_table['walk_15k']), self._state)},
            '5': {'name': 'walk_20k', 'data': apply_move_optimization_adventure(dict(adventure_data_table['walk_20k']), self._state)},
            '6': {'name': 'walk_25k', 'data': apply_move_optimization_adventure(dict(adventure_data_table['walk_25k']), self._state)},
            '7': {'name': 'walk_30k', 'data': apply_move_optimization_adventure(dict(adventure_data_table['walk_30k']), self._state)},
        }
        self.adventure_requirements = {}
        for key, adv in self.adventures.items():
            self.adventure_requirements[key] = (
                f'🏃: {steps_color(adv["data"]["steps"])} шагов, '
                f'🔋: {energy_color(adv["data"]["energy"])} энергии, '
                f'🕑: {time(speed_skill_equipment_and_level_bonus(adv["data"]["time"], self._state))}'
            )

    def adventure_check_done(self, state: GameState = None):
        """Финализатор приключения по таймеру: дроп + инкремент счётчика + clear.

        Поддерживает legacy-вызов `Adventure.adventure_check_done(self=None, state=state)` —
        в этом случае state приходит явно. Иначе берётся из self._state.
        """
        if state is None and self is not None:
            state = self._state
        if not state.adventure.active:
            return

        if state.adventure.end_ts <= datetime.now().timestamp():
            print('\n🗺 Приключение пройдено. 🗺')
            adv_name = state.adventure.name
            if adv_name in _ADV_COUNTER_KEYS:
                Drop_Item.item_collect(self=None, hard=adv_name, state=state)
                counter_key = _ADV_COUNTER_KEYS[adv_name]
                state.adventure.counters[counter_key] = state.adventure.counters.get(counter_key, 0) + 1

            state.adventure.active = False
            state.adventure.name = None
            state.adventure.end_ts = None
        elif state.adventure.end_ts > datetime.now().timestamp():
            adv_end = datetime.fromtimestamp(state.adventure.end_ts) - datetime.fromtimestamp(datetime.now().timestamp())
            adv_end = str(adv_end).split('.')[0]
            print(f'\t🗺️ Персонаж находится в Приключении: {state.adventure.name.title()}.')
            print(f'\t🕑 Персонаж вернется через: {Fore.LIGHTBLUE_EX}{adv_end}{Style.RESET_ALL}')

    def _render_adventure_menu(self):
        """Печать меню приключений с условной разблокировкой по counters.
        Вынесено в helper (1.5.5 — 0.2.1h), чтобы тело adventure_menu loop'а
        не раздувалось до 50 строк."""
        state = self._state
        print('\n ️🗺 ️--- Меню Приключения --- 🗺️')
        print(f"Steps 🏃: {state.steps.can_use}, Energy 🔋: {state.energy}, Money 💰: {state.money} $,")
        print('Вы можете отправить персонажа в приключение.'
              '\nВ приключении, персонаж может получить полезные предметы.')

        print('\nДоступные приключения: ')
        counters = state.adventure.counters
        print(f'\t1. Прогулка вокруг озера: {self.get_adventure_requirement("walk_easy")} - (Награда: C-Grade (Ring, Necklace))')

        if counters.get('walk_easy', 0) >= 3:
            print(f'\t2. Прогулка по району:    {self.get_adventure_requirement("walk_normal")} - (Награда: C-Grade, B-Grade (Ring, Necklace))')
        else:
            print(f'\t- Пройдите "Прогулку вокруг озера" ещё: {3 - counters.get("walk_easy", 0)} раз.')

        if counters.get('walk_normal', 0) >= 3:
            print(f'\t3. Прогулка в лес:        {self.get_adventure_requirement("walk_hard")} - (Награда: C-Grade, B-Grade, A-Grade (Ring, Necklace))')
        else:
            print(f'\t- Пройдите "Прогулку по району" ещё: {3 - counters.get("walk_normal", 0)} раз.')

        if counters.get('walk_hard', 0) >= 3:
            print(f'\t4. Прогулка 15к шагов:    {self.get_adventure_requirement("walk_15k")} - (Награда: B-Grade, A-Grade, S-Grade)')
        else:
            print(f'\t- Пройдите "Прогулку в лес" ещё: {3 - counters.get("walk_hard", 0)} раз.')

        if counters.get('walk_15k', 0) >= 3:
            print(f'\t5. Прогулка 20к шагов:    {self.get_adventure_requirement("walk_20k")} - (Награда: A-Grade, S-Grade, S+Grade (Ring, Necklace))')
        else:
            print(f'\t- Пройдите прогулку на 15к ещё: {3 - counters.get("walk_15k", 0)} раз.')

        if counters.get('walk_20k', 0) >= 3:
            print(f'\t6. Прогулка 25к шагов:    {self.get_adventure_requirement("walk_25k")} - (Награда: S-Grade, S+Grade (Ring, Necklace))')
        else:
            print(f'\t- Пройдите прогулку на 20к ещё: {3 - counters.get("walk_20k", 0)} раз.')

        if counters.get('walk_25k', 0) >= 3:
            print(f'\t7. Прогулка 30к шагов:    {self.get_adventure_requirement("walk_30k")} - (Награда: S+Grade (Ring, Necklace))')
        else:
            print(f'\t- Пройдите прогулку на 25к ещё: {3 - counters.get("walk_25k", 0)} раз.')

        print('\t0. Выход')

    def adventure_menu(self):
        # adventure_menu теперь только entry-point — вся retry-логика в
        # adventure_choice (1.5.5 — 0.2.1h, было: ping-pong рекурсия через
        # 2 функции).
        self.adventure_choice()

    def adventure_choice(self):
        # Цикл retry на невалиде (1.5.5 — 0.2.1h). Меню перерисовывается
        # на каждой итерации через _render_adventure_menu().
        while True:
            self._render_adventure_menu()
            ask = input('\nВыберите локацию, в которую хотите отправиться:\n>>> ')
            if ask in self.adventures:
                adv = self.adventures[ask]
                adv_name = adv['name']
                adv_data = adv['data']
                adv_req = self.adventure_requirements[ask]
                adv_steps = adv_data['steps']
                adv_energy = adv_data['energy']
                adv_time = speed_skill_equipment_and_level_bonus(adv_data['time'], self._state)
                # confirmation возвращает True (старт) / False (назад → пере-меню).
                started = self.adventure_choice_confirmation(adv_name, adv_req, adv_steps, adv_energy, adv_time)
                if started:
                    return
                continue
            if ask == '0':
                return

    def adventure_choice_confirmation(self, adv_name, adv_req, adv_steps, adv_energy, adv_time):
        # Цикл retry на невалиде (1.5.5 — 0.2.1h). Возвращает True если
        # приключение фактически стартовало (ресурсы хватили), иначе False
        # — caller (adventure_choice) перерисует меню.
        while True:
            print(f'\nВы выбрали приключение: {adv_name}.'
                  f'\nДля прохождения приключения необходимо: {adv_req}'
                  '\n\t1. Пройти Приключение.'
                  '\n\t0. Назад.')
            ask = input('\n>>> ')
            if ask == '1':
                return self.check_requirements(adv_name, adv_steps, adv_energy, adv_time)
            if ask == '0':
                return False

    def check_requirements(self, adv_name, adv_steps, adv_energy, adv_time):
        state = self._state
        if not try_spend(state, steps=adv_steps, energy=adv_energy):
            if state.steps.can_use < adv_steps:
                print('\n- Не достаточно: 🏃 шагов.')
            if state.energy < adv_energy:
                print('- Не достаточно: 🔋 энергии.')
            return False

        print('\nПроверка требований успешна.')
        self._enter_adventure(adv_name, adv_steps, adv_energy, adv_time)
        Wear_Equipped_Items(state).decrease_durability(adv_steps)
        return True

    def _enter_adventure(self, adv_name, adv_steps, adv_energy, adv_time):
        """Старт приключения после try_spend (списание уже произошло)."""
        state = self._state
        print(f'\nНачало приключения: {adv_name}')
        now_ts = int(datetime.now().timestamp())
        actions_start_adventure(
            state,
            name=adv_name,
            start_ts=now_ts,
            end_ts=now_ts + (adv_time * 60),
        )

        print(f'Steps_used_today 🏃: {state.steps.used}')
        print(f'Energy used 🔋: {adv_energy}')
        if debug_mode:
            print(f'Energy Left: {state.energy}')
            print(f'Время_now: {datetime.now().timestamp()}')
            print(f'Время прохождения Приключения: {state.adventure.end_ts - datetime.now().timestamp()}')
        return state

    # Сохраняем legacy-имя для совместимости с возможными внешними вызовами.
    def start_adventure(self, adv_name, adv_steps, adv_energy, adv_time):
        return self._enter_adventure(adv_name, adv_steps, adv_energy, adv_time)

    def get_adventure_requirement(self, adventure_key):
        base = self.adventure_data_table[adventure_key]
        final_time = speed_skill_equipment_and_level_bonus(base['time'], self._state)
        return (
            f'🏃: {steps_color(base["steps"])} шагов, '
            f'🔋: {energy_color(base["energy"])} энергии, '
            f'🕑: {time(final_time)}'
        )
