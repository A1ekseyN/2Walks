"""Forge — Кузница (4.59). Ремонт + Crafting + (deferred) Gems system.

4.59.0 (0.2.5X) — infra + skeleton меню с 5 пунктами:
- Пункты 1-2 будут реализованы в 4.59.1 (Repair) и 4.59.2 (Crafting).
- Пункты 3-5 — отложенная подзадача 4.59.3 (Gems system, deferred low-priority).

Все handler'ы 1-5 пока — stub'ы которые выводят «в разработке». Меню
работает, не падает, готово для последовательной реализации подзадач.
"""

from functions_02 import format_money
from state import GameState


def _print_forge_header(state: GameState) -> None:
    """Шапка меню Кузницы — текущие ресурсы."""
    print('\n--- 🔨 Кузница 🔨 ---')
    print(f'Steps 🏃: {state.steps.can_use}, '
          f'Energy 🔋: {state.energy}, '
          f'Money 💰: {format_money(state.money)} $.')


def _do_repair(state: GameState) -> None:
    """4.59.1 — Repair: восстановление quality предметов. TODO."""
    print('\n⚙ Отремонтировать предмет — функционал в разработке (4.59.1).')


def _do_craft(state: GameState) -> None:
    """4.59.2 — Crafting: upgrade grade (2 → 1). TODO."""
    print('\n⚙ Улучшить Grade предмета — функционал в разработке (4.59.2).')


def _do_socket_create(state: GameState) -> None:
    """4.59.3 — Gem sockets (deferred, low-priority)."""
    print('\n⚙ Сделать дырку в предмете для камня — в разработке (4.59.3, отложено).')


def _do_socket_insert(state: GameState) -> None:
    """4.59.3 — Insert gem in socket (deferred, low-priority)."""
    print('\n⚙ Вставить камень в предмет — в разработке (4.59.3, отложено).')


def _do_gem_combine(state: GameState) -> None:
    """4.59.3 — Combine 3 gems → 1 higher grade (deferred, low-priority)."""
    print('\n⚙ Объединить камни — в разработке (4.59.3, отложено).')


def forge_menu(state: GameState) -> None:
    """Главное меню Кузницы. Цикл retry — выходит только по '0'.

    Pattern идентичен `bank_menu` (4.49). UI loop с шапкой ресурсов
    и dispatch на handler-функции. Невалидный выбор → continue цикла.
    """
    while True:
        _print_forge_header(state)
        print('\nВ кузнице можно:')
        print('\t1. Отремонтировать предмет')
        print('\t2. Улучшить Grade предмета')
        print('\t3. Сделать дырку в предмете для камня (В разработке)')
        print('\t4. Вставить камень в предмет (В разработке)')
        print('\t5. Объединить камни (В разработке)')
        print('\t0. Назад')
        choice = input('>>> ').strip()
        if choice == '0':
            return
        if choice == '1':
            _do_repair(state)
        elif choice == '2':
            _do_craft(state)
        elif choice == '3':
            _do_socket_create(state)
        elif choice == '4':
            _do_socket_insert(state)
        elif choice == '5':
            _do_gem_combine(state)
        else:
            print('\nНеверный выбор. Попробуйте ещё раз.')
