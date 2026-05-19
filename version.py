"""Каноническая версия игры. Единая точка правды.

Используется:
- `game.py` — печатает на старте (`Version: 0.x.y`).
- `web/main.py` — `VERSION` в FastAPI app + dashboard footer.
- `history.py` — `game_version` поле в каждом логе события (4.6).

Bump версии — здесь. Все три файла подхватят автоматически.
"""

VERSION = "0.2.4v"
