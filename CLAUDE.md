# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project context

2Walks is a console-only step-counter RPG written in Python. Real-world steps (pulled from Google Fit) fuel in-game actions: training at the Gym, Work shifts, Adventures with item drops, etc. Comments and UI text are primarily in Russian. The project targets desktop (Mac); an Android/Kivy build existed historically but was removed — see `git log` before 2026-04-24 if you need to resurrect any of it.

## Entry points

A single runnable root:

- `game.py` — pure CLI REPL (`location_selection()` loop). Also re-exported as a function `game()` for programmatic use.

## Common commands

```bash
# Run the game
python game.py

# Re-auth Google Fit (regenerates token.json via OAuth browser flow)
python get_token_fitnes_api.py

# Manually sync the save to/from Google Sheets
python google_sheets_db.py

# Drop-rate simulation (NOT a unit test; runs 10k×6 iterations on import)
python test_drop.py
```

There is no test framework, linter, or CI configured. `test_drop.py` is a Monte-Carlo simulator, not a pytest suite — it calls `test_item_generation()` at module load, so merely importing it triggers a long run.

## Architecture

### Global mutable state: `char_characteristic`

Nearly every gameplay module reads and writes a single module-level dict `char_characteristic` defined in `characteristics.py:107`. It holds stats (energy, money, skills), equipment, inventory, timers (`skill_training_time_end`, `working_end`, `adventure_end_timestamp`), and current location. When editing game logic, assume it is shared, mutable, and imported by `from characteristics import char_characteristic`. Mutating it in one module is the primary way gameplay systems communicate.

A consequence: `characteristics.py` loads the save at **import time** by calling `load_data_from_google_sheet_or_csv()` at module top level (`characteristics.py:101`). Any import of `characteristics` can therefore trigger network I/O to Google Sheets (with CSV fallback). Keep this in mind when adding tests or tools.

### Persistence layers (three of them)

Saves are written to **all three** on save; loads prefer Google Sheets with CSV fallback:

1. `characteristic.csv` — flat CSV via `load_characteristic()` / `save_characteristic()` in `characteristics.py`. Uses `ast.literal_eval` to round-trip nested dicts/lists; specific keys (`skill_training_time_end`, `working_end`, `adventure_end_timestamp`) are parsed back to `datetime` with format `%Y-%m-%d %H:%M:%S.%f`.
2. `characteristic.txt` — JSON mirror (also used by `api.py` to cache `steps_today`).
3. Google Sheets — `google_sheets_db.py` uses gspread + a service-account key at `credentials/2walks_service_account.json`. Spreadsheet ID and sheet name are hardcoded in the function defaults.

When adding new fields to `char_characteristic`, make sure they survive both CSV and Sheets round-trips (the datetime special-case list is the common trap).

### Step-count integration (Google Fit)

`api.steps_today_update()` is the only source of fresh step counts. It compares `save.txt` (last-enter date) with today; only on a date change does it hit the Fitness REST endpoint. OAuth lives in `get_token_fitnes_api.py` (`token.json` cached; re-auth on 401 by deleting the file and recursing). Requires `fitness_api_credential.json` (OAuth client secrets) next to the code. Both `token.json` and `fitness_api_credential.json` are gitignored.

### Gameplay module map

- `locations.py` — dispatch layer between `game.py` and each location module; also maps `char_characteristic['loc']` to an emoji.
- `gym.py`, `work.py`, `adventure.py`, `shop.py`, `inventory.py`, `equipment.py` — one per location/menu. `work_check_done()` and `skill_training_check_done()` are polled from the main loop to finalize timer-based activities; if you add another timed action, follow the same "check on every tick" pattern.
- `drop.py` / `drop_simulator.py` — item drop logic for Adventure. Grades are `c/b/a/s/s+`, weighted by `drop_percent_*` constants and a `luck_chr` computed from skill + equipment bonuses at import time.
- `level.py` (`CharLevel`), `characteristics.py` (`char_info`, `save_characteristic`), `bonus.py`, `equipment_bonus.py`, `skill_bonus.py` — stat/bonus math.
- `adventure_data.py` — static data table for adventures.
- `functions.py` / `functions_02.py` — cross-cutting helpers (`status_bar`, `energy_time_charge`, `location_change_map`, date/time helpers).
- `settings.py` — `debug_mode` flag consumed by many modules for verbose logging.

### Credentials and ignored files

`.gitignore` excludes `token.json`, `fitness_api_credential.json`/`.txt`, and the `credentials/` directory (which must contain `2walks_service_account.json` for Sheets to work). When running locally for the first time, expect Sheets calls to fail until that file is provided; loaders fall back to CSV automatically (`characteristics.py:92`).
