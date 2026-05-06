"""Bank — депозиты и кредиты (зонтичная задача 4.49).

Phase 0.1 (4.49.0.1): депозит — внести / снять / capitalize-on-change.
Кредиты придут в Phase 4 (4.49.2.1).

Архитектура процентов: **capitalize-on-change**. Перед любым событием,
меняющим тело депозита или ставку, вызывается `accrue_deposit(state)` —
он капитализирует накопленные за `(now - last_interest_ts)` проценты по
ТЕКУЩЕЙ ставке. Это даёт compound interest с капитализацией на событиях.

Триггеры accrue:
- `_deposit` / `_deposit_all` (top-up — копейки переносятся вместе с целым)
- `_withdraw` / `_withdraw_all`
- (Phase 2, 4.49.1.1) хук в `gym.skill_training_check_done` для
  `banking_interest_rate` — accrue ПЕРЕД инкрементом скилла, чтобы новая
  ставка применялась только к будущим периодам.

Точность: `state.bank.deposit_amount` — float. Копейки текут между
кошельком и депозитом без потерь (`state.money: float` после 4.49.0.1).
В UI Bank-меню показываем 2 знака; в остальных меню (status_bar и т.п.)
используем `:,.0f` (целое + разделители тысяч).
"""

import time
from math import floor

from colorama import Fore, Style

from state import GameState


# 365 дней × 24 часа × 3600 секунд. Для simple-формулы непрерывного начисления.
_SECONDS_PER_YEAR = 365 * 24 * 3600


# ----------------------------------------------------------------------------
# Pure helpers — тестируются напрямую без UI.
# ----------------------------------------------------------------------------

def current_deposit_rate_pct(state: GameState) -> float:
    """Текущая годовая ставка депозита в процентах. Default 0%, +1% за каждый
    уровень скилла `banking_interest_rate`."""
    return float(state.gym.banking_interest_rate)


def can_open_deposit(state: GameState) -> bool:
    """Открытие / пополнение депозита разрешено только при skill ≥ 1 (4.49.0.2)."""
    return state.gym.banking_interest_rate >= 1


def can_withdraw(state: GameState) -> bool:
    """Снятие разрешено при skill ≥ 1 AND deposit_amount > 0 (4.49.0.2).

    Если skill упал до 0 (legacy / future prestige) — снятие тоже блокируется,
    игрок должен снова прокачать навык. Это даёт ennobling консистентность UX:
    если 'Внести' закрыто, 'Снять' тоже закрыто."""
    return can_open_deposit(state) and state.bank.deposit_amount > 0


def accrue_deposit(state: GameState) -> None:
    """Капитализирует накопленные проценты по ТЕКУЩЕЙ ставке за период
    `now - deposit_last_interest_ts`. Идемпотентна — повторный вызов в тот же
    момент даёт ~0 (за миллисекунды между вызовами).

    No-op при пустом депозите (`amount <= 0`) или отсутствии timestamp
    (`last_interest_ts is None` — deposita никогда не было).
    """
    bank = state.bank
    if bank.deposit_amount <= 0 or bank.deposit_last_interest_ts is None:
        return
    now = time.time()
    elapsed_s = now - bank.deposit_last_interest_ts
    if elapsed_s <= 0:
        # Защита от часов, идущих назад / clock skew. Пропускаем accrue, но
        # обновляем timestamp до now чтобы дальше считать вперёд.
        bank.deposit_last_interest_ts = now
        return
    rate_per_second = current_deposit_rate_pct(state) / 100.0 / _SECONDS_PER_YEAR
    interest = bank.deposit_amount * rate_per_second * elapsed_s
    bank.deposit_amount += interest
    bank.deposit_last_interest_ts = now


def preview_deposit_amount(state: GameState) -> float:
    """Возвращает 'виртуальный' остаток депозита, как если бы accrue был вызван
    сейчас. **Не мутирует state** — для отображения в Bank меню.

    При пустом депозите или отсутствии timestamp возвращает текущий
    `deposit_amount` (0 или закапитализированную сумму).
    """
    bank = state.bank
    if bank.deposit_amount <= 0 or bank.deposit_last_interest_ts is None:
        return bank.deposit_amount
    elapsed_s = time.time() - bank.deposit_last_interest_ts
    if elapsed_s <= 0:
        return bank.deposit_amount
    rate_per_second = current_deposit_rate_pct(state) / 100.0 / _SECONDS_PER_YEAR
    return bank.deposit_amount + bank.deposit_amount * rate_per_second * elapsed_s


def _deposit(state: GameState, amount: int) -> bool:
    """Внести целую сумму на депозит. Сначала capitalize накопленные проценты
    по старой ставке (если депозит уже был), потом списываем с money.
    Возвращает True при успехе, False при отказе (skill<1 / overdraft /
    amount <= 0)."""
    if not can_open_deposit(state):
        return False
    if amount <= 0:
        return False
    if state.money < amount:
        return False
    accrue_deposit(state)
    state.money -= amount
    state.bank.deposit_amount += amount
    if state.bank.deposit_last_interest_ts is None:
        state.bank.deposit_last_interest_ts = time.time()
    return True


def _deposit_all(state: GameState) -> float:
    """Перенести ВЕСЬ кошелёк (включая копейки) на депозит. Возвращает
    перенесённую сумму (0.0 при skill<1 или пустом кошельке). Накапливает
    проценты по старому balance перед top-up.
    """
    if not can_open_deposit(state):
        return 0.0
    if state.money <= 0:
        return 0.0
    accrue_deposit(state)
    moved = state.money
    state.bank.deposit_amount += moved
    state.money = 0.0
    if state.bank.deposit_last_interest_ts is None:
        state.bank.deposit_last_interest_ts = time.time()
    return moved


def _withdraw(state: GameState, amount: int) -> bool:
    """Снять целое X с депозита. **Strict floor** — копейки на депозите
    остаются (auto-promote НЕ применяется: при `floor(deposit) == X` копейки
    всё равно остаются; для полного снятия — `_withdraw_all`).

    4.49.0.2: блокируется при skill<1 ИЛИ пустом депозите."""
    if not can_withdraw(state):
        return False
    if amount <= 0:
        return False
    accrue_deposit(state)
    if amount > floor(state.bank.deposit_amount):
        return False
    state.bank.deposit_amount -= amount
    state.money += amount
    return True


def _withdraw_all(state: GameState) -> float:
    """Снять ВСЁ (включая копейки) — `state.money += deposit_amount`,
    `deposit_amount = 0.0`. Возвращает выплаченную сумму.

    4.49.0.2: блокируется при skill<1 ИЛИ пустом депозите."""
    if not can_withdraw(state):
        return 0.0
    accrue_deposit(state)
    paid = state.bank.deposit_amount
    if paid <= 0:
        return 0.0
    state.money += paid
    state.bank.deposit_amount = 0.0
    state.bank.deposit_last_interest_ts = None
    return paid


# ----------------------------------------------------------------------------
# UI — CLI меню Bank.
# ----------------------------------------------------------------------------

def _format_money(amount: float) -> str:
    """2 знака после запятой + разделители тысяч. Используется только в Bank UI."""
    return f"{amount:,.2f}"


def _print_bank_header(state: GameState) -> None:
    """Шапка Bank меню: кошелёк, депозит, ставка, накопленные проценты."""
    rate_pct = current_deposit_rate_pct(state)
    preview = preview_deposit_amount(state)
    accrued = preview - state.bank.deposit_amount

    yellow = Fore.LIGHTYELLOW_EX
    green = Fore.GREEN
    reset = Style.RESET_ALL

    print('\n--- 🏛 Bank Location 🏛 ---\n')
    print(f'💰 Кошелёк:   {yellow}{_format_money(state.money)}{reset} $')
    print(f'🏦 Депозит:   {green}{_format_money(preview)}{reset} $')
    rate_label = f'{rate_pct:.0f}% годовых'
    if rate_pct == 0.0:
        rate_label += '  (прокачай навык в Спортзале)'
    print(f'📈 Ставка:    {rate_label}')
    if accrued > 0:
        print(f'✨ Накоплено с прошлой капитализации: +{_format_money(accrued)} $')
    if not can_open_deposit(state):
        print('🔒 Банк заблокирован — прокачай навык до 1 уровня в Спортзале.')


def _ask_amount(prompt: str) -> int:
    """Запрашивает целое положительное число у игрока. Возвращает 0 при
    невалиде (caller трактует как cancel/error)."""
    raw = input(f'\n{prompt}\n>>> ').strip()
    try:
        value = int(raw)
    except ValueError:
        print('\nВведите целое число.')
        return 0
    if value <= 0:
        print('\nСумма должна быть больше 0.')
        return 0
    return value


_LOCK_MSG_BANK = '\n🔒 Банк заблокирован. Прокачай навык "Банковская ставка" до 1 уровня в Спортзале.'


def _do_deposit(state: GameState) -> None:
    if not can_open_deposit(state):
        print(_LOCK_MSG_BANK)
        return
    amount = _ask_amount('Введите сумму для внесения:')
    if amount <= 0:
        return
    if not _deposit(state, amount):
        print(f'\nНедостаточно средств. У вас {_format_money(state.money)} $.')
        return
    print(f'\nВы положили {amount} $ на депозит.')


def _do_deposit_all(state: GameState) -> None:
    if not can_open_deposit(state):
        print(_LOCK_MSG_BANK)
        return
    if state.money <= 0:
        print('\nНа кошельке нет средств.')
        return
    moved = _deposit_all(state)
    print(f'\nВы положили {_format_money(moved)} $ (весь кошелёк) на депозит.')


def _do_withdraw(state: GameState) -> None:
    if not can_open_deposit(state):
        print(_LOCK_MSG_BANK)
        return
    if state.bank.deposit_amount <= 0:
        print('\nДепозит пуст — нечего снимать.')
        return
    amount = _ask_amount('Введите сумму для снятия:')
    if amount <= 0:
        return
    if not _withdraw(state, amount):
        available = floor(preview_deposit_amount(state))
        print(f'\nНа депозите только {available} $ доступно к снятию (целое число).')
        return
    print(f'\nВы сняли {amount} $ с депозита.')


def _do_withdraw_all(state: GameState) -> None:
    if not can_open_deposit(state):
        print(_LOCK_MSG_BANK)
        return
    if state.bank.deposit_amount <= 0:
        print('\nДепозит пуст — нечего снимать.')
        return
    paid = _withdraw_all(state)
    print(f'\nВы сняли {_format_money(paid)} $ (весь депозит включая копейки) на кошелёк.')


def bank_menu(state: GameState) -> None:
    """Главное меню Bank. Цикл retry — выходит только по '0'."""
    while True:
        _print_bank_header(state)
        deposit_lock = '🔒 ' if not can_open_deposit(state) else ''
        withdraw_lock = '🔒 ' if not can_withdraw(state) else ''
        print(f'\n{deposit_lock}1. Внести')
        print(f'{deposit_lock}2. Внести всё')
        print(f'{withdraw_lock}3. Снять')
        print(f'{withdraw_lock}4. Снять всё')
        print('0. Назад')
        choice = input('>>> ').strip()
        if choice == '0':
            return
        if choice == '1':
            _do_deposit(state)
        elif choice == '2':
            _do_deposit_all(state)
        elif choice == '3':
            _do_withdraw(state)
        elif choice == '4':
            _do_withdraw_all(state)
        else:
            print('\nНеверный выбор. Попробуйте ещё раз.')
