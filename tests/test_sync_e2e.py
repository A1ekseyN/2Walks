"""End-to-end сценарии optimistic concurrency CLI ↔ Web (задача 4.54.7).

Здесь имитируется **поведение двух процессов** (CLI и web-uvicorn) через
shared in-memory `FakeSheetsBackend` — общий dict, который оба «процесса»
читают и пишут. Это позволяет прогнать реальную логику `save_safe` /
`load_meta` / `handle_stale_prompt` end-to-end без сети.

Покрытые сценарии (из дизайн-дока 4.54 → 4.54.7):

1. **CLI победил** — CLI сохранил, web загрузил → видит изменения.
2. **Web победил** — web сохранил, CLI получает STALE на save, через
   handle_stale_prompt('r') re-load'ит и redo save → OK.
3. **Параллельные saves** — два процесса с одинаковым `expected` → один
   OK, второй STALE (race detected).
4. **Migration legacy** — save без поля `last_modified` (pre-4.54
   формат) → load возвращает 0.0 → первый save_safe = OK + проставляет
   реальный timestamp.
5. **log_event payload** — sync_conflict содержит правильные поля
   (source, diff brief, choice / endpoint).

Юнит-тесты низкого уровня (save_safe / load_meta / diff_states /
handle_stale_prompt по отдельности) — в `test_sheets_repo.py`,
`test_sync_diff.py`, `test_characteristics.py`. Здесь — composition.
"""

import time

import pytest

import characteristics
import google_sheets_db
import history
from characteristics import game, init_game_state, save_characteristic
from state import GameState


def _reset_game_container() -> None:
    """Сброс container'а между тестами — повторяет паттерн из test_characteristics."""
    game.state = None


# ---------------------------------------------------------------------------
# FakeSheetsBackend — shared dict-симулятор Google Sheets для двух «процессов».
# ---------------------------------------------------------------------------

class FakeSheetsBackend:
    """In-memory замена Google Sheets `game_state` листа.

    Хранит `state_dict` + `last_modified`. Несколько `GameStateRepo`
    instance'ов после patch_repo() видят один и тот же backend — что и
    моделирует два процесса CLI ↔ web на одном Sheets.

    `save_safe` (реальная) внутри зовёт `load_meta()` (read) + `self.save()`
    (write) + `state_dict['last_modified'] = time.time()` — патчим только
    эти примитивы, оставляя реальную логику OK/STALE check'а нетронутой.
    """

    def __init__(self, initial_state: dict | None = None,
                 initial_last_modified: float = 0.0):
        self.state: dict = dict(initial_state) if initial_state else {}
        if initial_last_modified:
            self.state['last_modified'] = initial_last_modified

    @property
    def last_modified(self) -> float:
        return float(self.state.get('last_modified', 0.0) or 0.0)

    def install(self, monkeypatch) -> None:
        """Подмена `GameStateRepo.load_meta/load/save` чтобы реальный
        `save_safe` оперировал на этом backend'е."""
        backend = self

        def fake_load_meta(self):
            return backend.last_modified

        def fake_load(self):
            return dict(backend.state)

        def fake_save(self, state_dict):
            backend.state = dict(state_dict)

        monkeypatch.setattr(google_sheets_db.GameStateRepo, 'load_meta', fake_load_meta)
        monkeypatch.setattr(google_sheets_db.GameStateRepo, 'load', fake_load)
        monkeypatch.setattr(google_sheets_db.GameStateRepo, 'save', fake_save)


# ---------------------------------------------------------------------------
# Scenario 1: CLI победил → web видит изменения после load.
# ---------------------------------------------------------------------------

def test_scenario_cli_wins_web_sees_changes(monkeypatch, tmp_path):
    """CLI save → OK; backend обновлён; web load видит свежие данные."""
    monkeypatch.chdir(tmp_path)

    # Backend стартует с money=500.
    initial = GameState.default_new_game()
    initial.money = 500.0
    backend = FakeSheetsBackend(initial.to_dict(), initial_last_modified=100.0)
    backend.install(monkeypatch)

    # CLI «процесс»: load → mutate money → save.
    _reset_game_container()
    cli_state = GameState.from_dict(backend.state)
    cli_state.take_snapshot()
    init_game_state(cli_state)
    game.state.money = 800.0
    status = save_characteristic()

    assert status == "OK"
    # Backend обновлён.
    assert backend.state['money'] == 800.0
    # last_modified стал свежий.
    cli_ts = backend.last_modified
    assert cli_ts > 100.0

    # Web «процесс»: свежий load из backend → видит 800.
    web_state = GameState.from_dict(backend.state)
    assert web_state.money == 800.0
    assert web_state.last_modified == cli_ts


# ---------------------------------------------------------------------------
# Scenario 2: Web победил → CLI получает STALE → reload + redo → OK.
# ---------------------------------------------------------------------------

def test_scenario_web_wins_then_cli_reload_and_redo(monkeypatch, tmp_path):
    """Полный flow: оба загрузили; web сохранил первым; CLI на save
    получает STALE; через handle_stale_prompt('r') re-init'ит state из
    backend; повторный save → OK."""
    monkeypatch.chdir(tmp_path)

    initial = GameState.default_new_game()
    initial.money = 500.0
    backend = FakeSheetsBackend(initial.to_dict(), initial_last_modified=100.0)
    backend.install(monkeypatch)

    # Шаг 1: оба процесса загрузили один и тот же snapshot (expected=100).
    web_state_dict = dict(backend.state)
    cli_state_dict = dict(backend.state)

    # Шаг 2: web мутирует и сохраняет первым → backend.last_modified прыгает к t1.
    _reset_game_container()
    web_state = GameState.from_dict(web_state_dict)
    web_state.take_snapshot()
    init_game_state(web_state)
    game.state.money = 1100.0  # web заработал на work_done +600
    status = save_characteristic()
    assert status == "OK"
    t1 = backend.last_modified
    assert t1 > 100.0
    assert backend.state['money'] == 1100.0

    # Шаг 3: CLI пытается сохранить со своим expected=100 → STALE.
    _reset_game_container()
    cli_state = GameState.from_dict(cli_state_dict)
    cli_state.take_snapshot()
    init_game_state(cli_state)
    game.state.money = 700.0  # CLI потратил 200 в магазине
    status = save_characteristic()
    assert status == "STALE"
    # Backend не перезаписан CLI — money остаётся 1100 от web.
    assert backend.state['money'] == 1100.0

    # Шаг 4: CLI пользователь выбирает Reload → handle_stale_prompt re-init из backend.
    monkeypatch.setattr('builtins.input', lambda *a, **k: 'r')
    choice = characteristics.handle_stale_prompt()
    assert choice == 'reload'
    # State теперь имеет money=1100 (web'овский) и свежий last_modified=t1.
    assert game.state.money == 1100.0
    assert game.state.last_modified == t1

    # Шаг 5: CLI повторно мутирует и сохраняет — теперь expected=t1, save=OK.
    game.state.money = 900.0  # CLI потратил 200 от web'овских 1100
    status = save_characteristic()
    assert status == "OK"
    assert backend.state['money'] == 900.0
    assert backend.last_modified > t1


# ---------------------------------------------------------------------------
# Scenario 3: Параллельные saves — race на одинаковом expected.
# ---------------------------------------------------------------------------

def test_scenario_parallel_saves_one_wins_other_stale(monkeypatch, tmp_path):
    """Два процесса с одинаковым `expected_last_modified=100`. Первый
    save_safe пишет → backend ts=t1. Второй save_safe с тем же expected=100
    видит t1 > 100 → STALE."""
    monkeypatch.chdir(tmp_path)

    initial = GameState.default_new_game()
    backend = FakeSheetsBackend(initial.to_dict(), initial_last_modified=100.0)
    backend.install(monkeypatch)

    repo = google_sheets_db.GameStateRepo()

    # Process A: первый save проходит.
    state_a = initial.to_dict()
    state_a['money'] = 200.0
    status_a = repo.save_safe(state_a, expected_last_modified=100.0)
    assert status_a == "OK"
    assert backend.state['money'] == 200.0
    t1 = backend.last_modified
    assert t1 > 100.0

    # Process B: со старым expected=100 → STALE (backend уже t1).
    state_b = initial.to_dict()
    state_b['money'] = 300.0
    status_b = repo.save_safe(state_b, expected_last_modified=100.0)
    assert status_b == "STALE"
    # Backend НЕ перезаписан process B.
    assert backend.state['money'] == 200.0
    assert backend.last_modified == t1


# ---------------------------------------------------------------------------
# Scenario 4: Migration — legacy save без `last_modified`.
# ---------------------------------------------------------------------------

def test_scenario_legacy_save_without_last_modified_passes_first_save(monkeypatch, tmp_path):
    """Pre-4.54 save в Sheets не имеет ключа `last_modified`. После 4.54
    deploy: load_meta() возвращает 0.0 (default), GameState.from_dict
    тоже даёт 0.0. Первый save_safe(expected=0.0) сравнивает с 0.0 → match
    (с epsilon) → OK. После save backend.state['last_modified'] — реальный ts."""
    monkeypatch.chdir(tmp_path)

    # Legacy state — БЕЗ last_modified.
    legacy_state = GameState.default_new_game().to_dict()
    legacy_state.pop('last_modified', None)
    backend = FakeSheetsBackend(legacy_state)  # initial_last_modified=0.0
    backend.install(monkeypatch)

    assert 'last_modified' not in backend.state or backend.state.get('last_modified', 0.0) == 0.0
    assert backend.last_modified == 0.0

    # Repo load → from_dict default → state.last_modified=0.0.
    _reset_game_container()
    s = GameState.from_dict(backend.state)
    assert s.last_modified == 0.0
    s.take_snapshot()
    init_game_state(s)
    game.state.money = 999.0

    before_ts = time.time()
    status = save_characteristic()
    after_ts = time.time()

    assert status == "OK"
    # Backend теперь содержит реальный last_modified ≈ now().
    new_ts = backend.last_modified
    assert before_ts <= new_ts <= after_ts
    # GameState синкан с новым ts.
    assert game.state.last_modified == new_ts
    # Money сохранён.
    assert backend.state['money'] == 999.0


# ---------------------------------------------------------------------------
# Scenario 5: log_event sync_conflict payload — все три choice.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("user_choice,expected_choice,extra_inputs", [
    ('c', 'cancel', []),
    ('r', 'reload', []),
    ('f', 'force', ['yes']),  # Force требует двойного confirm.
])
def test_scenario_log_event_sync_conflict_payload(
    monkeypatch, tmp_path, user_choice, expected_choice, extra_inputs
):
    """Все три варианта STALE-prompt'а пишут log_event('sync_conflict',
    source='cli', diff=<brief>, choice=<choice>) с правильным payload."""
    monkeypatch.chdir(tmp_path)

    initial = GameState.default_new_game()
    initial.money = 500.0
    backend = FakeSheetsBackend(initial.to_dict(), initial_last_modified=100.0)
    backend.install(monkeypatch)

    # Setup state с snapshot=initial; затем backend «уезжает» вперёд (web сохранил).
    _reset_game_container()
    s = GameState.from_dict(backend.state)
    s.take_snapshot()
    init_game_state(s)

    # «Web» обновил backend пока CLI думал.
    backend.state['money'] = 1500.0
    backend.state['last_modified'] = 200.0

    # Перехват log_event (поверх autouse no-op fixture'а).
    events: list[tuple[str, dict]] = []
    monkeypatch.setattr(history, 'log_event',
                        lambda evt_type, **payload: events.append((evt_type, payload)))

    # Сценарий ввода: первый input = user_choice, далее extra_inputs.
    inputs = iter([user_choice] + extra_inputs)
    monkeypatch.setattr('builtins.input', lambda *a, **k: next(inputs))

    choice = characteristics.handle_stale_prompt()
    assert choice == expected_choice

    # log_event('sync_conflict', ...) ровно один раз с правильным payload.
    sync_events = [e for e in events if e[0] == 'sync_conflict']
    assert len(sync_events) == 1, f'Ожидался 1 sync_conflict event, получено {len(sync_events)}: {sync_events}'
    payload = sync_events[0][1]
    assert payload['source'] == 'cli'
    assert payload['choice'] == expected_choice
    # diff brief непустой и содержит изменение money (💰 +1000 от 500→1500).
    assert 'diff' in payload
    assert payload['diff']  # непустая строка
    # money change должно быть видно в brief.
    assert '💰' in payload['diff'] or '1,000' in payload['diff'] or '1000' in payload['diff']
