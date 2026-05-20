"""Тесты bank.py — депозит логика (Phase 0.1 / 4.49.0.1).

Pure helpers тестируются напрямую, UI меню — через monkeypatch input + capsys.
`time.time()` мокается через monkeypatch для детерминированных проверок accrue.
"""

from io import StringIO

import pytest

import bank
from bank import (
    accrue_deposit,
    accrue_loan,
    bank_menu,
    can_open_deposit,
    can_repay_loan,
    can_take_loan,
    can_withdraw,
    current_deposit_rate_pct,
    current_loan_rate_pct,
    max_loan,
    preview_deposit_amount,
    preview_loan_amount,
    _deposit,
    _deposit_all,
    _repay_loan,
    _repay_loan_all,
    _take_loan,
    _withdraw,
    _withdraw_all,
)
from state import GameState, BankState, GymSkills


# ----- current_deposit_rate_pct -----

def test_rate_default_zero():
    s = GameState.default_new_game()
    assert current_deposit_rate_pct(s) == 0.0


def test_rate_with_skill_5():
    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 5
    assert current_deposit_rate_pct(s) == 5.0


# ----- accrue_deposit -----

def test_accrue_noop_when_amount_zero():
    s = GameState(bank=BankState(deposit_amount=0.0, deposit_last_interest_ts=1700000000.0))
    accrue_deposit(s)
    assert s.bank.deposit_amount == 0.0
    # last_interest_ts не обновляется при пустом депозите.
    assert s.bank.deposit_last_interest_ts == 1700000000.0


def test_accrue_noop_when_no_timestamp():
    s = GameState(bank=BankState(deposit_amount=1000.0, deposit_last_interest_ts=None))
    accrue_deposit(s)
    assert s.bank.deposit_amount == 1000.0
    assert s.bank.deposit_last_interest_ts is None


def test_accrue_at_zero_rate_no_interest(monkeypatch):
    """skill=0 → ставка 0% → проценты не начисляются за любое время."""
    s = GameState.default_new_game()
    s.bank.deposit_amount = 1000.0
    s.bank.deposit_last_interest_ts = 1000.0
    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0 + 86400 * 30)  # +30 дней
    accrue_deposit(s)
    assert s.bank.deposit_amount == 1000.0  # без процентов
    assert s.bank.deposit_last_interest_ts == 1000.0 + 86400 * 30


def test_accrue_one_day_at_ten_percent(monkeypatch):
    """1000 $ × 10%/год × 1 день = 1000 * 0.1 / 365 ≈ 0.274 $."""
    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 10
    s.bank.deposit_amount = 1000.0
    s.bank.deposit_last_interest_ts = 1000.0
    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0 + 86400)  # +1 день
    accrue_deposit(s)
    expected = 1000.0 + 1000.0 * 0.10 * (86400 / (365 * 86400))
    assert s.bank.deposit_amount == pytest.approx(expected)
    assert s.bank.deposit_last_interest_ts == 1000.0 + 86400


def test_accrue_idempotent(monkeypatch):
    """Повторный вызов в тот же момент не меняет результат значимо."""
    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 5
    s.bank.deposit_amount = 1000.0
    s.bank.deposit_last_interest_ts = 1000.0
    # Сначала продвигаем время на 1 час.
    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0 + 3600)
    accrue_deposit(s)
    after_first = s.bank.deposit_amount
    # Второй вызов в тот же момент — elapsed=0, ничего не добавляет.
    accrue_deposit(s)
    assert s.bank.deposit_amount == after_first


def test_accrue_handles_clock_skew(monkeypatch):
    """Если now < last_interest_ts (часы пошли назад) — accrue не отрицательный,
    timestamp обновляется до now чтобы дальше считать вперёд."""
    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 5
    s.bank.deposit_amount = 1000.0
    s.bank.deposit_last_interest_ts = 2000.0  # будущее относительно "now"
    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0)  # now < last
    accrue_deposit(s)
    assert s.bank.deposit_amount == 1000.0  # без изменений
    assert s.bank.deposit_last_interest_ts == 1000.0  # обновился до now


# ----- preview_deposit_amount -----

def test_preview_no_mutation(monkeypatch):
    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 10
    s.bank.deposit_amount = 1000.0
    s.bank.deposit_last_interest_ts = 1000.0
    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0 + 86400)
    p = preview_deposit_amount(s)
    assert p > 1000.0  # есть начисление
    # State не изменён — это ключевое свойство preview.
    assert s.bank.deposit_amount == 1000.0
    assert s.bank.deposit_last_interest_ts == 1000.0


def test_preview_zero_when_empty():
    s = GameState.default_new_game()
    assert preview_deposit_amount(s) == 0.0


# ----- _deposit -----

def test_deposit_normal():
    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 1  # gate (4.49.0.2)
    s.money = 500.0
    assert _deposit(s, 100) is True
    assert s.money == 400.0
    assert s.bank.deposit_amount == 100.0
    assert s.bank.deposit_last_interest_ts is not None


def test_deposit_overdraft_rejected():
    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 1
    s.money = 50.0
    assert _deposit(s, 100) is False
    assert s.money == 50.0
    assert s.bank.deposit_amount == 0.0
    # Timestamp не устанавливается при отказе.
    assert s.bank.deposit_last_interest_ts is None


def test_deposit_zero_or_negative_rejected():
    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 1
    s.money = 100.0
    assert _deposit(s, 0) is False
    assert _deposit(s, -10) is False
    assert s.money == 100.0
    assert s.bank.deposit_amount == 0.0


def test_deposit_topup_capitalizes_first(monkeypatch):
    """Top-up: capitalize старый процент перед прибавлением новой суммы."""
    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 10
    s.money = 500.0
    s.bank.deposit_amount = 1000.0
    s.bank.deposit_last_interest_ts = 1000.0
    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0 + 86400)  # +1 день
    _deposit(s, 200)
    # 1000 * 1.1 / 365 ≈ 0.274 капитализировались + 200 топ-ап
    assert s.bank.deposit_amount > 1200.0  # ~1200.274
    assert s.bank.deposit_amount < 1201.0
    assert s.money == 300.0
    assert s.bank.deposit_last_interest_ts == 1000.0 + 86400


# ----- _deposit_all -----

def test_deposit_all_includes_cents():
    """Перенести весь кошелёк (включая копейки) на депозит."""
    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 1
    s.money = 100.42
    moved = _deposit_all(s)
    assert moved == pytest.approx(100.42)
    assert s.money == 0.0
    assert s.bank.deposit_amount == pytest.approx(100.42)


def test_deposit_all_empty_wallet():
    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 1
    moved = _deposit_all(s)
    assert moved == 0.0
    assert s.bank.deposit_amount == 0.0


# ----- _withdraw -----

def test_withdraw_strict_floor_leaves_cents(monkeypatch):
    """deposit=100.42, withdraw 100 → НЕ auto-promote, копейки остаются."""
    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 1
    s.bank.deposit_amount = 100.42
    s.bank.deposit_last_interest_ts = 1000.0
    s.money = 0.0
    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0)  # zero elapsed
    assert _withdraw(s, 100) is True
    assert s.money == 100.0
    assert s.bank.deposit_amount == pytest.approx(0.42)


def test_withdraw_partial(monkeypatch):
    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 1
    s.bank.deposit_amount = 200.5
    s.bank.deposit_last_interest_ts = 1000.0
    s.money = 0.0
    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0)
    _withdraw(s, 50)
    assert s.money == 50.0
    assert s.bank.deposit_amount == pytest.approx(150.5)


def test_withdraw_more_than_floor_rejected(monkeypatch):
    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 1
    s.bank.deposit_amount = 100.42
    s.bank.deposit_last_interest_ts = 1000.0
    s.money = 0.0
    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0)
    assert _withdraw(s, 101) is False
    assert s.money == 0.0
    assert s.bank.deposit_amount == pytest.approx(100.42)


def test_withdraw_zero_rejected():
    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 1
    s.bank.deposit_amount = 100.0
    s.bank.deposit_last_interest_ts = 1000.0
    assert _withdraw(s, 0) is False


# ----- _withdraw_all -----

def test_withdraw_all_includes_cents(monkeypatch):
    """Снять всё — копейки тоже переходят в кошелёк. Mock time чтобы accrue
    не добавил процентов за многолетний gap (skill=1 → 1% годовых)."""
    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 1
    s.bank.deposit_amount = 100.42
    s.bank.deposit_last_interest_ts = 1000.0
    s.money = 50.0
    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0)  # elapsed = 0
    paid = _withdraw_all(s)
    assert paid == pytest.approx(100.42)
    assert s.money == pytest.approx(150.42)
    assert s.bank.deposit_amount == 0.0
    # При полном выводе timestamp сбрасывается — следующий депозит начнёт
    # отсчёт с нуля.
    assert s.bank.deposit_last_interest_ts is None


def test_withdraw_all_empty():
    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 1
    paid = _withdraw_all(s)
    assert paid == 0.0
    assert s.money == 0.0


# ----- bank_menu UI -----

def _menu_inputs(monkeypatch, inputs: list):
    """Утилита: заменить input() на iterator над фиксированным списком."""
    it = iter(inputs)
    monkeypatch.setattr('builtins.input', lambda *args, **kwargs: next(it))


def test_bank_menu_exit_immediately(monkeypatch, capsys):
    s = GameState.default_new_game()
    _menu_inputs(monkeypatch, ['0'])
    bank_menu(s)
    out = capsys.readouterr().out
    assert 'Bank Location' in out


def test_bank_menu_deposit_flow(monkeypatch, capsys):
    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 1  # gate (4.49.0.2)
    s.money = 500.0
    _menu_inputs(monkeypatch, ['1', '100', '0'])  # выбор Внести → 100 → выход
    bank_menu(s)
    assert s.money == 400.0
    assert s.bank.deposit_amount == 100.0


def test_bank_menu_invalid_choice_retries(monkeypatch, capsys):
    s = GameState.default_new_game()
    _menu_inputs(monkeypatch, ['xyz', '99', '0'])
    bank_menu(s)
    out = capsys.readouterr().out
    assert 'Неверный выбор' in out


def test_bank_menu_zero_rate_shows_hint(capsys):
    """При ставке 0% в шапке меню — подсказка про прокачку навыка."""
    s = GameState.default_new_game()
    bank._print_bank_header(s)
    out = capsys.readouterr().out
    assert 'прокачай' in out
    assert 'Банковская ставка' in out


def test_bank_menu_nonzero_rate_no_hint(capsys):
    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 5
    bank._print_bank_header(s)
    out = capsys.readouterr().out
    assert 'прокачай навык' not in out
    assert '5% годовых' in out


def test_bank_menu_deposit_invalid_amount(monkeypatch, capsys):
    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 1
    s.money = 500.0
    _menu_inputs(monkeypatch, ['1', 'abc', '0'])  # Внести → не число → выход
    bank_menu(s)
    out = capsys.readouterr().out
    assert 'целое число' in out
    assert s.money == 500.0
    assert s.bank.deposit_amount == 0.0


def test_bank_menu_deposit_overdraft_message(monkeypatch, capsys):
    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 1
    s.money = 50.0
    _menu_inputs(monkeypatch, ['1', '100', '0'])
    bank_menu(s)
    out = capsys.readouterr().out
    assert 'Недостаточно' in out
    assert s.money == 50.0


def test_bank_menu_withdraw_all_flow(monkeypatch, capsys):
    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 1  # gate
    s.bank.deposit_amount = 250.75
    s.bank.deposit_last_interest_ts = 1000.0
    s.money = 0.0
    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0)  # zero elapsed → no accrue
    _menu_inputs(monkeypatch, ['4', '0'])  # Снять всё → выход
    bank_menu(s)
    assert s.money == pytest.approx(250.75)
    assert s.bank.deposit_amount == 0.0


def test_bank_menu_deposit_all_flow(monkeypatch, capsys):
    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 1
    s.money = 123.45
    _menu_inputs(monkeypatch, ['2', '0'])  # Внести всё → выход
    bank_menu(s)
    assert s.money == 0.0
    assert s.bank.deposit_amount == pytest.approx(123.45)


# ---------------------------------------------------------------------------
# 4.49.0.2 — Gate: открытие/пополнение депозита требует skill ≥ 1.
# Снятие НЕ блокируется (защита от потери legacy депозита).
# ---------------------------------------------------------------------------

def test_can_open_deposit_default_zero():
    """Default new game — skill=0 → депозит заблокирован."""
    s = GameState.default_new_game()
    assert can_open_deposit(s) is False


def test_can_open_deposit_at_skill_1():
    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 1
    assert can_open_deposit(s) is True


def test_deposit_blocked_at_skill_zero():
    """skill=0 → _deposit отказывает даже при наличии средств."""
    s = GameState.default_new_game()
    s.money = 1000.0
    assert _deposit(s, 100) is False
    assert s.money == 1000.0
    assert s.bank.deposit_amount == 0.0


def test_deposit_all_blocked_at_skill_zero():
    """skill=0 → _deposit_all отказывает (возвращает 0.0, кошелёк не трогается)."""
    s = GameState.default_new_game()
    s.money = 500.0
    moved = _deposit_all(s)
    assert moved == 0.0
    assert s.money == 500.0
    assert s.bank.deposit_amount == 0.0


def test_withdraw_blocked_at_skill_zero():
    """Снятие тоже блокируется при skill<1 (даже если депозит > 0).
    Edge case: legacy / future prestige — игрок должен снова прокачать навык."""
    s = GameState.default_new_game()
    s.bank.deposit_amount = 100.0
    s.bank.deposit_last_interest_ts = 1000.0
    assert _withdraw(s, 50) is False
    assert s.money == 0.0
    assert s.bank.deposit_amount == 100.0


def test_withdraw_all_blocked_at_skill_zero():
    s = GameState.default_new_game()
    s.bank.deposit_amount = 100.42
    s.bank.deposit_last_interest_ts = 1000.0
    paid = _withdraw_all(s)
    assert paid == 0.0
    assert s.money == 0.0
    # Депозит остался нетронутым.
    assert s.bank.deposit_amount == pytest.approx(100.42)


def test_withdraw_blocked_when_deposit_zero():
    """Даже при skill ≥ 1 — снять с пустого депозита нельзя."""
    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 1
    s.bank.deposit_amount = 0.0
    assert can_withdraw(s) is False
    assert _withdraw(s, 1) is False
    paid = _withdraw_all(s)
    assert paid == 0.0


def test_can_withdraw_requires_both_conditions():
    """can_withdraw = skill ≥ 1 AND deposit > 0."""
    s = GameState.default_new_game()
    # skill=0, deposit=0 — оба фолз
    assert can_withdraw(s) is False
    # skill=1, deposit=0 — false (нечего снимать)
    s.gym.banking_interest_rate = 1
    assert can_withdraw(s) is False
    # skill=1, deposit>0 — true
    s.bank.deposit_amount = 50.0
    assert can_withdraw(s) is True
    # skill=0, deposit>0 — false (gate)
    s.gym.banking_interest_rate = 0
    assert can_withdraw(s) is False


def test_bank_menu_shows_lock_at_skill_zero(monkeypatch, capsys):
    s = GameState.default_new_game()
    _menu_inputs(monkeypatch, ['0'])
    bank_menu(s)
    out = capsys.readouterr().out
    assert '🔒' in out
    assert 'заблокирован' in out  # substring; ловит и "Банк заблокирован"


def test_bank_menu_no_lock_at_skill_one(monkeypatch, capsys):
    """При банк-skill=1 + кредит-skill=1 — никаких локов."""
    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 1
    s.gym.loan_capacity = 1  # чтобы кредитный блок тоже был unlocked
    _menu_inputs(monkeypatch, ['0'])
    bank_menu(s)
    out = capsys.readouterr().out
    assert 'заблокирован' not in out


def test_bank_menu_deposit_attempt_at_skill_zero_shows_message(monkeypatch, capsys):
    """При skill=0 выбор '1. Внести' выдаёт понятное сообщение, не вызывая
    prompt на сумму."""
    s = GameState.default_new_game()
    s.money = 1000.0
    _menu_inputs(monkeypatch, ['1', '0'])  # попытка Внести → выход
    bank_menu(s)
    out = capsys.readouterr().out
    assert 'Банк заблокирован' in out
    # Деньги остались на кошельке, депозит пуст.
    assert s.money == 1000.0
    assert s.bank.deposit_amount == 0.0


# ---------------------------------------------------------------------------
# 4.49.1.2 (0.2.4z) — Retro-bonus exploit ОТКРЫТ намеренно. Хук accrue
# ПЕРЕД инкрементом скилла удалён. Новая ставка применяется ретроактивно
# к накопленному времени с last_interest_ts — стимул прокачивать скиллы
# банка. Симметрично earnings_boost (4.23).
# ---------------------------------------------------------------------------

def test_skill_up_no_accrue_retro_bonus_applies(monkeypatch):
    """End-to-end: открыли депозит при skill=0 (rate 0%) → 30 дней →
    завершилась тренировка banking_interest_rate (skill 0→1) → НИКАКОГО
    accrue не произошло (timestamp не сдвинулся) → ручной accrue по
    НОВОЙ ставке считает проценты за ВЕСЬ 30-дневный период (retro-bonus)."""
    from datetime import datetime
    import gym as gym_module

    s = GameState.default_new_game()
    s.bank.deposit_amount = 1000.0
    s.bank.deposit_last_interest_ts = 1000.0
    s.training.active = True
    s.training.skill_name = 'banking_interest_rate'
    s.training.time_end = datetime.fromtimestamp(900.0)  # уже истекло

    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0 + 86400 * 30)
    monkeypatch.setattr(gym_module, 'save_characteristic', lambda: None)

    gym_module.skill_training_check_done(s)

    # Skill инкрементнут.
    assert s.gym.banking_interest_rate == 1
    # accrue НЕ вызывался — депозит не изменился, timestamp не сдвинулся.
    assert s.bank.deposit_amount == 1000.0
    assert s.bank.deposit_last_interest_ts == 1000.0

    # Следующий accrue (top-up / withdraw / другая mutation) применит НОВУЮ
    # ставку 1% за все 30 дней с момента открытия депозита = retro-bonus.
    bank.accrue_deposit(s)
    expected_interest = 1000.0 * 0.01 * (86400 * 30 / (365 * 86400))
    assert s.bank.deposit_amount == pytest.approx(1000.0 + expected_interest)
    assert s.bank.deposit_last_interest_ts == 1000.0 + 86400 * 30


def test_skill_up_hook_does_not_fire_for_other_skills(monkeypatch):
    """Хук accrue работает только для banking_interest_rate. Прокачка stamina
    не вызывает accrue (а если бы вызвала — депозит бы немного вырос)."""
    from datetime import datetime
    import gym as gym_module

    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 10  # высокая ставка, чтобы accrue был заметен
    s.bank.deposit_amount = 1000.0
    s.bank.deposit_last_interest_ts = 1000.0
    s.training.active = True
    s.training.skill_name = 'stamina'
    s.training.time_end = datetime.fromtimestamp(900.0)

    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0 + 86400 * 30)
    monkeypatch.setattr(gym_module, 'save_characteristic', lambda: None)

    gym_module.skill_training_check_done(s)

    # accrue НЕ был вызван — депозит не изменился, last_interest_ts не сдвинулся.
    assert s.bank.deposit_amount == 1000.0
    assert s.bank.deposit_last_interest_ts == 1000.0
    assert s.gym.stamina == 1  # stamina таки прокачался


def test_banking_skill_in_descriptions_dict():
    """4.49.1.0: navyk должен быть зарегистрирован в _SKILL_DESCRIPTIONS
    (для CLI описания) и в _SKILL_OPTIONS (для меню Gym)."""
    import gym as gym_module
    assert 'banking_interest_rate' in gym_module._SKILL_DESCRIPTIONS
    title, _, body = gym_module._SKILL_DESCRIPTIONS['banking_interest_rate']
    assert 'Банковская ставка' in title
    assert '%' in body  # описание упоминает проценты


def test_banking_skill_in_web_display_dict():
    """4.49.1.0: navyk должен быть в _GYM_SKILL_DISPLAY для web UI."""
    from web.main import _GYM_SKILL_DISPLAY
    assert 'banking_interest_rate' in _GYM_SKILL_DISPLAY
    meta = _GYM_SKILL_DISPLAY['banking_interest_rate']
    assert meta['available'] is True
    assert meta['icon'] == '🏦'
    assert meta['field'] == 'banking_interest_rate'


# ---------------------------------------------------------------------------
# 4.49.2.0 — Loan-related skills: loan_capacity + loan_interest_reduction.
# Только регистрация в Gym + state. Хук capitalize-on-skill-up для
# loan_interest_reduction добавится в 4.49.2.1 одновременно с accrue_loan.
# ---------------------------------------------------------------------------

def test_loan_capacity_default_zero():
    s = GameState.default_new_game()
    assert s.gym.loan_capacity == 0


def test_loan_interest_reduction_default_zero():
    s = GameState.default_new_game()
    assert s.gym.loan_interest_reduction == 0


def test_loan_skills_round_trip():
    """Round-trip обоих новых полей через to_dict/from_dict."""
    s1 = GameState.default_new_game()
    s1.gym.loan_capacity = 5
    s1.gym.loan_interest_reduction = 3
    d = s1.to_dict()
    assert d['loan_capacity'] == 5
    assert d['loan_interest_reduction'] == 3
    s2 = GameState.from_dict(d)
    assert s2.gym.loan_capacity == 5
    assert s2.gym.loan_interest_reduction == 3


def test_loan_skills_in_descriptions_dict():
    """Оба навыка зарегистрированы в _SKILL_DESCRIPTIONS (CLI описание)."""
    import gym as gym_module
    assert 'loan_capacity' in gym_module._SKILL_DESCRIPTIONS
    assert 'loan_interest_reduction' in gym_module._SKILL_DESCRIPTIONS
    title_lc, _, body_lc = gym_module._SKILL_DESCRIPTIONS['loan_capacity']
    assert 'Кредитный лимит' in title_lc
    assert '+100' in body_lc
    title_lir, _, body_lir = gym_module._SKILL_DESCRIPTIONS['loan_interest_reduction']
    assert 'Снижение ставки' in title_lir
    assert '1%' in body_lir or '−1%' in body_lir or '-1%' in body_lir


def test_loan_skills_in_gym_menu_options():
    """Новые навыки доступны в gym_menu — проверяем pre-rendering при открытом меню."""
    import gym as gym_module
    s = GameState.default_new_game()
    # Эмулируем то, что делает gym_menu — собираем skill_options dict.
    # gym_menu закрытая функция, проверяем напрямую через её внутреннюю логику.
    # Простейший способ: запустить меню с input='0' и проверить наличие пунктов.
    from io import StringIO
    import sys
    inputs = iter(['0'])
    original_input = __builtins__['input'] if isinstance(__builtins__, dict) else __builtins__.input
    captured = StringIO()
    original_stdout = sys.stdout
    sys.stdout = captured
    try:
        # Подмена input на iterator (без monkeypatch — для совместимости).
        if isinstance(__builtins__, dict):
            __builtins__['input'] = lambda *args, **kwargs: next(inputs)
        else:
            __builtins__.input = lambda *args, **kwargs: next(inputs)
        gym_module.gym_menu(s)
    finally:
        sys.stdout = original_stdout
        if isinstance(__builtins__, dict):
            __builtins__['input'] = original_input
        else:
            __builtins__.input = original_input
    out = captured.getvalue()
    assert 'Кредитный лимит' in out
    assert 'Снижение ставки' in out


def test_loan_skills_in_web_display_dict():
    """4.49.2.0: оба навыка в _GYM_SKILL_DISPLAY с available=True."""
    from web.main import _GYM_SKILL_DISPLAY
    assert 'loan_capacity' in _GYM_SKILL_DISPLAY
    lc = _GYM_SKILL_DISPLAY['loan_capacity']
    assert lc['available'] is True
    assert lc['icon'] == '💳'
    assert lc['field'] == 'loan_capacity'

    assert 'loan_interest_reduction' in _GYM_SKILL_DISPLAY
    lir = _GYM_SKILL_DISPLAY['loan_interest_reduction']
    assert lir['available'] is True
    assert lir['icon'] == '📉'
    assert lir['field'] == 'loan_interest_reduction'


# ---------------------------------------------------------------------------
# 4.49.2.1 — Loan mechanics: take / repay / accrue / max_loan / hooks.
# ---------------------------------------------------------------------------

def test_current_loan_rate_default_100():
    s = GameState.default_new_game()
    assert current_loan_rate_pct(s) == 100.0


def test_current_loan_rate_with_skill():
    s = GameState.default_new_game()
    s.gym.loan_interest_reduction = 5
    assert current_loan_rate_pct(s) == 95.0


def test_current_loan_rate_clamped_at_zero():
    """Скилл выше 100 уровней (теоретически) → ставка 0%, не отрицательная."""
    s = GameState.default_new_game()
    s.gym.loan_interest_reduction = 200
    assert current_loan_rate_pct(s) == 0.0


def test_max_loan_default_zero():
    s = GameState.default_new_game()
    assert max_loan(s) == 0


def test_max_loan_with_skill():
    s = GameState.default_new_game()
    s.gym.loan_capacity = 5
    assert max_loan(s) == 500


def test_can_take_loan_default_false():
    """Default — loan_capacity=0 → max_loan=0 → False."""
    s = GameState.default_new_game()
    assert can_take_loan(s) is False


def test_can_take_loan_with_capacity_and_no_debt():
    s = GameState.default_new_game()
    s.gym.loan_capacity = 5
    assert can_take_loan(s) is True


def test_can_take_loan_at_full_cap():
    """Лимит исчерпан → False даже при skill > 0."""
    s = GameState.default_new_game()
    s.gym.loan_capacity = 5
    s.bank.loan_amount = 500.0
    assert can_take_loan(s) is False


def test_can_repay_loan_requires_debt():
    s = GameState.default_new_game()
    assert can_repay_loan(s) is False
    s.bank.loan_amount = 50.0
    assert can_repay_loan(s) is True


def test_can_repay_loan_does_not_require_skill():
    """Гасить можно даже при loan_capacity=0 — игрок не должен застрять с долгом."""
    s = GameState.default_new_game()
    s.bank.loan_amount = 50.0
    # loan_capacity = 0 (default)
    assert can_repay_loan(s) is True


# ----- accrue_loan -----

def test_accrue_loan_noop_zero_amount():
    s = GameState.default_new_game()
    accrue_loan(s)
    assert s.bank.loan_amount == 0.0


def test_accrue_loan_noop_no_timestamp():
    s = GameState.default_new_game()
    s.bank.loan_amount = 100.0  # без ts
    accrue_loan(s)
    assert s.bank.loan_amount == 100.0


def test_accrue_loan_at_100_percent_one_day(monkeypatch):
    """Дефолтные 100% годовых × 1 день на долге 100 → +0.27 $."""
    s = GameState.default_new_game()
    s.bank.loan_amount = 100.0
    s.bank.loan_last_interest_ts = 1000.0
    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0 + 86400)
    accrue_loan(s)
    expected = 100.0 + 100.0 * 1.0 * (86400 / (365 * 86400))
    assert s.bank.loan_amount == pytest.approx(expected)


def test_accrue_loan_idempotent(monkeypatch):
    s = GameState.default_new_game()
    s.bank.loan_amount = 100.0
    s.bank.loan_last_interest_ts = 1000.0
    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0 + 3600)
    accrue_loan(s)
    after_first = s.bank.loan_amount
    accrue_loan(s)
    assert s.bank.loan_amount == after_first


def test_preview_loan_no_mutation(monkeypatch):
    s = GameState.default_new_game()
    s.bank.loan_amount = 100.0
    s.bank.loan_last_interest_ts = 1000.0
    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0 + 86400)
    p = preview_loan_amount(s)
    assert p > 100.0
    assert s.bank.loan_amount == 100.0  # не мутирован


# ----- _take_loan -----

def test_take_loan_blocked_at_skill_zero():
    s = GameState.default_new_game()
    assert _take_loan(s, 50) is False
    assert s.money == 0.0
    assert s.bank.loan_amount == 0.0


def test_take_loan_normal():
    s = GameState.default_new_game()
    s.gym.loan_capacity = 5  # cap = 500
    assert _take_loan(s, 100) is True
    assert s.money == 100.0
    assert s.bank.loan_amount == 100.0
    assert s.bank.loan_last_interest_ts is not None


def test_take_loan_respects_cap(monkeypatch):
    """Mock time чтобы accrue не накручивал между двумя _take_loan вызовами."""
    s = GameState.default_new_game()
    s.gym.loan_capacity = 5  # cap = 500
    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0)
    _take_loan(s, 400)
    assert _take_loan(s, 100) is True
    assert s.bank.loan_amount == 500.0
    assert _take_loan(s, 1) is False


def test_take_loan_zero_or_negative_rejected():
    s = GameState.default_new_game()
    s.gym.loan_capacity = 5
    assert _take_loan(s, 0) is False
    assert _take_loan(s, -10) is False


# ----- _repay_loan -----

def test_repay_loan_partial(monkeypatch):
    s = GameState.default_new_game()
    s.gym.loan_capacity = 5
    s.bank.loan_amount = 100.0
    s.bank.loan_last_interest_ts = 1000.0
    s.money = 200.0
    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0)  # zero accrue
    assert _repay_loan(s, 30) is True
    assert s.money == 170.0
    assert s.bank.loan_amount == 70.0


def test_repay_loan_auto_promote_at_ceil(monkeypatch):
    """Долг 100.42 → ввод 101 (== ceil) → точное списание 100.42, кредит закрыт."""
    s = GameState.default_new_game()
    s.gym.loan_capacity = 5
    s.bank.loan_amount = 100.42
    s.bank.loan_last_interest_ts = 1000.0
    s.money = 200.0
    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0)
    assert _repay_loan(s, 101) is True
    # state.money уменьшился ТОЧНО на 100.42 (не на 101 — нет переплаты копеек).
    assert s.money == pytest.approx(99.58)
    assert s.bank.loan_amount == 0.0
    assert s.bank.loan_last_interest_ts is None


def test_repay_loan_over_ceil_rejected(monkeypatch):
    s = GameState.default_new_game()
    s.gym.loan_capacity = 5
    s.bank.loan_amount = 100.42
    s.bank.loan_last_interest_ts = 1000.0
    s.money = 200.0
    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0)
    assert _repay_loan(s, 102) is False
    # Состояние не изменилось.
    assert s.money == 200.0
    assert s.bank.loan_amount == pytest.approx(100.42)


def test_repay_loan_insufficient_money(monkeypatch):
    s = GameState.default_new_game()
    s.gym.loan_capacity = 5
    s.bank.loan_amount = 100.0
    s.bank.loan_last_interest_ts = 1000.0
    s.money = 30.0
    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0)
    assert _repay_loan(s, 50) is False
    assert s.money == 30.0
    assert s.bank.loan_amount == 100.0


def test_repay_loan_no_debt():
    s = GameState.default_new_game()
    s.money = 100.0
    assert _repay_loan(s, 10) is False


def test_repay_loan_zero_or_negative():
    s = GameState.default_new_game()
    s.bank.loan_amount = 100.0
    s.money = 100.0
    assert _repay_loan(s, 0) is False
    assert _repay_loan(s, -1) is False


# ----- _repay_loan_all -----

def test_repay_loan_all_pays_exact_float(monkeypatch):
    """Long_amount=100.42, money=200 → платим 100.42 точно (float)."""
    s = GameState.default_new_game()
    s.gym.loan_capacity = 5
    s.bank.loan_amount = 100.42
    s.bank.loan_last_interest_ts = 1000.0
    s.money = 200.0
    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0)
    paid = _repay_loan_all(s)
    assert paid == pytest.approx(100.42)
    assert s.money == pytest.approx(99.58)
    assert s.bank.loan_amount == 0.0
    assert s.bank.loan_last_interest_ts is None


def test_repay_loan_all_insufficient_money(monkeypatch):
    s = GameState.default_new_game()
    s.bank.loan_amount = 100.42
    s.bank.loan_last_interest_ts = 1000.0
    s.money = 50.0
    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0)
    paid = _repay_loan_all(s)
    assert paid == 0.0
    # Состояние не изменилось.
    assert s.money == 50.0
    assert s.bank.loan_amount == pytest.approx(100.42)


def test_repay_loan_all_no_debt():
    s = GameState.default_new_game()
    paid = _repay_loan_all(s)
    assert paid == 0.0


# ----- Loan retro-discount (4.49.2.3 / 0.2.4z): см. 4.49.1.2 для deposit -----

def test_skill_up_no_accrue_for_loan_retro_discount(monkeypatch):
    """End-to-end: взяли кредит при skill=0 (rate 100%) → 30 дней →
    завершилась тренировка loan_interest_reduction (skill 0→1, rate 99%) →
    НИКАКОГО accrue не произошло → следующий accrue считает по НОВОЙ ставке
    99% за весь период = retro-DISCOUNT (player отдал меньше)."""
    from datetime import datetime
    import gym as gym_module

    s = GameState.default_new_game()
    s.gym.loan_capacity = 5  # cap=500, чтобы взять
    s.bank.loan_amount = 100.0
    s.bank.loan_last_interest_ts = 1000.0
    s.training.active = True
    s.training.skill_name = 'loan_interest_reduction'
    s.training.time_end = datetime.fromtimestamp(900.0)

    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0 + 86400 * 30)
    monkeypatch.setattr(gym_module, 'save_characteristic', lambda: None)

    gym_module.skill_training_check_done(s)

    assert s.gym.loan_interest_reduction == 1
    # accrue НЕ вызывался на skill-up — долг и timestamp не трогались.
    assert s.bank.loan_amount == 100.0
    assert s.bank.loan_last_interest_ts == 1000.0

    # Следующий accrue применит НОВУЮ ставку 99% за весь 30-дневный период
    # (вместо 100% если бы accrue сработал на skill-up).
    bank.accrue_loan(s)
    expected = 100.0 + 100.0 * 0.99 * (86400 * 30 / (365 * 86400))
    assert s.bank.loan_amount == pytest.approx(expected, rel=1e-4)


def test_skill_up_hook_does_not_affect_loan_for_other_skills(monkeypatch):
    """Прокачка stamina не вызывает accrue_loan."""
    from datetime import datetime
    import gym as gym_module

    s = GameState.default_new_game()
    s.gym.loan_interest_reduction = 0
    s.bank.loan_amount = 100.0
    s.bank.loan_last_interest_ts = 1000.0
    s.training.active = True
    s.training.skill_name = 'stamina'
    s.training.time_end = datetime.fromtimestamp(900.0)

    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0 + 86400 * 30)
    monkeypatch.setattr(gym_module, 'save_characteristic', lambda: None)

    gym_module.skill_training_check_done(s)

    # accrue_loan НЕ был вызван — долг и timestamp не трогались.
    assert s.bank.loan_amount == 100.0
    assert s.bank.loan_last_interest_ts == 1000.0


# ----- bank_menu UI с кредитом -----

def test_bank_menu_shows_credit_section_when_capacity_zero(monkeypatch, capsys):
    """При loan_capacity=0 в шапке видна строка о блокировке кредита."""
    s = GameState.default_new_game()
    _menu_inputs(monkeypatch, ['0'])
    bank_menu(s)
    out = capsys.readouterr().out
    assert 'Кредит' in out
    # ANSI codes между числами; проверяем суффикс отдельно.
    assert '0.00 $ (лимит)' in out
    assert 'Кредит заблокирован' in out


def test_bank_menu_credit_unlocked_when_capacity_set(monkeypatch, capsys):
    s = GameState.default_new_game()
    s.gym.loan_capacity = 5
    _menu_inputs(monkeypatch, ['0'])
    bank_menu(s)
    out = capsys.readouterr().out
    assert 'Кредит заблокирован' not in out
    assert '500.00 $ (лимит)' in out


def test_bank_menu_take_loan_with_confirmation(monkeypatch, capsys):
    s = GameState.default_new_game()
    s.gym.loan_capacity = 5
    # 5. Взять → 200 $ → y → 0
    _menu_inputs(monkeypatch, ['5', '200', 'y', '0'])
    bank_menu(s)
    assert s.money == 200.0
    assert s.bank.loan_amount == 200.0


def test_bank_menu_take_loan_cancel_confirmation(monkeypatch, capsys):
    """Отказ от кредита через 'n' — state не меняется."""
    s = GameState.default_new_game()
    s.gym.loan_capacity = 5
    _menu_inputs(monkeypatch, ['5', '200', 'n', '0'])
    bank_menu(s)
    assert s.money == 0.0
    assert s.bank.loan_amount == 0.0


def test_bank_menu_repay_loan_full_message(monkeypatch, capsys):
    """Полное погашение через '7' — выводится сообщение 'Кредит закрыт'."""
    s = GameState.default_new_game()
    s.gym.loan_capacity = 5
    s.bank.loan_amount = 100.0
    s.bank.loan_last_interest_ts = 1000.0
    s.money = 200.0
    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0)
    _menu_inputs(monkeypatch, ['7', '0'])
    bank_menu(s)
    out = capsys.readouterr().out
    assert 'Кредит закрыт' in out
    assert s.bank.loan_amount == 0.0


# ---------------------------------------------------------------------------
# 4.27 — Inspiration ('Обучение'): регистрация в Gym + web display.
# Бизнес-логика начисления тестируется в test_actions.py / test_level.py.
# ---------------------------------------------------------------------------

def test_inspiration_skill_in_descriptions_dict():
    import gym as gym_module
    assert 'inspiration' in gym_module._SKILL_DESCRIPTIONS
    title, _, body = gym_module._SKILL_DESCRIPTIONS['inspiration']
    assert title == 'Обучение'
    assert '+1%' in body or '+ 1%' in body or 'опыт' in body.lower()


def test_inspiration_skill_in_web_display_dict():
    from web.main import _GYM_SKILL_DISPLAY
    assert 'inspiration' in _GYM_SKILL_DISPLAY
    meta = _GYM_SKILL_DISPLAY['inspiration']
    assert meta['available'] is True
    assert meta['icon'] == '📚'
    assert meta['field'] == 'inspiration'
    assert meta['title'] == 'Обучение'


# ---------------------------------------------------------------------------
# 4.20 — money_saving skill registration in CLI + web. Бизнес-логика
# покрыта в test_bonus.py (apply_money_saving) и интеграция — ниже.
# ---------------------------------------------------------------------------

def test_money_saving_skill_in_descriptions_dict():
    import gym as gym_module
    assert 'money_saving' in gym_module._SKILL_DESCRIPTIONS
    title, _, body = gym_module._SKILL_DESCRIPTIONS['money_saving']
    assert title == 'Экономия денег'
    assert '1%' in body or 'денежных' in body.lower()


def test_money_saving_skill_in_web_display_dict():
    from web.main import _GYM_SKILL_DISPLAY
    assert 'money_saving' in _GYM_SKILL_DISPLAY
    meta = _GYM_SKILL_DISPLAY['money_saving']
    assert meta['available'] is True
    assert meta['icon'] == '🏷'
    assert meta['field'] == 'money_saving'
    assert meta['title'] == 'Экономия денег'


# ---------------------------------------------------------------------------
# 4.23 — earnings_boost skill registration.
# Бизнес-логика — в test_bonus.py (apply_earnings_boost).
# ---------------------------------------------------------------------------

def test_earnings_boost_skill_in_descriptions_dict():
    import gym as gym_module
    assert 'earnings_boost' in gym_module._SKILL_DESCRIPTIONS
    title, _, body = gym_module._SKILL_DESCRIPTIONS['earnings_boost']
    assert title == 'Бонус к зарплате'
    assert '1%' in body or '+1' in body or 'зарплат' in body.lower()


def test_earnings_boost_skill_in_web_display_dict():
    from web.main import _GYM_SKILL_DISPLAY
    assert 'earnings_boost' in _GYM_SKILL_DISPLAY
    meta = _GYM_SKILL_DISPLAY['earnings_boost']
    assert meta['available'] is True
    assert meta['icon'] == '💵'
    assert meta['field'] == 'earnings_boost'
    assert meta['title'] == 'Бонус к зарплате'


def test_earnings_boost_default_zero():
    s = GameState.default_new_game()
    assert s.gym.earnings_boost == 0


def test_earnings_boost_round_trip():
    s1 = GameState.default_new_game()
    s1.gym.earnings_boost = 25
    d = s1.to_dict()
    assert d['earnings_boost'] == 25
    s2 = GameState.from_dict(d)
    assert s2.gym.earnings_boost == 25


def test_try_spend_accepts_float_money():
    """try_spend(money=float) — после 4.20 сигнатура принимает float
    (raised from int). Корректно сравнивается со state.money: float."""
    from actions import try_spend
    state = GameState.default_new_game()
    state.money = 100.0
    assert try_spend(state, money=49.50) is True
    assert state.money == pytest.approx(50.50)


def test_buy_item_with_money_saving_discount():
    """Интеграционный: shop._buy_item принимает float-cost, вычитает дробную сумму."""
    from shop import _buy_item
    from bonus import apply_money_saving
    state = GameState.default_new_game()
    state.gym.money_saving = 7
    state.money = 100.0
    cost = apply_money_saving(50, state)  # 50 * 0.93 = 46.50
    item = {'item_name': ['test']}
    assert _buy_item(state, item, cost) is True
    assert state.money == pytest.approx(53.50)
    assert state.inventory == [item]
