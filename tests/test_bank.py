"""Тесты bank.py — депозит логика (Phase 0.1 / 4.49.0.1).

Pure helpers тестируются напрямую, UI меню — через monkeypatch input + capsys.
`time.time()` мокается через monkeypatch для детерминированных проверок accrue.
"""

from io import StringIO

import pytest

import bank
from bank import (
    accrue_deposit,
    bank_menu,
    can_open_deposit,
    can_withdraw,
    current_deposit_rate_pct,
    preview_deposit_amount,
    _deposit,
    _deposit_all,
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
    assert 'прокачай навык' in out


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
    s = GameState.default_new_game()
    s.gym.banking_interest_rate = 1
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
# 4.49.1.1 — Capitalize-on-skill-up. Хук в gym.skill_training_check_done.
# Когда тренировка banking_interest_rate завершается, accrue_deposit вызывается
# ПЕРЕД инкрементом скилла — чтобы накопленные проценты пошли по СТАРОЙ ставке,
# а новая применялась только к будущим периодам.
# ---------------------------------------------------------------------------

def test_skill_up_hook_capitalizes_at_old_rate_first(monkeypatch):
    """End-to-end: открыли депозит при skill=0 → 30 дней без процентов
    (т.к. ставка 0%) → завершилась тренировка banking_interest_rate (skill 0→1)
    → ещё 30 дней → проценты идут только за второй период по 1%."""
    from datetime import datetime
    import gym as gym_module

    s = GameState.default_new_game()
    s.bank.deposit_amount = 1000.0
    s.bank.deposit_last_interest_ts = 1000.0
    # Активная тренировка banking_interest_rate, time_end в прошлом.
    s.training.active = True
    s.training.skill_name = 'banking_interest_rate'
    s.training.time_end = datetime.fromtimestamp(900.0)  # уже истекло

    # Mock time на момент завершения тренировки = +30 дней с открытия депозита.
    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0 + 86400 * 30)
    # Mock save_characteristic — не пишем в реальные файлы из теста.
    monkeypatch.setattr(gym_module, 'save_characteristic', lambda: None)

    gym_module.skill_training_check_done(s)

    # Проценты накопились по СТАРОЙ ставке (0% за 30 дней) → ничего не изменилось.
    assert s.bank.deposit_amount == 1000.0
    # Skill инкрементнут после accrue.
    assert s.gym.banking_interest_rate == 1
    # last_interest_ts переехал на момент финализации (= now).
    assert s.bank.deposit_last_interest_ts == 1000.0 + 86400 * 30

    # Теперь второй период — 30 дней при skill=1 (ставка 1%).
    monkeypatch.setattr(bank.time, 'time', lambda: 1000.0 + 86400 * 60)
    bank.accrue_deposit(s)
    expected_interest = 1000.0 * 0.01 * (86400 * 30 / (365 * 86400))
    assert s.bank.deposit_amount == pytest.approx(1000.0 + expected_interest)


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
