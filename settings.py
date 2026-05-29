# Файл для настроек игры
import os

debug_mode = False      # Включает и отключает debug mode для дополнительный информации. (False / True)

# 4.54.0.3 — Dry-run: безопасная песочница для smoke-проверок live-сервера.
# При DRY_RUN=1 ВСЕ persistence write-paths становятся no-op:
#   - Sheets: GameStateRepo.save / save_safe, StepsLogRepo.append, HistoryLogRepo.append
#   - локальные: state.json (save_characteristic), history.jsonl (log_event)
# Reads работают как обычно → смокаем поверх RAM-копии реального state, прод
# не загрязняется. Защищает и web-смок, и ручной `python -c`-смок.
# Env-driven (НЕ правим файл): `DRY_RUN=1 uvicorn ...` / `DRY_RUN=1 python -c ...`.
dry_run = os.environ.get('DRY_RUN', '').strip().lower() in ('1', 'true', 'yes', 'on')
