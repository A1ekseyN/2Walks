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
from math import ceil, floor

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
# Loan logic (4.49.2.1)
# ----------------------------------------------------------------------------

def current_loan_rate_pct(state: GameState) -> float:
    """Текущая годовая ставка кредита: max(0, 100 - loan_interest_reduction).
    Default 100% (грабительская), снижается на 1%/level скилла."""
    return max(0.0, 100.0 - float(state.gym.loan_interest_reduction))


def max_loan(state: GameState) -> int:
    """Максимальная сумма непогашенного долга = loan_capacity * 100. Default 0."""
    return state.gym.loan_capacity * 100


def can_take_loan(state: GameState) -> bool:
    """Можно взять кредит, если есть свободный лимит. При loan_capacity=0
    cap=0 → False всегда (gate)."""
    return max_loan(state) > 0 and state.bank.loan_amount < max_loan(state)


def can_repay_loan(state: GameState) -> bool:
    """Гасить можно при наличии долга. НЕ гейтится скиллом — игрок всегда может
    закрыть свой долг (даже если loan_capacity вдруг упал до 0)."""
    return state.bank.loan_amount > 0


def accrue_loan(state: GameState) -> None:
    """Капитализирует накопленные проценты по долгу. Симметрично accrue_deposit.
    Идемпотентна. No-op при пустом кредите или отсутствии ts."""
    bank = state.bank
    if bank.loan_amount <= 0 or bank.loan_last_interest_ts is None:
        return
    now = time.time()
    elapsed_s = now - bank.loan_last_interest_ts
    if elapsed_s <= 0:
        bank.loan_last_interest_ts = now
        return
    rate_per_second = current_loan_rate_pct(state) / 100.0 / _SECONDS_PER_YEAR
    interest = bank.loan_amount * rate_per_second * elapsed_s
    bank.loan_amount += interest
    bank.loan_last_interest_ts = now


def preview_loan_amount(state: GameState) -> float:
    """Виртуальный текущий долг (с накопленными %% на момент now). Без мутации."""
    bank = state.bank
    if bank.loan_amount <= 0 or bank.loan_last_interest_ts is None:
        return bank.loan_amount
    elapsed_s = time.time() - bank.loan_last_interest_ts
    if elapsed_s <= 0:
        return bank.loan_amount
    rate_per_second = current_loan_rate_pct(state) / 100.0 / _SECONDS_PER_YEAR
    return bank.loan_amount + bank.loan_amount * rate_per_second * elapsed_s


def _take_loan(state: GameState, amount: int) -> bool:
    """Взять кредит на целую сумму. Capitalize старый долг по старой ставке
    перед добавлением. Проверяет cap (`loan_amount + amount <= max_loan`)."""
    if amount <= 0:
        return False
    if not can_take_loan(state):
        return False
    accrue_loan(state)
    if state.bank.loan_amount + amount > max_loan(state):
        return False
    state.money += amount
    state.bank.loan_amount += amount
    if state.bank.loan_last_interest_ts is None:
        state.bank.loan_last_interest_ts = time.time()
    return True


def _repay_loan(state: GameState, amount: int) -> bool:
    """Погасить целое X с долга. Capitalize first.

    Auto-promote: если `amount == ceil(loan_amount)` — закрываем кредит
    полностью (списываем `loan_amount` точно, без переплаты копеек). Иначе
    strict integer subtraction (X с money, X с долга), копейки остаются.

    Reject conditions: amount <= 0 / нет долга / amount > ceil(loan) /
    state.money < amount."""
    if amount <= 0:
        return False
    if not can_repay_loan(state):
        return False
    accrue_loan(state)
    loan = state.bank.loan_amount
    if amount > ceil(loan):
        return False
    if state.money < amount:
        return False
    if amount == ceil(loan):
        # Auto-promote — списываем точную сумму долга (float), кредит закрывается.
        state.money -= loan
        state.bank.loan_amount = 0.0
        state.bank.loan_last_interest_ts = None
    else:
        state.money -= amount
        state.bank.loan_amount -= amount
    return True


def _repay_loan_all(state: GameState) -> float:
    """Погасить весь кредит точной суммой (float). Возвращает заплаченную сумму
    (= loan_amount before payment) или 0.0 если долг отсутствует / денег не
    хватает."""
    if not can_repay_loan(state):
        return 0.0
    accrue_loan(state)
    cost = state.bank.loan_amount
    if state.money < cost:
        return 0.0
    state.money -= cost
    state.bank.loan_amount = 0.0
    state.bank.loan_last_interest_ts = None
    return cost


# ----------------------------------------------------------------------------
# UI — CLI меню Bank.
# ----------------------------------------------------------------------------

def _format_money(amount: float) -> str:
    """2 знака после запятой + разделители тысяч. Используется только в Bank UI."""
    return f"{amount:,.2f}"


def _print_bank_header(state: GameState) -> None:
    """Шапка Bank меню: кошелёк, депозит, ставка, накопленные проценты,
    блок кредита (всегда виден — даже при `max_loan=0` отображаем `0 / 0`
    и подсказку про прокачку)."""
    deposit_rate_pct = current_deposit_rate_pct(state)
    deposit_preview = preview_deposit_amount(state)
    deposit_accrued = deposit_preview - state.bank.deposit_amount

    loan_rate_pct = current_loan_rate_pct(state)
    loan_preview = preview_loan_amount(state)
    loan_accrued = loan_preview - state.bank.loan_amount
    loan_cap = max_loan(state)

    yellow = Fore.LIGHTYELLOW_EX
    green = Fore.GREEN
    red = Fore.LIGHTRED_EX
    reset = Style.RESET_ALL

    print('\n--- 🏛 Bank Location 🏛 ---\n')
    print(f'💰 Кошелёк:   {yellow}{_format_money(state.money)}{reset} $')
    # Депозит-блок.
    print(f'🏦 Депозит:   {green}{_format_money(deposit_preview)}{reset} $')
    deposit_rate_label = f'{deposit_rate_pct:.0f}% годовых'
    if deposit_rate_pct == 0.0:
        deposit_rate_label += '  (прокачай "Банковская ставка" в Спортзале)'
    print(f'📈 Ставка деп.:  {deposit_rate_label}')
    if deposit_accrued > 0:
        print(f'✨ Накоплено по депозиту: +{_format_money(deposit_accrued)} $')
    if not can_open_deposit(state):
        print('🔒 Депозит заблокирован — прокачай "Банковская ставка" до 1 уровня.')
    # Кредит-блок (всегда виден).
    print()
    print(f'💳 Кредит:    {red}{_format_money(loan_preview)}{reset} / {_format_money(loan_cap)} $ (лимит)')
    print(f'📉 Ставка кред.: {loan_rate_pct:.0f}% годовых')
    if loan_accrued > 0:
        print(f'💢 Начислено по кредиту: +{_format_money(loan_accrued)} $')
    if loan_cap == 0:
        print('🔒 Кредит заблокирован — прокачай "Кредитный лимит" до 1 уровня в Спортзале.')


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


# ----- Loan handlers (4.49.2.1) -----

_LOCK_MSG_LOAN = '\n🔒 Кредит заблокирован. Прокачай навык "Кредитный лимит" в Спортзале.'


def _do_take_loan(state: GameState) -> None:
    if max_loan(state) == 0:
        print(_LOCK_MSG_LOAN)
        return
    free = max_loan(state) - int(state.bank.loan_amount)
    if free <= 0:
        print(f'\nЛимит кредита исчерпан. Текущий долг: {_format_money(state.bank.loan_amount)} $ из {max_loan(state)} $.')
        return
    amount = _ask_amount(f'Введите сумму кредита (доступно {free} $):')
    if amount <= 0:
        return
    if amount > free:
        print(f'\nПревышен свободный лимит. Доступно {free} $.')
        return
    rate = current_loan_rate_pct(state)
    confirm = input(f'\nВзять {amount} $ под {rate:.0f}% годовых? (y/n): \n>>> ').strip().lower()
    if confirm not in ('y', 'yes', 'д', 'да'):
        print('\nОтменено.')
        return
    if not _take_loan(state, amount):
        # Не должно случаться при пройденных проверках, но defensive.
        print('\nНе удалось оформить кредит.')
        return
    print(f'\nВы взяли {amount} $ в кредит. Текущий долг: {_format_money(state.bank.loan_amount)} $.')


def _do_repay_loan(state: GameState) -> None:
    if state.bank.loan_amount <= 0:
        print('\nКредит отсутствует — нечего погашать.')
        return
    accrue_loan(state)  # обновим долг ДО подсказки игроку, чтобы он видел актуальную сумму
    full = ceil(state.bank.loan_amount)
    amount = _ask_amount(f'Введите сумму погашения (текущий долг ≈ {full} $):')
    if amount <= 0:
        return
    if amount > full:
        print(f'\nСумма погашения больше долга. Введите ≤ {full} $.')
        return
    if state.money < amount:
        print(f'\nНедостаточно средств. Нужно {amount} $, у вас {_format_money(state.money)} $.')
        return
    closed_fully = (amount == full)  # auto-promote
    if not _repay_loan(state, amount):
        print('\nНе удалось погасить кредит.')
        return
    if closed_fully:
        print('\nКредит закрыт. Спасибо за пользование банком.')
    else:
        print(f'\nПогашено {amount} $. Остаток долга: {_format_money(state.bank.loan_amount)} $.')


def _do_repay_loan_all(state: GameState) -> None:
    if state.bank.loan_amount <= 0:
        print('\nКредит отсутствует — нечего погашать.')
        return
    accrue_loan(state)
    cost = state.bank.loan_amount
    if state.money < cost:
        print(f'\nНедостаточно средств для полного погашения. Нужно {_format_money(cost)} $, у вас {_format_money(state.money)} $.')
        return
    paid = _repay_loan_all(state)
    if paid <= 0:
        print('\nНе удалось погасить кредит.')
        return
    print(f'\nПогашено {_format_money(paid)} $. Кредит закрыт. Спасибо за пользование банком.')


def bank_menu(state: GameState) -> None:
    """Главное меню Bank. Цикл retry — выходит только по '0'."""
    while True:
        _print_bank_header(state)
        deposit_lock = '🔒 ' if not can_open_deposit(state) else ''
        withdraw_lock = '🔒 ' if not can_withdraw(state) else ''
        take_loan_lock = '🔒 ' if not can_take_loan(state) else ''
        repay_loan_lock = '🔒 ' if not can_repay_loan(state) else ''
        print('\n═══ Депозит ═══')
        print(f'{deposit_lock}1. Внести')
        print(f'{deposit_lock}2. Внести всё')
        print(f'{withdraw_lock}3. Снять')
        print(f'{withdraw_lock}4. Снять всё')
        print('═══ Кредит ═══')
        print(f'{take_loan_lock}5. Взять кредит')
        print(f'{repay_loan_lock}6. Погасить')
        print(f'{repay_loan_lock}7. Погасить полностью')
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
        elif choice == '5':
            _do_take_loan(state)
        elif choice == '6':
            _do_repay_loan(state)
        elif choice == '7':
            _do_repay_loan_all(state)
        else:
            print('\nНеверный выбор. Попробуйте ещё раз.')
