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
    """Мокает GameStateRepo.load и StepsLogRepo.for_day — чтобы тесты не ходили
    в реальный Sheets во время reload + max-merge (4.15). Тесты, которые хотят
    assert call count или симулировать ошибку, переопределяют patch внутри тела
    теста."""
    from google_sheets_db import GameStateRepo, StepsLogRepo

    def fake_load(self):
        return game.state.to_dict() if game.state is not None else {}

    def fake_for_day(self, date_str, user_id=None):
        return []  # пустой лог = max-merge no-op

    monkeypatch.setattr(GameStateRepo, "load", fake_load)
    monkeypatch.setattr(StepsLogRepo, "for_day", fake_for_day)
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


def test_dashboard_does_not_have_htmx_polling_on_status_bar():
    """HTMX polling намеренно отключён в 0.2.0j — цифры обновляются только при
    F5 / submit формы. Таймеры активных сессий двигаются JS на клиенте.
    Endpoint GET /status оставлен для будущего использования (4.54.0.1)."""
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/")
    body = response.text
    # Извлекаем wrapper #status-bar и проверяем что у него нет HTMX-атрибутов
    # для авто-полинга.
    import re
    match = re.search(r'<div id="status-bar"([^>]*)>', body)
    assert match, '#status-bar wrapper not found'
    attrs = match.group(1)
    assert 'hx-get' not in attrs
    assert 'hx-trigger' not in attrs


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


def test_dashboard_no_polling_intervals_present():
    """Полная защита от регрессии: ни 15s, ни 60s polling интервалов на
    странице (HTMX-полинг отключён в 0.2.0j)."""
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/")
    body = response.text
    assert 'hx-trigger="every 15s"' not in body
    assert 'hx-trigger="every 60s"' not in body
    # Любой "every Ns" pattern.
    import re
    assert not re.search(r'hx-trigger="every \d+s"', body)


# ----- Steps input (task 4.48.2) -----

def test_api_steps_valid_value_applies_and_logs(monkeypatch):
    from google_sheets_db import StepsLogRepo
    appended = []
    monkeypatch.setattr(StepsLogRepo, "append",
                        lambda self, ts, steps, source, user_id="alex":
                        appended.append((ts, steps, source)))

    state = GameState.default_new_game()
    state.steps.today = 1000
    state.steps.used = 200
    _setup_state(state)

    with TestClient(app) as client:
        response = client.post("/api/steps", json={"steps": 5000})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["applied"] is True
    assert body["steps_today"] == 5000
    assert state.steps.today == 5000
    # can_use = today - used + bonuses; bonuses = 0 для default state.
    assert state.steps.can_use == 5000 - 200
    assert len(appended) == 1
    assert appended[0][1] == 5000
    assert appended[0][2] == "web"


def test_api_steps_below_today_is_rejected_no_log(monkeypatch):
    from google_sheets_db import StepsLogRepo
    appended = []
    monkeypatch.setattr(StepsLogRepo, "append",
                        lambda self, ts, steps, source, user_id="alex":
                        appended.append((ts, steps, source)))

    state = GameState.default_new_game()
    state.steps.today = 5000
    _setup_state(state)

    with TestClient(app) as client:
        response = client.post("/api/steps", json={"steps": 4000})

    assert response.status_code == 422
    body = response.json()
    assert body["applied"] is False
    assert "должно быть больше" in body["error"]
    assert state.steps.today == 5000  # state не изменён
    assert appended == []  # log не вызван


def test_api_steps_equal_to_today_is_rejected():
    state = GameState.default_new_game()
    state.steps.today = 5000
    _setup_state(state)

    with TestClient(app) as client:
        response = client.post("/api/steps", json={"steps": 5000})

    assert response.status_code == 422
    assert state.steps.today == 5000


def test_api_steps_negative_value_rejected_by_pydantic():
    _setup_state()
    with TestClient(app) as client:
        response = client.post("/api/steps", json={"steps": -1})
    assert response.status_code == 422


def test_api_steps_non_int_rejected():
    _setup_state()
    with TestClient(app) as client:
        response = client.post("/api/steps", json={"steps": "hello"})
    assert response.status_code == 422


def test_api_steps_sheets_error_returns_503_state_unchanged(monkeypatch):
    from google_sheets_db import StepsLogRepo
    def failing_append(self, ts, steps, source, user_id="alex"):
        raise RuntimeError("Network down")
    monkeypatch.setattr(StepsLogRepo, "append", failing_append)

    state = GameState.default_new_game()
    state.steps.today = 1000
    _setup_state(state)

    with TestClient(app) as client:
        response = client.post("/api/steps", json={"steps": 5000})

    assert response.status_code == 503
    body = response.json()
    assert body["ok"] is False
    assert "Sheets unavailable" in body["error"]
    assert state.steps.today == 1000  # state НЕ изменён при Sheets-ошибке


def test_api_steps_with_explicit_ts_and_source(monkeypatch):
    from google_sheets_db import StepsLogRepo
    appended = []
    monkeypatch.setattr(StepsLogRepo, "append",
                        lambda self, ts, steps, source, user_id="alex":
                        appended.append((ts, steps, source)))

    _setup_state()
    with TestClient(app) as client:
        response = client.post("/api/steps", json={
            "steps": 7000,
            "ts": 1746125425.5,
            "source": "auto",
        })

    assert response.status_code == 200
    assert appended[0] == (1746125425.5, 7000, "auto")


# ----- /web/steps (HTML form) -----

def test_web_steps_valid_returns_html_fragment_with_updated_value(monkeypatch):
    from google_sheets_db import StepsLogRepo
    monkeypatch.setattr(StepsLogRepo, "append",
                        lambda self, ts, steps, source, user_id="alex": None)

    state = GameState.default_new_game()
    state.steps.today = 1000
    state.steps.used = 0
    _setup_state(state)

    with TestClient(app) as client:
        response = client.post("/web/steps", data={"steps": "8500"})

    assert response.status_code == 200
    body = response.text
    # Fragment, не полная страница.
    assert "<html" not in body.lower()
    assert "Stats" in body
    # Новый steps.today применён → can_use = 8500 - 0 = 8500.
    assert "8,500" in body
    # Форма закрыта (не form-visible).
    assert 'class="form-visible"' not in body


def test_web_steps_invalid_value_keeps_form_open_with_error_message(monkeypatch):
    from google_sheets_db import StepsLogRepo
    appended = []
    monkeypatch.setattr(StepsLogRepo, "append",
                        lambda self, ts, steps, source, user_id="alex":
                        appended.append((ts, steps, source)))

    state = GameState.default_new_game()
    state.steps.today = 5000
    _setup_state(state)

    with TestClient(app) as client:
        response = client.post("/web/steps", data={"steps": "3000"})

    # Возвращаем 200 с ошибкой в теле — для HTMX swap.
    assert response.status_code == 200
    body = response.text
    assert "должно быть больше" in body
    # form-visible маркер есть.
    assert "form-visible" in body
    # Log не вызван.
    assert appended == []


def test_dashboard_includes_steps_form_with_min_attribute():
    state = GameState.default_new_game()
    state.steps.today = 1500
    _setup_state(state)

    with TestClient(app) as client:
        response = client.get("/")

    body = response.text
    # Форма + клиентская валидация min=today+1.
    assert 'name="steps"' in body
    assert 'min="1501"' in body
    assert 'hx-post="/web/steps"' in body
    # Кнопка Применить и Отмена.
    assert "Применить" in body
    assert "Отмена" in body


def test_dashboard_steps_form_hidden_by_default():
    """form-visible класс отсутствует на свежем dashboard'е."""
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/")
    body = response.text
    # Класс form-visible отсутствует — форма скрыта (CSS hide).
    assert 'class="form-visible"' not in body


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


# ----- Collapsible sections (0.2.0j follow-up) -----

def test_inventory_uses_details_element():
    """Инвентарь обёрнут в <details><summary>, по умолчанию свёрнут."""
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Внутри #inventory есть <details> и <summary>.
    inv_start = body.find('id="inventory"')
    inv_section = body[inv_start:inv_start + 2000]
    assert "<details>" in inv_section
    assert "<summary>" in inv_section
    # Свернут по умолчанию (нет open атрибута).
    assert "<details open" not in inv_section


def test_equipment_uses_details_element():
    """Экипировка обёрнута в <details><summary>, по умолчанию свёрнута."""
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    eq_start = body.find('id="equipment"')
    eq_section = body[eq_start:eq_start + 2000]
    assert "<details>" in eq_section
    assert "<summary>" in eq_section
    assert "<details open" not in eq_section


def test_inventory_summary_shows_count():
    """Summary инвентаря показывает счётчик (N)."""
    state = GameState.default_new_game()
    state.inventory = [
        {"item_name": ["x"], "item_type": ["ring"], "grade": ["a-grade"],
         "characteristic": ["luck"], "bonus": [3], "quality": [80.0], "price": [120]},
        {"item_name": ["y"], "item_type": ["helmet"], "grade": ["b-grade"],
         "characteristic": ["stamina"], "bonus": [2], "quality": [70.0], "price": [70]},
    ]
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Summary содержит "(2)" сразу после "Инвентарь</strong>".
    assert "Инвентарь</strong> (2)" in body


def test_equipment_summary_shows_worn_count():
    """Summary экипировки показывает (N/7)."""
    state = GameState.default_new_game()
    state.equipment.head = {
        "item_name": ["helmet"], "item_type": ["helmet"], "grade": ["a-grade"],
        "characteristic": ["stamina"], "bonus": [3], "quality": [80.0], "price": [120],
    }
    state.equipment.neck = {
        "item_name": ["necklace"], "item_type": ["necklace"], "grade": ["b-grade"],
        "characteristic": ["luck"], "bonus": [2], "quality": [70.0], "price": [70],
    }
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # 2 надетых из 7 → "(2/7)".
    assert "(2/7)" in body


def test_equipment_summary_shows_only_nonzero_bonuses():
    """Summary экипировки показывает только не-нулевые бонусы (stamina выше 0
    видно, energy_max/speed/luck с +0 — спрятаны)."""
    state = GameState.default_new_game()
    state.equipment.head = {
        "item_name": ["helmet"], "item_type": ["helmet"], "grade": ["a-grade"],
        "characteristic": ["stamina"], "bonus": [5], "quality": [80.0], "price": [120],
    }
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Найдём summary блока экипировки.
    eq_start = body.find('id="equipment"')
    summary_start = body.find("<summary>", eq_start)
    summary_end = body.find("</summary>", summary_start)
    summary = body[summary_start:summary_end]
    # stamina ненулевой → отображается с +5.
    assert "stamina +5" in summary
    # Остальные нулевые → скрыты.
    assert "energy_max" not in summary
    assert "speed" not in summary
    assert "luck" not in summary


def test_equipment_summary_no_bonuses_block_when_all_zero():
    """Если ни одного бонуса нет — <small> с "·" префиксом не рендерится в summary."""
    state = GameState.default_new_game()
    # Никакой экипировки → все 4 бонуса = 0.
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Найдём summary блока экипировки.
    eq_start = body.find('id="equipment"')
    summary_start = body.find("<summary>", eq_start)
    summary_end = body.find("</summary>", summary_start)
    summary = body[summary_start:summary_end]
    assert "stamina" not in summary
    assert "energy_max" not in summary
    assert "speed" not in summary
    assert "luck" not in summary
    assert "·" not in summary  # никаких разделителей не осталось


def test_equipment_summary_shows_multiple_nonzero_bonuses():
    """При нескольких ненулевых — все они показаны в summary."""
    state = GameState.default_new_game()
    state.equipment.head = {
        "item_name": ["helmet"], "item_type": ["helmet"], "grade": ["a-grade"],
        "characteristic": ["stamina"], "bonus": [3], "quality": [80.0], "price": [120],
    }
    state.equipment.neck = {
        "item_name": ["necklace"], "item_type": ["necklace"], "grade": ["a-grade"],
        "characteristic": ["luck"], "bonus": [4], "quality": [80.0], "price": [120],
    }
    state.equipment.foots = {
        "item_name": ["shoes"], "item_type": ["shoes"], "grade": ["b-grade"],
        "characteristic": ["speed_skill"], "bonus": [2], "quality": [70.0], "price": [70],
    }
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    eq_start = body.find('id="equipment"')
    summary_start = body.find("<summary>", eq_start)
    summary_end = body.find("</summary>", summary_start)
    summary = body[summary_start:summary_end]
    assert "stamina +3" in summary
    assert "luck +4" in summary
    assert "speed +2" in summary
    # energy_max нулевой → скрыт.
    assert "energy_max" not in summary


def test_bonuses_section_uses_details_collapsed_by_default():
    """Бонусы Steps + Energy перенесены в отдельный <details> блок, свёрнут."""
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    bon_start = body.find('id="bonuses"')
    assert bon_start > 0, "section id=bonuses missing"
    bon_section = body[bon_start:bon_start + 2000]
    assert "<details>" in bon_section
    assert "<summary>" in bon_section
    assert "<details open" not in bon_section


def test_bonuses_section_contains_steps_breakdown():
    state = GameState.default_new_game()
    state.steps.today = 10000
    state.gym.stamina = 5
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    bon_start = body.find('id="bonuses"')
    bon_section = body[bon_start:bon_start + 2000]
    # Внутри секции бонусов: stamina/equipment/daily/level + всего/percent.
    assert "stamina" in bon_section
    assert "equipment" in bon_section
    assert "daily" in bon_section
    assert "level" in bon_section
    assert "Всего:" in bon_section
    assert "%" in bon_section


def test_bonuses_section_contains_energy_breakdown():
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    bon_start = body.find('id="bonuses"')
    bon_section = body[bon_start:bon_start + 2000]
    # Energy block внутри секции бонусов.
    assert "🔋" in bon_section
    assert "Energy" in bon_section


def test_total_used_moved_into_bonuses_section():
    """`Total used: N шагов` перенесено из Stats в свёрнутый блок Бонусы."""
    state = GameState.default_new_game()
    state.steps.total_used = 123456
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Total used должен быть только внутри секции id="bonuses".
    bon_start = body.find('id="bonuses"')
    assert bon_start > 0
    bon_end = body.find('</section>', bon_start)
    bon_section = body[bon_start:bon_end]
    assert "Total used: 123,456" in bon_section
    # И НЕ должен быть ранее по странице (например, в Stats).
    pre_bonuses = body[:bon_start]
    assert "Total used:" not in pre_bonuses


def test_steps_section_no_longer_inline_bonus_line():
    """После переноса в <details> — старая строка 'Bonus 🏃: ...' удалена из стартового
    блока Steps в Stats."""
    state = GameState.default_new_game()
    state.steps.today = 5000
    state.gym.stamina = 5
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Inline-бонус "Bonus 🏃: stamina +X · equipment +Y..." больше не появляется
    # вне details. Внутри details строка ещё есть (там детали показаны).
    # Проверяем по уникальной фразе "Bonus 🏃" — она была в исходной inline-строке.
    assert "Bonus 🏃:" not in body


def test_energy_section_no_longer_inline_bonus_line():
    """После переноса в <details> — строка 'Equipment +X · daily +Y · level +Z'
    под Energy больше не отображается inline."""
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Извлекаем кусок между Energy stat-row и Money stat-row — там не должно
    # быть отдельной "Equipment +N · daily +M · level +K" строки.
    energy_pos = body.find("🔋")
    money_pos = body.find("💰")
    assert 0 < energy_pos < money_pos
    between = body[energy_pos:money_pos]
    # В этом куске нет полного шаблона строки бонусов (она перенесена в <details>).
    import re
    assert not re.search(r"Equipment\s*\+\d+\s*·\s*daily\s*\+\d+\s*·\s*level\s*\+\d+", between)


def test_inventory_items_still_in_dom_when_collapsed():
    """Содержимое <details> остаётся в DOM даже когда блок свёрнут — это
    важно для accessibility и поиска. Браузер только скрывает визуально."""
    state = GameState.default_new_game()
    state.inventory = [{
        "item_name": ["uniqitem"], "item_type": ["ring"], "grade": ["s-grade"],
        "characteristic": ["luck"], "bonus": [4], "quality": [85.0], "price": [170],
    }]
    _setup_state(state)
    with TestClient(app) as client:
        response = client.get("/status")
    body = response.text
    # Item в DOM несмотря на свёрнутость.
    assert "Ring" in body
    assert "s-grade" in body
    assert "+4" in body
