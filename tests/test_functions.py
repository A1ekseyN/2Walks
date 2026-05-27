"""Тесты functions.py после миграции на GameState (Phase 4 задачи 1.1).

UI-функции (status_bar, char_info) тестируются через capsys на корректность
основных секций вывода. Логика дня, шагов, энергии — через прямые ассерты.
"""

from datetime import datetime, timedelta

import pytest

from state import GameState
import functions
from functions import (
    timestamp_now,
    energy_time_charge,
    save_game_date_last_enter,
    steps_today_set,
    today_steps_to_yesterday_steps,
    total_bonus_steps,
    bonus_percentage,
    format_steps,
    location_change_map,
    energy_timestamp,
    char_info,
    status_bar,
    steps as steps_fn,
)


# ----- format_steps (pure utility) -----

def test_format_steps_below_10k():
    assert format_steps(0) == "0"
    assert format_steps(999) == "999"
    assert format_steps(9999) == "9999"


def test_format_steps_thousands():
    assert format_steps(10_000) == "10k"
    assert format_steps(123_456) == "123k"
    assert format_steps(999_999) == "999k"


def test_format_steps_millions():
    assert format_steps(1_000_000) == "1.0kk"
    assert format_steps(1_500_000) == "1.5kk"
    assert format_steps(2_750_000) == "2.8kk"


# ----- timestamp_now (pure) -----

def test_timestamp_now_returns_float():
    ts = timestamp_now()
    assert isinstance(ts, float)
    assert ts > 0


# ----- bonus_percentage / total_bonus_steps -----

def test_bonus_percentage_zero_steps_today():
    state = GameState.default_new_game()
    state.steps.today = 0
    assert bonus_percentage(state) == 0


def test_bonus_percentage_with_bonus():
    state = GameState.default_new_game()
    state.steps.today = 10000
    state.gym.stamina = 5  # stamina bonus def: round(10000/100)*5 = 500
    # base 10000, bonus 500 → 5%
    assert bonus_percentage(state) == 5.0


def test_total_bonus_steps_sums_all_sources():
    state = GameState.default_new_game()
    state.steps.today = 10000
    state.gym.stamina = 3              # stamina bonus: 100*3 = 300
    state.steps.daily_bonus = 2        # daily: 100*2 = 200
    state.char_level.skill_stamina = 1  # level: 100*1 = 100
    # total = 300 + 0 (equipment) + 200 + 100 = 600
    assert total_bonus_steps(state) == 600


# ----- today_steps_to_yesterday_steps -----

def test_today_steps_to_yesterday_at_10k_increments_bonus():
    state = GameState.default_new_game()
    state.steps.today = 10500
    state.steps.daily_bonus = 3

    yesterday, bonus = today_steps_to_yesterday_steps(state)

    assert yesterday == 10500
    assert bonus == 4
    assert state.steps.yesterday == 10500
    assert state.steps.daily_bonus == 4


def test_today_steps_to_yesterday_below_10k_resets_bonus():
    state = GameState.default_new_game()
    state.steps.today = 8000
    state.steps.daily_bonus = 5

    yesterday, bonus = today_steps_to_yesterday_steps(state)

    assert yesterday == 8000
    assert bonus == 0


def test_today_steps_to_yesterday_accumulates_total_walked():
    """4.62.1.1.1 — реально пройденные накапливаются в total_walked на rollover."""
    state = GameState.default_new_game()
    state.steps.total_walked = 100_000
    state.steps.today = 8500

    today_steps_to_yesterday_steps(state)
    assert state.steps.total_walked == 108_500  # += завершившийся день

    # Следующий день.
    state.steps.today = 12000
    today_steps_to_yesterday_steps(state)
    assert state.steps.total_walked == 120_500


def test_today_steps_to_yesterday_increments_days_played():
    """4.62.1.9 — день с активностью (≥1 шаг) → days_played += 1; пустой день нет."""
    state = GameState.default_new_game()
    state.days_played = 5

    state.steps.today = 8000  # активный день
    today_steps_to_yesterday_steps(state)
    assert state.days_played == 6

    state.steps.today = 0     # день без ввода шагов
    today_steps_to_yesterday_steps(state)
    assert state.days_played == 6  # не инкрементился

    state.steps.today = 1     # хоть 1 шаг → активный
    today_steps_to_yesterday_steps(state)
    assert state.days_played == 7


def test_today_steps_to_yesterday_tracks_streak_record():
    """4.62.1.9 — daily_streak_record = max(стрик); не откатывается при обрыве."""
    state = GameState.default_new_game()
    # 3 дня подряд 10k+ → стрик растёт, рекорд = 3.
    for _ in range(3):
        state.steps.today = 12000
        today_steps_to_yesterday_steps(state)
    assert state.steps.daily_bonus == 3
    assert state.steps.daily_streak_record == 3

    # День <10k → текущий стрик сброшен, но рекорд держится.
    state.steps.today = 5000
    today_steps_to_yesterday_steps(state)
    assert state.steps.daily_bonus == 0
    assert state.steps.daily_streak_record == 3  # не откатился


# ----- steps_today_set -----

def test_steps_today_set_higher_replaces():
    state = GameState.default_new_game()
    state.steps.today = 1000
    steps_today_set(2000, state)
    assert state.steps.today == 2000


def test_steps_today_set_lower_keeps_old():
    state = GameState.default_new_game()
    state.steps.today = 5000
    steps_today_set(3000, state)
    assert state.steps.today == 5000


def test_steps_today_set_negative_no_op():
    state = GameState.default_new_game()
    state.steps.today = 1000
    steps_today_set(-5, state)
    assert state.steps.today == 1000


def test_steps_today_set_equal_keeps_value():
    state = GameState.default_new_game()
    state.steps.today = 1500
    steps_today_set(1500, state)
    assert state.steps.today == 1500


# ----- energy_time_charge -----

def test_energy_time_charge_at_max_clamps_and_syncs_stamp():
    state = GameState.default_new_game()
    state.energy = 60
    state.energy_max = 50
    state.energy_time_stamp = 0

    energy_time_charge(state)

    assert state.energy == 50
    # Стамп синкнут к now (ненулевой и близкий к timestamp_now()).
    assert state.energy_time_stamp > 0


def test_energy_time_charge_below_max_recent_no_change():
    """Если elapsed < interval, энергия не меняется."""
    state = GameState.default_new_game()
    state.energy = 30
    state.energy_max = 50
    state.energy_time_stamp = timestamp_now() - 5  # 5 сек < 60 сек интервала

    energy_time_charge(state)

    assert state.energy == 30


def test_energy_time_charge_below_max_adds_points():
    """elapsed > N * interval → +N энергии."""
    state = GameState.default_new_game()
    state.energy = 30
    state.energy_max = 50
    state.energy_time_stamp = timestamp_now() - 185  # 3 интервала по 60 сек + 5 сек остатка

    energy_time_charge(state)

    assert state.energy == 33


def test_no_free_energy_after_spend_from_max():
    """Conformance-тест на баг "бесплатная энергия после максимума" (bugs.txt,
    задача 2.2.3, исправлено в 0.2.0l).

    Сценарий: игрок 1000 секунд назад был на full (стамп = now-1000), потом
    через actions.try_spend потратил 10 энергии (стамп должен синкнуться к now),
    потом сразу же energy_time_charge → не должно начислиться 16 единиц
    "накопленных" из прошлого."""
    from actions import try_spend
    state = GameState.default_new_game()
    state.energy = 50
    state.energy_max = 50
    state.energy_time_stamp = timestamp_now() - 1000  # давно был на full

    # Трата через try_spend (как делают gym/work/adventure).
    assert try_spend(state, energy=10) is True
    assert state.energy == 40  # списали

    # Сразу после — тик регенерации.
    energy_time_charge(state)

    # Не должно быть начисления "накопленной" энергии.
    # При корректном поведении 2.2.3 — стамп = now → elapsed=0 → energy=40.
    # При багованном поведении (без 2.2.3) — energy ≈ 50 (накатило 10).
    assert state.energy == 40


def test_energy_time_charge_clamps_to_max():
    """Не превышает energy_max."""
    state = GameState.default_new_game()
    state.energy = 48
    state.energy_max = 50
    state.energy_time_stamp = timestamp_now() - 600  # 10 интервалов = +10, но clamp до 50

    energy_time_charge(state)

    assert state.energy == 50


def test_energy_time_charge_uses_energy_regen_not_speed():
    """0.2.4i (task 4.21) — energy_time_charge зависит от energy_regen_skill,
    но НЕ от speed_skill. Прокачка Speed не должна влиять на regen.

    До 0.2.4i эти две механики были связаны (общий speed_skill_equipment_and_level_bonus)."""
    state = GameState.default_new_game()
    state.gym.speed_skill = 50          # speed=50, regen=0
    state.char_level.skill_speed = 30   # тоже не должен влиять
    state.energy = 0
    state.energy_max = 10
    state.energy_time_stamp = timestamp_now() - 60  # ровно один base interval

    energy_time_charge(state)

    # interval = 60 сек (regen=0), elapsed=60 → +1 эн.
    # Если бы speed_skill влиял (как до 0.2.4i): interval = 60 - 60*0.80 = 12 сек,
    # elapsed=60 → 60//12 = 5 единиц энергии → state.energy=5.
    assert state.energy == 1, "speed_skill не должен ускорять regen"


def test_energy_time_charge_accelerates_with_energy_regen_skill():
    """0.2.4i — прокачка energy_regen_skill ускоряет regen."""
    state = GameState.default_new_game()
    state.gym.energy_regen_skill = 50  # interval = 60 - 30 = 30 сек
    state.energy = 0
    state.energy_max = 10
    state.energy_time_stamp = timestamp_now() - 90  # 90 // 30 = 3 единицы

    energy_time_charge(state)

    assert state.energy == 3


# ----- save_game_date_last_enter (same-day path) -----

def test_save_game_date_last_enter_same_day_recalcs_can_use():
    state = GameState.default_new_game()
    state.date_last_enter = str(datetime.now().date())
    state.steps.today = 5000
    state.steps.used = 500
    state.gym.stamina = 0
    state.steps.daily_bonus = 0
    state.char_level.skill_stamina = 0

    result = save_game_date_last_enter(state)

    # 5000 - 500 + 0 + 0 + 0 + 0 = 4500
    assert result == 4500
    assert state.steps.can_use == 4500
    # Today/used не сбрасываются — тот же день.
    assert state.steps.today == 5000
    assert state.steps.used == 500


def test_save_game_date_last_enter_new_day_resets(tmp_path, monkeypatch):
    """Новый день — сбрасывает today/used, переносит в yesterday."""
    monkeypatch.chdir(tmp_path)
    state = GameState.default_new_game()
    state.date_last_enter = '2020-01-01'  # точно не сегодня
    state.steps.today = 12000
    state.steps.used = 2000
    state.steps.daily_bonus = 1

    save_game_date_last_enter(state)

    assert state.steps.today == 0
    assert state.steps.used == 0
    assert state.steps.yesterday == 12000
    assert state.steps.daily_bonus == 2  # +1 за >=10k шагов
    assert state.date_last_enter == str(datetime.now().date())


def test_daily_bonus_increments_when_log_has_10k_yesterday(tmp_path, monkeypatch):
    """2.4: state.steps.today был частичный (5000), но в steps_log за вчера
    лежит 12000 — max-merge должен поднять today до 12000 перед rollover,
    чтобы yesterday>=10k и daily_bonus +=1."""
    from google_sheets_db import StepsLogRepo
    monkeypatch.chdir(tmp_path)

    state = GameState.default_new_game()
    state.date_last_enter = '2026-05-01'  # вчера
    state.steps.today = 5000  # частичный (web ввод не сохранён в game_state)
    state.steps.daily_bonus = 3

    # Mock: steps_log за вчера содержит 12000 (web ввод).
    monkeypatch.setattr(
        StepsLogRepo, "for_day",
        lambda self, d, user_id=None: [
            {"ts": 1.0, "user_id": "alex", "steps": 12000, "source": "web"}
        ] if d == '2026-05-01' else []
    )

    save_game_date_last_enter(state)

    # После rollover: yesterday = 12000 (из лога), daily_bonus +=1.
    assert state.steps.yesterday == 12000
    assert state.steps.daily_bonus == 4


def test_daily_bonus_resets_when_yesterday_no_log(tmp_path, monkeypatch):
    """2.4: лог пустой за вчера, today=5000 → yesterday=5000 → daily_bonus=0."""
    from google_sheets_db import StepsLogRepo
    monkeypatch.chdir(tmp_path)

    state = GameState.default_new_game()
    state.date_last_enter = '2026-05-01'
    state.steps.today = 5000
    state.steps.daily_bonus = 7

    monkeypatch.setattr(StepsLogRepo, "for_day",
                        lambda self, d, user_id=None: [])

    save_game_date_last_enter(state)

    assert state.steps.yesterday == 5000
    assert state.steps.daily_bonus == 0


def test_daily_bonus_resets_when_log_yesterday_under_10k(tmp_path, monkeypatch):
    """2.4: в логе за вчера лежит 8000 (<10k), today=5000 → max=8000 → yesterday<10k → bonus=0."""
    from google_sheets_db import StepsLogRepo
    monkeypatch.chdir(tmp_path)

    state = GameState.default_new_game()
    state.date_last_enter = '2026-05-01'
    state.steps.today = 5000
    state.steps.daily_bonus = 5

    monkeypatch.setattr(
        StepsLogRepo, "for_day",
        lambda self, d, user_id=None: [
            {"ts": 1.0, "user_id": "alex", "steps": 8000, "source": "web"}
        ]
    )

    save_game_date_last_enter(state)

    assert state.steps.yesterday == 8000
    assert state.steps.daily_bonus == 0


def test_daily_bonus_max_merge_silent_fail_on_sheets_error(tmp_path, monkeypatch):
    """2.4: ошибка в Sheets во время max-merge не должна ломать rollover."""
    from google_sheets_db import StepsLogRepo
    monkeypatch.chdir(tmp_path)

    state = GameState.default_new_game()
    state.date_last_enter = '2026-05-01'
    state.steps.today = 12000  # уже на >10k
    state.steps.daily_bonus = 2

    def failing(self, d, user_id=None):
        raise RuntimeError("Network down")
    monkeypatch.setattr(StepsLogRepo, "for_day", failing)

    save_game_date_last_enter(state)

    # state.steps.today=12000 → yesterday=12000 → bonus +=1.
    # Sheets-ошибка не привела к падению, просто пропустили max-merge.
    assert state.steps.yesterday == 12000
    assert state.steps.daily_bonus == 3


def test_save_game_date_last_enter_does_not_create_save_txt(tmp_path, monkeypatch):
    """save.txt больше не пишется (задача 2.1, версия 0.2.0k) — единственный
    источник правды для day rollover теперь state.date_last_enter."""
    monkeypatch.chdir(tmp_path)
    state = GameState.default_new_game()
    state.date_last_enter = '2020-01-01'

    save_game_date_last_enter(state)

    save_file = tmp_path / 'save.txt'
    assert not save_file.exists(), "save.txt должен не создаваться после 2.1"


# ----- steps() helper -----

def test_steps_returns_can_use():
    """steps() запускает recalc и возвращает steps.can_use."""
    state = GameState.default_new_game()
    state.date_last_enter = str(datetime.now().date())
    state.steps.today = 3000
    state.steps.used = 500

    assert steps_fn(state) == 2500


# ----- location_change_map (no-op) -----

def test_location_change_map_no_op():
    state = GameState.default_new_game()
    state.energy = 30
    state.steps.used = 100
    location_change_map(state)
    # Сейчас стоимость нулевая — состояние не меняется.
    assert state.energy == 30
    assert state.steps.used == 100


# ----- energy_timestamp -----

def test_energy_timestamp_sets_to_now(capsys):
    state = GameState.default_new_game()
    state.energy_time_stamp = 0

    result = energy_timestamp(state)

    assert result > 0
    assert state.energy_time_stamp == result
    captured = capsys.readouterr()
    assert 'Energy TimeStamp Update' in captured.out


# ----- char_info (UI smoke via capsys) -----

def test_char_info_prints_all_sections(capsys):
    state = GameState.default_new_game()
    state.steps.today = 5000
    state.energy = 30
    state.gym.stamina = 7
    state.gym.energy_max_skill = 4
    state.gym.luck_skill = 2

    char_info(state)

    out = capsys.readouterr().out
    assert 'Характеристики персонажа' in out
    assert 'Бонусы за навыки' in out
    assert 'Бонусы экипировки' in out
    assert 'Прокачка навыков от уровня персонажа' in out
    # Конкретные значения отображены
    assert '5,000' in out  # steps_today форматирован запятыми
    assert '+ 7 %' in out  # stamina


# ----- status_bar (UI smoke via capsys) -----

def test_status_bar_smoke_no_active_sessions(tmp_path, monkeypatch, capsys):
    """status_bar() с дефолтным state — печатает шаги/энергию/деньги/локацию без падений."""
    monkeypatch.chdir(tmp_path)
    state = GameState.default_new_game()
    state.date_last_enter = str(datetime.now().date())
    state.steps.today = 8000
    state.energy = 25
    state.money = 100
    state.loc = 'home'

    status_bar(state)

    out = capsys.readouterr().out
    assert 'Steps' in out
    assert 'Energy' in out
    assert 'Money' in out
    assert 'Home' in out


def test_status_bar_with_training_active(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    state = GameState.default_new_game()
    state.date_last_enter = str(datetime.now().date())
    state.training.active = True
    state.training.skill_name = 'stamina'
    state.training.time_end = datetime.now() + timedelta(minutes=5)

    status_bar(state)

    out = capsys.readouterr().out
    assert 'Улучшаем навык' in out
    assert 'Stamina' in out


def test_status_bar_with_work_active(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    state = GameState.default_new_game()
    state.date_last_enter = str(datetime.now().date())
    state.work.active = True
    state.work.work_type = 'factory'
    state.work.salary = 5
    state.work.hours = 3
    state.work.end = datetime.now() + timedelta(hours=1)

    status_bar(state)

    out = capsys.readouterr().out
    assert 'Место работы' in out
    assert 'Factory' in out


# ===========================================================================
# 4.61 — status_bar warning для broken / low-quality equipped items
# ===========================================================================


def _eq_item(char='stamina', bonus=5, quality=80):
    return {'characteristic': [char], 'bonus': [bonus], 'quality': [quality],
            'item_name': ['x'], 'item_type': ['helmet'], 'grade': ['a-grade'], 'price': [50]}


def test_status_bar_no_warning_when_all_items_full_quality(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    state = GameState.default_new_game()
    state.date_last_enter = str(datetime.now().date())
    state.equipment.head = _eq_item(quality=80)
    status_bar(state)
    out = capsys.readouterr().out
    assert 'Сломано' not in out
    assert 'Требует ремонта' not in out


def test_status_bar_warning_when_broken_item_equipped(tmp_path, monkeypatch, capsys):
    """quality=0 → красное «🔨 Сломано» warning."""
    monkeypatch.chdir(tmp_path)
    state = GameState.default_new_game()
    state.date_last_enter = str(datetime.now().date())
    state.equipment.head = _eq_item(quality=0)
    status_bar(state)
    out = capsys.readouterr().out
    assert '🔨' in out
    assert 'Сломано: 1' in out


def test_status_bar_warning_when_low_quality_item_equipped(tmp_path, monkeypatch, capsys):
    """0 < quality < 20 → жёлтое «Требует ремонта» warning (но не broken)."""
    monkeypatch.chdir(tmp_path)
    state = GameState.default_new_game()
    state.date_last_enter = str(datetime.now().date())
    state.equipment.head = _eq_item(quality=15)
    status_bar(state)
    out = capsys.readouterr().out
    assert 'Требует ремонта: 1' in out
    assert 'Сломано' not in out  # quality=15 это не broken


def test_status_bar_warns_for_both_broken_and_low_separately(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    state = GameState.default_new_game()
    state.date_last_enter = str(datetime.now().date())
    state.equipment.head = _eq_item(quality=0)     # broken
    state.equipment.neck = _eq_item(quality=10)    # low
    state.equipment.torso = _eq_item(quality=12)   # low
    status_bar(state)
    out = capsys.readouterr().out
    assert 'Сломано: 1' in out
    assert 'Требует ремонта: 2' in out
