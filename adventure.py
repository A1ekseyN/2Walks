"""Adventure — приключения, проверка таймера, дроп предметов."""

from datetime import datetime
from typing import Any, Optional

from colorama import Fore, Style

from adventure_data import adventure_data_table
from colors import steps_color, energy_color
from drop import Drop_Item, compute_grade_probabilities
from functions_02 import format_money, format_timedelta, time
from skill_bonus import speed_skill_equipment_and_level_bonus
from settings import debug_mode
from bonus import apply_energy_optimization_adventure, apply_move_optimization_adventure
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

    def __init__(self, adventure_data_table: dict, state: GameState) -> None:
        self._state = state
        self.adventure_data_table = adventure_data_table
        # dict[str, dict[str, Any]] — внутренние values имеют mixed types
        # ('name': str, 'data': dict). Без явного annotate mypy выводит
        # Collection[Any] и индексация adv['data']['steps'] становится ошибкой.
        # Since 0.2.4j (task 4.22) — apply_energy_optimization_adventure после
        # apply_move_optimization_adventure: первая мутирует 'steps', вторая 'energy'.
        def _prepare_adv(name: str) -> dict:
            data = dict(adventure_data_table[name])
            data = apply_move_optimization_adventure(data, self._state)
            data = apply_energy_optimization_adventure(data, self._state)
            return data

        self.adventures: dict[str, dict[str, Any]] = {
            '1': {'name': 'walk_easy', 'data': _prepare_adv('walk_easy')},
            '2': {'name': 'walk_normal', 'data': _prepare_adv('walk_normal')},
            '3': {'name': 'walk_hard', 'data': _prepare_adv('walk_hard')},
            '4': {'name': 'walk_15k', 'data': _prepare_adv('walk_15k')},
            '5': {'name': 'walk_20k', 'data': _prepare_adv('walk_20k')},
            '6': {'name': 'walk_25k', 'data': _prepare_adv('walk_25k')},
            '7': {'name': 'walk_30k', 'data': _prepare_adv('walk_30k')},
        }
        self.adventure_requirements = {}
        for key, adv in self.adventures.items():
            self.adventure_requirements[key] = (
                f'🏃: {steps_color(adv["data"]["steps"])} шагов, '
                f'🔋: {energy_color(adv["data"]["energy"])} энергии, '
                f'🕑: {time(speed_skill_equipment_and_level_bonus(adv["data"]["time"], self._state))}'
            )

    def adventure_check_done(self, state: Optional[GameState] = None,
                             deferred_events: Optional[list] = None) -> None:
        """Финализатор приключения по таймеру: дроп + инкремент счётчика + clear.

        Поддерживает legacy-вызов `Adventure.adventure_check_done(self=None, state=state)` —
        в этом случае state приходит явно. Иначе берётся из self._state.

        4.48.5.1.1 — `deferred_events`: если передан список, события `drop*` /
        `adventure_done` складываются в него (через `emit_or_defer`) вместо
        немедленного `log_event`. Caller (web `_finalize_adventure_with_drop_capture`)
        логирует их ПОСЛЕ успешного save commit — при STALE rollback'е phantom-записи
        не попадают в history (искажали бы triumph-backfill, 4.6.1 / 4.62). None
        (CLI) → лог сразу, поведение не меняется.
        """
        if state is None and self is not None:
            state = self._state
        if not state.adventure.active:
            return

        if state.adventure.end_ts <= datetime.now().timestamp():
            print('\n🗺 Приключение пройдено. 🗺')
            adv_name = state.adventure.name
            if adv_name in _ADV_COUNTER_KEYS:
                Drop_Item.item_collect(self=None, hard=adv_name, state=state,
                                       deferred_events=deferred_events)
                counter_key = _ADV_COUNTER_KEYS[adv_name]
                state.adventure.counters[counter_key] = state.adventure.counters.get(counter_key, 0) + 1

            # 4.6 — log_event завершения приключения. Drop фиксируется отдельно
            # внутри Drop_Item.item_collect (если был).
            # 4.48.5.1.1 — emit_or_defer: при STALE save-rollback'е не оставляем
            # phantom 'adventure_done' в history.
            from history import emit_or_defer
            emit_or_defer(deferred_events, 'adventure_done', name=adv_name)

            state.adventure.active = False
            state.adventure.name = None
            state.adventure.end_ts = None
        elif state.adventure.end_ts > datetime.now().timestamp():
            adv_end = format_timedelta(
                datetime.fromtimestamp(state.adventure.end_ts) - datetime.fromtimestamp(datetime.now().timestamp())
            )
            print(f'\t🗺️ Персонаж находится в Приключении: {state.adventure.name.title()}.')
            print(f'\t🕑 Персонаж вернется через: {Fore.LIGHTBLUE_EX}{adv_end}{Style.RESET_ALL}')

    def _render_adventure_menu(self) -> None:
        """Печать меню приключений с условной разблокировкой по counters.
        Вынесено в helper (1.5.5 — 0.2.1h), чтобы тело adventure_menu loop'а
        не раздувалось до 50 строк.

        Since 0.2.4f (4.29-replacement): % вероятности выпадения каждого грейда
        рассчитываются через `compute_grade_probabilities` (учитывает current_luck)
        и встраиваются в строку «Награда: <Grade> (XX.XX%)». Item-type инфо
        («могут выпасть: ring · necklace · ...») вынесена во вступительный
        блок т.к. она одинакова для ВСЕХ приключений (drop.py:item_type
        сэмплит 5 типов с равной вероятностью независимо от hard'а).
        """
        state = self._state
        print('\n ️🗺 ️--- Меню Приключения --- 🗺️')
        print(f"Steps 🏃: {state.steps.can_use}, Energy 🔋: {state.energy}, Money 💰: {format_money(state.money)} $,")
        print('Вы можете отправить персонажа в приключение.'
              '\nВ приключении, персонаж может получить полезные предметы.'
              '\n🎁 Могут выпасть: ring · necklace · helmet · shoes · t-shirt (по ~20% каждый).')

        print('\nДоступные приключения: ')
        # 4.34 — data-driven рендер цепочки разблокировки. Прогресс-бар (как в
        # Triumphs, глифы ▰▱) показывается только у ПЕРВОЙ запертой прогулки
        # (реально прокачиваемой); более глубокие — просто «🔒 заблокировано».
        from adventure_data import (
            ADVENTURE_PREREQ, ADVENTURE_RU_LABELS, ADVENTURE_UNLOCK_THRESHOLD,
        )
        from triumphs import _format_progress_bar

        counters = state.adventure.counters
        threshold = ADVENTURE_UNLOCK_THRESHOLD
        first_locked_shown = False
        for key, adv in self.adventures.items():
            adv_name = adv['name']
            label = ADVENTURE_RU_LABELS[adv_name]
            prereq = ADVENTURE_PREREQ.get(adv_name)
            unlocked = prereq is None or counters.get(prereq, 0) >= threshold
            if unlocked:
                print(f'\t{key}. {label}: {self.get_adventure_requirement(adv_name)} '
                      f'- (Награда: {self._format_reward(adv_name)})')
            elif not first_locked_shown:
                cur = min(counters.get(prereq, 0), threshold)
                bar = _format_progress_bar(cur, threshold, width=threshold)
                pct = round(cur / threshold * 100)
                print(f'\t- 🔒 {label}: {bar} {cur}/{threshold} ({pct}%) '
                      f'— пройдите «{ADVENTURE_RU_LABELS[prereq]}»')
                first_locked_shown = True
            else:
                print(f'\t- 🔒 {label}: заблокировано')

        print('\t0. Выход')

    def _format_reward(self, adventure_name: str) -> str:
        """4.29-replacement (0.2.4f) — формирует строку наград с % выпадения.

        Пример: 'C-Grade (37.20%), B-Grade (33.36%)' для walk_normal.
        Учитывает текущий luck игрока через compute_grade_probabilities.
        Грейд 'nothing' (вероятность miss'а) не отображается — игрок видит
        только потенциальные награды.
        """
        probs = compute_grade_probabilities(adventure_name, self._state)
        parts = [
            f'{grade.title()} [{pct * 100:.2f}%]'
            for grade, pct in probs.items()
            if grade != 'nothing' and pct > 0
        ]
        return ', '.join(parts) if parts else '—'

    def adventure_menu(self) -> None:
        # adventure_menu теперь только entry-point — вся retry-логика в
        # adventure_choice (1.5.5 — 0.2.1h, было: ping-pong рекурсия через
        # 2 функции).
        self.adventure_choice()

    def adventure_choice(self) -> None:
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

    def adventure_choice_confirmation(self, adv_name: str, adv_req: str,
                                       adv_steps: int, adv_energy: int,
                                       adv_time: int) -> bool:
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

    def check_requirements(self, adv_name: str, adv_steps: int,
                           adv_energy: int, adv_time: int) -> bool:
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

    def _enter_adventure(self, adv_name: str, adv_steps: int,
                         adv_energy: int, adv_time: int) -> GameState:
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
        # 4.6 — log_event старта приключения.
        from history import log_event
        log_event('adventure_start', name=adv_name, cost_steps=adv_steps,
                  cost_energy=adv_energy, duration_minutes=adv_time)

        print(f'Steps_used_today 🏃: {state.steps.used}')
        print(f'Energy used 🔋: {adv_energy}')
        if debug_mode:
            print(f'Energy Left: {state.energy}')
            print(f'Время_now: {datetime.now().timestamp()}')
            print(f'Время прохождения Приключения: {state.adventure.end_ts - datetime.now().timestamp()}')
        return state

    # Сохраняем legacy-имя для совместимости с возможными внешними вызовами.
    def start_adventure(self, adv_name: str, adv_steps: int,
                        adv_energy: int, adv_time: int) -> GameState:
        return self._enter_adventure(adv_name, adv_steps, adv_energy, adv_time)

    def get_adventure_requirement(self, adventure_key: str) -> str:
        base = self.adventure_data_table[adventure_key]
        final_time = speed_skill_equipment_and_level_bonus(base['time'], self._state)
        return (
            f'🏃: {steps_color(base["steps"])} шагов, '
            f'🔋: {energy_color(base["energy"])} энергии, '
            f'🕑: {time(final_time)}'
        )
