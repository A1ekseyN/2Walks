"""Тесты FastAPI скелета (задача 4.48.0).

Используется ``fastapi.testclient.TestClient`` — он автоматически вызывает
lifespan на входе/выходе из контекста. Перед TestClient мы инициализируем
``game.state`` через ``init_game_state(GameState.default_new_game())``;
повторный вызов в lifespan — no-op (idempotent), Sheets не дёргается.
"""

from fastapi.testclient import TestClient

from characteristics import game, init_game_state
from state import GameState
from web.main import app, VERSION


def _setup_state():
    """Сбросить container и заполнить дефолтным state — так lifespan не пойдёт в Sheets."""
    game.state = None
    init_game_state(GameState.default_new_game())


def test_healthz_returns_ok_status():
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["state_loaded"] is True
    assert body["version"] == VERSION


def test_root_returns_html():
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    body = response.text
    assert "2Walks" in body
    assert VERSION in body


def test_lifespan_initializes_state_idempotent():
    """Если state уже стоит до TestClient — lifespan не пересоздаёт его."""
    _setup_state()
    pre_state = game.state
    with TestClient(app):
        # Внутри lifespan вызвался init_game_state() без аргументов — он idempotent.
        assert game.state is pre_state


def test_root_marks_state_loaded_true_when_initialized():
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/")
    assert "State loaded: <strong>True</strong>" in response.text


def test_unknown_route_returns_404():
    _setup_state()
    with TestClient(app) as client:
        response = client.get("/this-does-not-exist")
    assert response.status_code == 404
