# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project context

2Walks is a step-counter RPG written in Python. Real-world steps (entered manually via the `+` command) fuel in-game actions: training at the Gym, Work shifts, Adventures with item drops, etc. Comments and UI text are primarily in Russian. The project targets desktop (Mac); an Android/Kivy build existed historically but was removed — see `git log` before 2026-04-24 if you need to resurrect any of it. A Google Fit auto-sync existed historically but was removed on 2026-04-27 (task 4.16); a future iOS Shortcut → Google Sheets pipeline is planned (tasks 4.13–4.15).

**Primary interface:** CLI (`game.py`). **Secondary (planned):** Web interface via FastAPI backend on a VPS (task 4.48 — incremental rollout). CLI remains the primary path; web is supplementary and grows feature-by-feature. Single source of truth for both — Google Sheets.

## Entry points

A single runnable root:

- `game.py` — pure CLI REPL (`location_selection()` loop). Also re-exported as a function `game()` for programmatic use.

## Common commands

```bash
# Run the game
python game.py

# Manually sync the save to/from Google Sheets
python google_sheets_db.py

# Drop-rate Monte-Carlo simulation (10k×6 iterations)
python drop_test_montecarlo.py
```

Pytest is the test framework (config in `pytest.ini`, tests in `tests/`). Run all tests with `.venv/bin/pytest tests/`. There is no linter or CI configured. `drop_test_montecarlo.py` is a standalone Monte-Carlo drop simulator.

## Architecture

### Game state: `GameState` (state.py)

The single source of game state is a `GameState` dataclass in `state.py` with nested subclasses (`StepsState`, `CharLevel`, `GymSkills`, `TrainingSession`, `WorkSession`, `AdventureSession`, `Equipment`). The live instance is `game_state` exported from `characteristics.py`. Almost every function in gameplay modules takes `state: GameState` as an explicit parameter — there is no implicit global. Mutate `state.<sub>.<field>` to communicate between systems.

A historical legacy dict `char_characteristic` and proxy class were removed in version 0.2.0 (task 1.1). If you encounter that name in old commits or external docs, it referred to today's `game_state`.

`characteristics.py` still loads the save at **import time** (`load_data_from_google_sheet_or_csv()` at module top level), so `import characteristics` can trigger network I/O to Google Sheets (with CSV fallback). Keep this in mind when adding tests or tools — task 1.2 will move this to lazy initialization.

### Persistence layers (three of them)

Saves are written to **all three** on save; loads prefer Google Sheets with CSV fallback:

1. `characteristic.csv` — flat CSV. `save_characteristic()` writes `game_state.to_dict()`; `load_characteristic()` parses back via `ast.literal_eval` for nested dicts/lists. `from_dict()` then reconstructs `GameState`. Datetime keys (`skill_training_time_end`, `working_end`, `adventure_end_timestamp`) are parsed via `%Y-%m-%d %H:%M:%S.%f`.
2. `characteristic.txt` — JSON mirror, same `to_dict()` format.
3. Google Sheets — `google_sheets_db.py` uses gspread + a service-account key at `credentials/2walks_service_account.json`. Spreadsheet ID and sheet name are hardcoded in the function defaults.

When adding new fields to `GameState`, update both `from_dict` and `to_dict` so the round-trip stays clean (the datetime special-case list in `_deser_datetime` / `json_serial` is the common trap).

### Step-count input

`state.steps.today` is set by manual entry only — the `+` command in the main menu invokes `steps_today_manual_entry(state)` (`functions.py`), which reads a number from the player and stores `max(current, entered)`. On date change (`save_game_date_last_enter(state)`), `today` and `used` reset to `0` so the new day starts fresh; the player re-enters the bracelet reading via `+`. `save.txt` holds the last-enter date used for the day-rollover check.

### Mutation helpers: `actions.py`

Non-trivial mutations go through `actions.py` to keep invariants in one place:

- `try_spend(state, steps, energy, money) → bool` — atomic check & deduct. Returns False without mutation if any resource is insufficient.
- `start_work(state, work_type, salary, hours, start, end)` — populate `state.work` for a session.
- `start_training(state, skill_name, time_end, timestamp)` — populate `state.training`.
- `start_adventure(state, name, start_ts, end_ts)` — populate `state.adventure`.

### Gameplay module map

- `locations.py` — dispatch layer between `game.py` and each location module; `icon_loc(state)` maps `state.loc` to an emoji.
- `gym.py`, `work.py`, `adventure.py`, `shop.py`, `inventory.py`, `equipment.py` — one per location/menu. `work_check_done(state)` and `skill_training_check_done(state)` are polled from the main loop to finalize timer-based activities; if you add another timed action, follow the same "check on every tick" pattern.
- `drop.py` — item drop logic for Adventure. Grades are `c/b/a/s/s+`, weighted by `drop_percent_*` constants. `current_luck(state)` is computed at the moment of the drop (no module-level pinning).
- `level.py` (`CharLevel`), `characteristics.py` (`save_characteristic`), `bonus.py`, `equipment_bonus.py`, `skill_bonus.py` — stat/bonus math. All take `state` explicitly.
- `adventure_data.py` — static data table for adventures. Adventure `__init__` copies entries before applying `move_optimization` so the table itself is never mutated.
- `functions.py` / `functions_02.py` — cross-cutting helpers (`status_bar`, `energy_time_charge`, `char_info`, date/time helpers).
- `settings.py` — `debug_mode` flag consumed by many modules for verbose logging.

### Tests

`tests/` contains pytest suites for each module. Pure logic helpers (`_sort_inventory`, `_buy_item`, `_equip_from_inventory`, `try_spend`, formula functions) are tested directly with hand-built `GameState` instances. UI methods that use `input()`/`print()` are tested via `capsys` and `monkeypatch.setattr('builtins.input', ...)`. Tests do not depend on Google Sheets — `import` of test modules can still trigger I/O via `characteristics.py`, but tests themselves construct a fresh `GameState` per case.

### Credentials and ignored files

`.gitignore` excludes the `credentials/` directory (which must contain `2walks_service_account.json` for Sheets to work). When running locally for the first time, expect Sheets calls to fail until that file is provided; loaders fall back to CSV automatically (`characteristics.py:92`).
