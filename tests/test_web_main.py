"""Тесты FastAPI скелета и dashboard (задачи 4.48.0 + 4.48.1 + 4.54.0).

Используется ``fastapi.testclient.TestClient`` — он автоматически вызывает
lifespan на входе/выходе из контекста. Перед TestClient мы инициализируем
``game.state`` через ``init_game_state(GameState.default_new_game())``;
повторный вызов в lifespan — no-op (idempotent), Sheets не дёргается.

Auto-fixture ``patch_sheets_load`` мокает ``GameStateRepo.load`` для всех
тестов в этом файле — чтобы `GET /` (который через 4.54.0 делает reload)
не ходил в реальный Sheets.
"""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from characteristics import game, init_game_state
from state import GameState
from web import sync as web_sync
from web.main import VERSION, app


@pytest.fixture(autouse=True)
def patch_sheets_load(monkeypatch):
    """Мокает GameStateRepo.load — возвращает текущий state.to_dict() (no-op
    reload). Тесты, которые хотят assert call count или симулировать ошибку,
    переопределяют patch внутри тела теста."""
    from google_sheets_db import GameStateRepo

    def fake_load(self):
        return game.state.to_dict() if game.state is not None else {}

    monkeypatch.setattr(GameStateRepo, "load", fake_load)
    # Сброс кэша last_reload между тестами — чтобы badge от предыдущих
    # тестов не протекал в текущий.
    web_sync._reset_for_tests()


def _setup_state(state=None):
    """Сбросить container и заполнить дефолтным state — так lifespan не пойдёт в Sheets."""
    game.state = None
    init_game_state(state if state is not None else GameState.default_new_game())


# ----- /healthz -----

def test_healthz_returns_ok_status():
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["state_loaded"] is True
    assert body["version"] == VERSION


def test_lifespan_initializes_state_idempotent():
    """Если state уже стоит до TestClient — lifespan не пересоздаёт его."""
    _setup_state()
    pre_state = game.state
    with TestClient(app):
        assert game.state is pre_state


def test_unknown_route_returns_404():
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/this-does-not-exist")
    assert response.status_code == 404


# ----- GET / (dashboard) -----

def test_dashboard_returns_html():
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    body = response.text
    assert "2Walks" in body
    assert VERSION in body


def test_dashboard_contains_main_sections():
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/")
    body = response.text
    assert "Stats" in body
    assert "Steps" in body
    assert "Energy" in body
    assert "Money" in body
    assert "Инвентарь" in body
    assert "Экипировка" in body


def test_dashboard_includes_htmx_polling_attributes():
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/")
    body = response.text
    assert 'hx-get="/status"' in body
    assert 'hx-trigger="every 60s"' in body


def test_dashboard_loads_pico_and_htmx_cdn():
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/")
    body = response.text
    assert "@picocss/pico" in body
    assert "htmx.org" in body


def test_dashboard_shows_location_icon_and_name():
    state = GameState.default_new_game()
    state.loc = "gym"
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/")
    body = response.text
    # Icon + capitalized location name.
    assert "🏋" in body  # gym icon (без variation selector U+FE0F — Pico может не отрендерить совсем точно)
    assert "Gym" in body


# ----- GET /status (HTMX fragment) -----

def test_status_fragment_returns_html_without_full_page_wrapper():
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/status")
    assert response.status_code == 200
    body = response.text
    # Это fragment — не должно быть <html>/<body> обёрток.
    assert "<html" not in body.lower()
    assert "<body" not in body.lower()
    # Но содержание секций есть.
    assert "Stats" in body
    assert "Инвентарь" in body


def test_status_fragment_contains_core_stats():
    state = GameState.default_new_game()
    state.steps.today = 5000
    state.steps.can_use = 4500
    state.energy = 30
    state.money = 250
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert "4,500" in body  # steps.can_use formatted
    assert "30" in body
    assert "250" in body


# ----- Active sessions -----

def test_active_training_renders_with_data_end_ts():
    state = GameState.default_new_game()
    state.training.active = True
    state.training.skill_name = "stamina"
    state.training.time_end = datetime(2026, 5, 1, 18, 0, 0)
    state.gym.stamina = 4
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert "Тренировка" in body
    assert "Stamina" in body
    assert "data-end-ts=" in body
    # Целевой уровень: 4 + 1 = 5
    assert "уровень 5" in body


def test_active_work_renders_with_data_end_ts():
    state = GameState.default_new_game()
    state.work.active = True
    state.work.work_type = "factory"
    state.work.salary = 5
    state.work.hours = 4
    state.work.end = datetime(2026, 5, 1, 19, 0, 0)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert "Работа" in body
    assert "Factory" in body
    assert "20 $" in body  # 5 * 4
    assert "data-end-ts=" in body


def test_active_adventure_in_progress_shows_timer():
    state = GameState.default_new_game()
    state.adventure.active = True
    state.adventure.name = "walk_easy"
    # end_ts в будущем — приключение ещё идёт
    state.adventure.end_ts = datetime.now().timestamp() + 600
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert "Walk_Easy" in body
    assert "data-end-ts=" in body
    assert "Adventure finished" not in body


def test_finished_adventure_shows_warning_not_timer():
    """end_ts < now — приключение фактически закончилось, но не финализировано."""
    state = GameState.default_new_game()
    state.adventure.active = True
    state.adventure.name = "walk_15k"
    state.adventure.end_ts = datetime.now().timestamp() - 60  # 1 минуту назад
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert "Adventure finished" in body
    # Таймер на adv не показывается, потому что ветка ушла в "finished"
    # (training/work тоже не активны → data-end-ts отсутствует).
    assert "data-end-ts=" not in body


def test_no_active_sessions_section_omitted():
    """Если все сессии неактивны — секция 'Активные сессии' не рендерится."""
    state = GameState.default_new_game()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert "Активные сессии" not in body


# ----- Inventory / Equipment -----

def test_empty_inventory_shows_placeholder():
    state = GameState.default_new_game()
    state.inventory = []
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert "пусто" in body


def test_inventory_renders_items():
    state = GameState.default_new_game()
    state.inventory = [
        {
            'item_name': ['ring'],
            'item_type': ['ring'],
            'grade': ['s-grade'],
            'characteristic': ['luck'],
            'bonus': [4],
            'quality': [85.5],
            'price': [171],
        }
    ]
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert "Ring" in body
    assert "s-grade" in body
    assert "+4" in body
    assert "Luck" in body
    assert "171 $" in body


def test_equipment_empty_slot_shows_placeholder():
    state = GameState.default_new_game()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Несколько слотов пустые — все выводятся
    assert "Голова" in body
    assert "Ступни" in body
    # И содержат маркер пустоты в равном кол-ве (7 слотов = 7 placeholder'ов).
    assert body.count("— пусто —") >= 7  # +1 если inventory тоже пуст


def test_equipment_filled_slot_shows_item_details():
    state = GameState.default_new_game()
    state.equipment.head = {
        'item_name': ['helmet'],
        'item_type': ['helmet'],
        'grade': ['a-grade'],
        'characteristic': ['stamina'],
        'bonus': [3],
        'quality': [88.0],
        'price': [132],
    }
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert "Helmet" in body
    assert "a-grade" in body
    assert "+3" in body
    assert "Stamina" in body


# ----- Progress bars (active sessions) -----

def test_active_work_renders_progress_bar():
    """Work с известными start/end → <progress> с value в диапазоне 0-100."""
    state = GameState.default_new_game()
    state.work.active = True
    state.work.work_type = "factory"
    state.work.salary = 5
    state.work.hours = 4
    # Старт час назад, конец через час → ~50% прогресса.
    state.work.start = datetime.now() - timedelta(hours=1)
    state.work.end = datetime.now() + timedelta(hours=1)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert "<progress" in body
    assert "data-progress-start-ts=" in body
    assert "data-progress-end-ts=" in body
    # Прогресс примерно 50% — допускаем разброс при флексе тестового запуска.
    import re
    # Берём только session-progress (с data-progress-start-ts), не Level.
    match = re.search(r'<progress[^>]*data-progress-start-ts[^>]*value="([0-9]+\.[0-9]+)"', body)
    assert match, "session <progress> not found"
    pct = float(match.group(1))
    assert 30 <= pct <= 70


def test_active_training_renders_progress_bar():
    state = GameState.default_new_game()
    state.training.active = True
    state.training.skill_name = "stamina"
    state.training.timestamp = (datetime.now() - timedelta(minutes=5)).timestamp()
    state.training.time_end = datetime.now() + timedelta(minutes=5)
    state.gym.stamina = 4
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert "<progress" in body
    # ~50% прогресса.
    import re
    match = re.search(r'<progress[^>]*data-progress-start-ts[^>]*value="([0-9]+\.[0-9]+)"', body)
    assert match
    pct = float(match.group(1))
    assert 30 <= pct <= 70


def test_active_adventure_renders_progress_bar():
    state = GameState.default_new_game()
    state.adventure.active = True
    state.adventure.name = "walk_easy"
    state.adventure.start_ts = (datetime.now() - timedelta(minutes=5)).timestamp()
    state.adventure.end_ts = (datetime.now() + timedelta(minutes=5)).timestamp()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert "<progress" in body
    assert "data-progress-start-ts=" in body
    # Не помечено как finished, прогресс ~50%.
    assert "✓ Завершено" not in body
    import re
    match = re.search(r'<progress[^>]*data-progress-start-ts[^>]*value="([0-9]+\.[0-9]+)"', body)
    assert match
    pct = float(match.group(1))
    assert 30 <= pct <= 70


def test_finished_work_progress_bar_at_100_with_done_marker():
    """Work с end в прошлом → progress 100 + ✓ Завершено."""
    state = GameState.default_new_game()
    state.work.active = True
    state.work.work_type = "factory"
    state.work.salary = 5
    state.work.hours = 4
    state.work.start = datetime.now() - timedelta(hours=2)
    state.work.end = datetime.now() - timedelta(seconds=1)
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert 'value="100.00"' in body
    assert "✓ Завершено" in body


def test_finished_adventure_shows_progress_100_and_claim_warning():
    """Adventure с end в прошлом → progress 100 + ✓ Завершено + warning о CLI claim."""
    state = GameState.default_new_game()
    state.adventure.active = True
    state.adventure.name = "walk_easy"
    state.adventure.start_ts = (datetime.now() - timedelta(hours=1)).timestamp()
    state.adventure.end_ts = (datetime.now() - timedelta(seconds=1)).timestamp()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    assert 'value="100.00"' in body
    assert "✓ Завершено" in body
    assert "Adventure finished" in body
    assert "claim drop" in body


def test_no_active_session_renders_no_progress_bars():
    state = GameState.default_new_game()
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Прогресс-бары секции "Активные сессии" не рендерятся (Level прогресс — только обычный прогресс-бар).
    assert "data-progress-start-ts=" not in body


# ----- Sync (task 4.54.0) -----

def test_get_root_triggers_sheets_reload(monkeypatch):
    """GET / должен дёргать GameStateRepo.load() (свежие данные из Sheets)."""
    from google_sheets_db import GameStateRepo
    calls = []

    def counting_load(self):
        calls.append(1)
        return game.state.to_dict() if game.state else {}

    monkeypatch.setattr(GameStateRepo, "load", counting_load)
    _setup_state()

    with TestClient(app) as client:
        client.get("/")

    assert len(calls) == 1


def test_get_status_does_not_trigger_sheets_reload(monkeypatch):
    """GET /status (HTMX-полинг) — НЕ дёргает Sheets, рендерит из памяти."""
    from google_sheets_db import GameStateRepo
    calls = []

    def counting_load(self):
        calls.append(1)
        return game.state.to_dict() if game.state else {}

    monkeypatch.setattr(GameStateRepo, "load", counting_load)
    _setup_state()

    with TestClient(app) as client:
        client.get("/status")

    assert calls == []


def test_get_root_with_sheets_error_returns_200_and_shows_badge(monkeypatch):
    """Сетевая ошибка во время reload — возвращаем 200 + кэшированный state + badge."""
    from google_sheets_db import GameStateRepo

    def failing_load(self):
        raise RuntimeError("Network down")

    monkeypatch.setattr(GameStateRepo, "load", failing_load)
    _setup_state()

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    body = response.text
    assert "Cloud sync failed" in body
    assert "Network down" in body
    # state остался кэшированным — основной контент рендерится.
    assert "Stats" in body


def test_dashboard_no_badge_when_reload_succeeds():
    """Успешный reload — badge не должен показываться."""
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/")
    body = response.text
    assert "Cloud sync failed" not in body


def test_status_fragment_does_not_show_reload_badge():
    """Badge показывается только в полной странице (dashboard), не в HTMX-фрагменте."""
    _setup_state()
    with TestClient(app) as client:
        # Сначала вызвать reload, чтобы last_reload был заполнен (даже успешный).
        client.get("/")
        response = client.get("/status")
    # Fragment не содержит badge даже после reload.
    assert "Cloud sync failed" not in response.text


def test_dashboard_polling_interval_is_60_seconds():
    """HTMX polling интервал должен быть 60s (4.54.0), не 15s."""
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/")
    body = response.text
    assert 'hx-trigger="every 60s"' in body
    assert 'hx-trigger="every 15s"' not in body


# ----- Section ordering -----

def test_equipment_section_appears_before_inventory():
    """Экипировка идёт раньше инвентаря на странице."""
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    eq_pos = body.find('id="equipment"')
    inv_pos = body.find('id="inventory"')
    assert eq_pos > 0 and inv_pos > 0
    assert eq_pos < inv_pos
