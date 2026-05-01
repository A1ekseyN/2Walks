"""FastAPI скелет 2Walks (задача 4.48.0).

Запуск локально для разработки:
    uvicorn web.main:app --reload --host 127.0.0.1 --port 8008

Запуск с переменными окружения для VPS:
    WEB_HOST=0.0.0.0 WEB_PORT=8008 uvicorn web.main:app

Сейчас включает только:
- ``GET /healthz`` — health-check endpoint (ok / state_loaded).
- ``GET /`` — заглушка-страница (наполнится в 4.48.1).

Состояние ``game.state`` инициализируется в lifespan на старте процесса
через ``init_game_state()`` (idempotent — повторный вызов no-op).

CLI и web — отдельные процессы. В MVP-версии запускаем только что-то одно
за раз. Sync resolution CLI ↔ Web — отдельная задача (4.54).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from characteristics import game, init_game_state


VERSION = "0.2.0e"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: грузим Sheets / CSV в game.state.
    init_game_state()
    yield
    # Shutdown: пока ничего. В будущем — auto-save при остановке uvicorn.


app = FastAPI(title="2Walks Web", version=VERSION, lifespan=lifespan)


@app.get("/healthz")
async def healthz():
    """Health-check для smoke и future load balancer / monitoring."""
    return JSONResponse({
        "status": "ok",
        "state_loaded": game.state is not None,
        "version": VERSION,
    })


@app.get("/", response_class=HTMLResponse)
async def root():
    """Заглушка главной страницы. Полноценный dashboard — задача 4.48.1."""
    state_loaded = game.state is not None
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>2Walks — Web (in progress)</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 600px; margin: 2rem auto; padding: 0 1rem;">
    <h1>2Walks — версия {VERSION}</h1>
    <p>Web interface coming в задаче <strong>4.48.1</strong>.</p>
    <p>State loaded: <strong>{state_loaded}</strong></p>
    <p>Health: <a href="/healthz">/healthz</a></p>
</body>
</html>"""
