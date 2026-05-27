# Triumphs / Достижения — система и каталог

Документ описывает Destiny-2-inspired систему достижений в 2Walks: архитектуру, mechanics, state schema, и полный каталог triumph'ов на момент актуальной версии. Цель — чтобы при добавлении новых triumph'ов / категорий / bonuses было понятно «что уже есть и как оно работает».

Status: **active since 0.2.5j (22.05.2026)**. Зонтичная задача **4.62** в TASKS.md, см. секцию «4.62. Triumphs» для полного breakdown подзадач.

---

## 1. Высокоуровневая концепция

Игрок прогрессирует через 4 уровня:

```
Trigger (action) → Triumph progress → Capstone (last tier) → Seal → Title
     log_event        counter / metric       all tiers done       category    cosmetic
        ↓                ↓                       ↓                  ↓           ↓
   work_done       Hard Worker            Hard Worker          Workaholic    👑 Workaholic
   hours=4         500h → 1000h               10000h              seal       в status_bar
```

- **Triumph** — одно достижение с 4-5 tier'ами. Пример: «Marathoner» с tiers `[100k, 500k, 1M, 5M, 10M]` спрятанных шагов.
- **Capstone** — последний (самый сложный) tier triumph'а. «Capstone достигнут» = triumph полностью пройден.
- **Seal** — закрыл **все capstones** в категории. Пример: для категории `gym` нужно довести все 20 per-skill triumph'ов до lvl 30 + Skill Master до 1000.
- **Title** — cosmetic «звание» которое игрок может надеть; даётся как право использования с unlocked seal.

Дополнительные слои поверх:

- **Pinned** (4.62.4) — игрок выбирает до 3 triumph'ов для приоритетного показа в status_bar.
- **Claim queue** (4.62.4) — новые tier-unlocks требуют **явного acknowledge** через menu (Destiny-2 паттерн «нашёл — нужно собрать»).
- **Score** — каждый **собранный (claimed)** tier даёт `POINTS_PER_TIER` (10) очков → суммарный `total_score(state)`. **Важно (0.2.6 fix):** очки начисляются за claimed tier'ы (`unlocked − unclaimed`), а НЕ за unlock — Destiny-2 паттерн «нашёл → собрал → засчиталось». До фикса score считался по unlocked tier и рассинхронивался с `X/Y tiers` counter'ом (Score 210 при 0/196 claimed).

**Не входит** в систему на момент 0.2.6: gameplay-бонусы за capstones (Phase 4 — задача 4.62.2.1, **deferred** 25.05.2026 до balance design), Hidden triumphs (4.62.5). Web UI **добавлен** в 0.2.5y (4.62.7) — параллельная вёрстка к CLI menu, **UX-polished** в 0.2.5z (4.62.7.1 — per-tier claim + section перенесена в конец dashboard'а) и **дополнительно** в 0.2.6 (4.62.7.2/3 — claimed tier counts в category labels: `🏃 Шаги · 3/5` вместо misleading `1/1`, growing по мере claim'ов).

---

## 2. Архитектура

3 base модуля + Web UI слой + auto-hook'и в существующих модулях:

| Модуль | Слой | Содержит |
|---|---|---|
| `triumphs_data.py` | Static catalog | `POINTS_PER_TIER`, `CATEGORIES`, `SEALS`, `TRIUMPHS` (dict[id, spec]), helper `_GYM_SKILL_FIELDS` |
| `triumphs.py` | Pure engine | `register_event` / `init_metric_check` / `get_progress` / `total_score` / `backfill_from_history` / `backfill_from_sheets_history`, claim helpers (`append_unclaimed`, `claim_triumph (batch)`, `claim_one_tier (per-tier, since 0.2.5z)`, `next_unclaimed_tier (UI helper)`, `claim_all`, `get_unclaimed_for`, `backfill_unclaimed_from_existing`), seal helpers (`is_seal_unlocked`, `available_seals`, `available_titles`, `set_title`, `check_seal_unlocks`), progress bar formatter `_format_progress_bar` |
| `triumphs_menu.py` | CLI UI | `open_triumphs_menu` (3-level navigation: main → category → detail), Pin/Unpin toggle, Claim flow, Seals view, `render_pinned_status_bar` (для `functions.status_bar`) |
| `web/main.py` | Web UI (since 0.2.5y / 4.62.7) | `_build_triumphs_view(state) -> dict` (pre-computed nested view: pinned_rows / unclaimed / categories / seals со всеми flags), `_validate_and_apply_pin/claim/claim_all/seal_toggle/backfill_sheets` helpers, 10 endpoints (5 web Form HTMX + 5 API JSON Pydantic) |
| `web/templates/_status_fragment.html` | Web template | Top banners над Stats (unclaimed + pinned), title badge в Stats header (float-right), main `<section id="triumphs">` **в конце dashboard'а после Inventory** (since 4.62.7.1 / 0.2.5z; collapsible + sub-collapsibles per category + Seals sub-section + Backfill button) |

Auto-hook'и:

- **`history.py:log_event`** — после write event'а вызывает `register_event(state, type, **payload)` + `append_unclaimed` для returned unlocks + `check_seal_unlocks` + `append_unclaimed` для seal unlocks. Try/except / silent fail / lazy import чтобы избежать circular dependency.
- **`characteristics.py:init_game_state`** — на startup: `backfill_unclaimed_from_existing` (one-shot synth для уже-unlocked tier'ов из state.triumphs) + `init_metric_check` (auto-unlock metric-based) + `check_seal_unlocks` (для existing players у которых уже все capstones категории закрыты).
- **`functions.py:status_bar`** — на каждом tick'е CLI печатает `render_pinned_status_bar(state)` (unclaimed banner + pinned section) + строку `👑 <title>` если `state.title` non-None.
- **`web/main.py:_dashboard_context`** — на каждом GET / POST web возвращает `triumphs_view = _build_triumphs_view(state)` в template context → top banners + title badge + main section рендерятся conditionally (visible если есть pinned / unclaimed / title).

---

## 3. State schema

Всё хранится в `GameState` (state.py) и round-trip'ится через `to_dict`/`from_dict`:

```python
# 4.62.0.1 — Triumph progress (sparse — entry создаётся при первом progress).
triumphs: dict[str, dict] = field(default_factory=dict)
# Entry structure: {
#   'tier': int (highest unlocked tier, 0 = none),
#   'unlocked_at': dict[str→str] (tier index → ISO datetime),
#   'count': int (event-based accumulator counter; metric-based не использует),
# }

# 4.62.0.1 — Pinned triumph IDs (≤3 enforced в pin operation).
pinned_triumphs: list[str] = field(default_factory=list)

# 4.62.0.1 — Selected title из unlocked seals.
title: Optional[str] = None

# 4.62.0.2 — Backfill prompt dismiss flag (one-shot UI control).
triumphs_backfill_dismissed: bool = False

# 4.62.4 — Unclaimed unlocks queue (Destiny-2 claim mechanic).
# Entries: {'triumph_id': str, 'tier': int, 'unlocked_ts': float, 'kind': 'triumph' | 'seal'}
# `kind='seal'` (4.62.3) → triumph_id = category key, tier = 0 (unused).
unclaimed_unlocks: list[dict] = field(default_factory=list)
```

**Дополнительный pseudo-entry** в `state.triumphs`:

```python
state.triumphs['__seal__'] = {'acknowledged': list[str]}
# Tracks которые seal cat_keys уже push'нуты в unclaimed queue —
# для idempotency check_seal_unlocks. Создаётся lazy через setdefault.
# Defensive: iteration кода `triumphs.py:backfill_unclaimed_from_existing`
# делает `spec = TRIUMPHS.get(triumph_id)` → None для '__seal__' → skip.
```

---

## 4. Два типа triumph'ов

### Metric-based

Читает state напрямую через lambda. Используется когда есть **persistent counter** уже в state.

```python
'marathoner': {
    'name': 'Marathoner',
    'category': 'steps',
    'tiers': [100_000, 500_000, 1_000_000, 5_000_000, 10_000_000],
    'metric': lambda state: state.steps.total_used,
}
```

**Auto-unlock на старте** через `init_metric_check(state)` в `init_game_state` — existing players мгновенно получают credit за всю прошлую игру **без backfill**.

**Recheck** на любом `register_event` (любой log_event):
```python
for triumph_id, spec in TRIUMPHS.items():
    current = _read_current_value(state, spec)
    newly = _check_tier_unlocks(state, triumph_id, spec, current)
    # newly = list of tier indices unlocked at this call
```

### Event-based

Counter в `state.triumphs[id]['count']` accumulates на каждом matching `log_event`. Используется когда persistent counter в state **нет** — нужно считать события.

```python
'workhorse': {
    'name': 'Workhorse',
    'category': 'energy',
    'tiers': [1_000, 5_000, 10_000, 50_000],
    'event_hooks': ['work_start', 'work_extend'],  # типы событий
    'count_delta': lambda p: int(p.get('cost_energy', 0) or 0),  # сколько добавить
    'event_filter': lambda p: p.get('vacancy') == 'watchman',  # опционально
}
```

**Backfill из `history.jsonl`** через `backfill_from_history(state, path)` — replay'ит все события файла, accumulate counters, recheck tier unlocks. Идемпотентен (reset counters → replay).

**Backfill sources (since 4.62.6 / 0.2.5x):** два варианта в Triumphs menu —
- `[b] 🌐 Backfill из Sheets` (recommended) — `backfill_from_sheets_history(state)` через `HistoryLogRepo.since(0)`, cross-device (CLI + server's web events). Sheets-first с auto-fallback на local jsonl при network error.
- `[r] 🔄 Re-sync local jsonl` — `backfill_from_history(state, path)`, только local file (offline fallback).

Оба пути используют shared internal `_replay_events_into_counters(state, events)` helper — identical behavior для одинаковых events.

### Max-tracking (гибрид metric + hook)

Engine не имеет встроенного `count_mode='max'`. Для триумфов «**максимум** одного события за всю историю» (longest shift, biggest single drop, highest day streak) использовать pattern «metric + hook»:

1. Новое поле в state для max-tracker'а (например `state.work.longest_shift_hours`).
2. Hook в mutation function (`work.py:work_check_done`) обновляет поле ПЕРЕД `log_event`: `state.work.longest_shift_hours = max(current, this_event)`.
3. Triumph — metric-based, читает поле напрямую.
4. One-shot backfill helper в `characteristics.py` сканирует `history.jsonl` для `max(payload[field])` (запускается only-if поле == 0).

Пример: **Iron Worker** (Work category, 4.62.1.5.1) — `state.work.longest_shift_hours` + `_backfill_longest_shift_from_history`. См. секцию 12 для рецепта.

---

## 5. Capstone & Seal logic

**Capstone** = `unlocked_tier == len(spec['tiers'])`. Marker:

```python
unlock_event['is_capstone'] = (tier_idx == len(spec.get('tiers', [])))
```

UI рендерит capstone'нутый triumph специально (золотая «Capstone» label в Detail view).

**Seal unlocked** = ВСЕ triumph'ы категории на capstone:

```python
def is_seal_unlocked(state, cat_key):
    cat_triumph_ids = [tid for tid, spec in TRIUMPHS.items()
                       if spec.get('category') == cat_key]
    if not cat_triumph_ids:
        return False  # пустая категория не unlock'ает seal
    for tid in cat_triumph_ids:
        total_tiers = len(TRIUMPHS[tid].get('tiers', []))
        if int(state.triumphs.get(tid, {}).get('tier', 0)) < total_tiers:
            return False
    return True
```

**Symmetry с claim mechanic:** seal unlock попадает в `unclaimed_unlocks` через `check_seal_unlocks` → idempotency через `state.triumphs['__seal__']['acknowledged']` marker. Acknowledged seal удаляется из queue при claim, но `acknowledged` flag остаётся → повторно в queue не попадает.

---

## 6. Pinned mechanic (4.62.4)

- `state.pinned_triumphs` cap = 3 (enforced в `_toggle_pin`, не в schema).
- **Smart replace prompt** при попытке pin 4-го: «У тебя уже 3 закреплено. Какой заменить? [1/2/3/c]».
- Auto-unpin на capstone = **НЕТ** (capstone остаётся в pinned как trophy — design choice 25.05.2026).
- Display: pinned section в начале Triumphs main menu + в `functions.status_bar` через `render_pinned_status_bar`. Лимит 3 строки.
- Visual marker `📌` рядом с pinned triumph в category list / detail view.

---

## 7. Claim mechanic (4.62.4, per-tier UX 4.62.7.1)

Destiny-2 паттерн: при unlock игрок видит индикатор и должен **явно acknowledge**. Эмоциональный payoff — без этого triumph закрывается в фоне.

**Flow:**
1. `register_event` returns list newly-unlocked tiers.
2. Auto-hook (`history.log_event`) push'ит unlocks в `state.unclaimed_unlocks` через `append_unclaimed` (dedupe по `(triumph_id, tier, kind)`).
3. На каждом tick'е `status_bar` показывает banner:
   ```
   🎁 N закрыто: имя1, имя2, имя3 (и ещё X) — открой [t]
   ```
4. Игрок открывает Triumphs menu → видит ✨ markers на категориях/triumph'ах с unclaimed → drill'ит в detail view → нажимает `[c] ✓ Собрать tier N (M ост.)`.
5. После claim: `🎉 Marathoner: Tier 1 собран! Score: 280 (ещё 2 осталось)` + одна entry удаляется из queue + persist + re-render обновляет label на следующий tier.

**Per-tier semantic (4.62.7.1 / 0.2.5z):** один клик = один tier (oldest first). Раньше (0.2.5u..0.2.5y) клик `[✓ Собрать (3)]` clear'ил все 3 tier'а одним batch'ем — заменено на per-tier для emotional payoff каждого acknowledgment (Destiny-2 style). Sort order для «oldest»: `unlocked_ts ASC, tier ASC` (если несколько tier'ов unlocked одним batch register_event — берётся меньший tier).

**Claimed tier counts в category labels (4.62.7.2/3 / 0.2.6):** category sub-collapsible label показывает **claimed tiers** (= `current_tier - unclaimed_count` per triumph, summed по категории) / total possible tiers. Marathoner tier 3/5 с 3 unclaimed → `🏃 Шаги · 0/5 ✨`. После claim_all → `3/5`. Реализовано в `_build_triumphs_view` (web) + `_category_counts` (CLI) — both consistent. Эволюция через 2 шага: (1) 4.62.7.2 сменил triumph count на tier count (`1/1` → `3/5`); (2) 4.62.7.3 уточнил — counter показывает **claimed** не **unlocked** (по user feedback «логичнее 0/5 пока не собрал»).

**Synth-backfill anti-loop + persist (4.62.4.1 fix / 0.2.6):** real-world incident — у Oleksii state.triumphs содержал 17 unlocked tier'ов но `unclaimed_unlocks` был пустой → banner никогда не появлялся. Root cause: `init_game_state` делал synth backfill в RAM, но **не persist'ил** → первый GET / web вызывал `try_reload_state.update_from_dict(Sheets)` который OVERRIDES RAM значением [] из Sheets → 17 entries silently теряются. Fix двойной:
- **Persist after init backfill** — `characteristics.init_game_state` если `synth_added > 0` → immediate `save_characteristic()` (silent-fail). Закрывает race.
- **Anti-loop marker** `state.triumphs['__synth_done__']['done']` ставится после первого `backfill_unclaimed_from_existing`. Backfill runs только если marker NOT set. Без него после user claim_all → следующий restart re-populates queue (infinite loop). С marker'ом — true one-shot, queue остаётся empty после первого claim_all.

**Batch claim:** в main menu отдельная кнопка `[a] ✓ Собрать все (N)` clear'ит весь queue (через `claim_all`) — для quick-clear при большом backfill (17 unlocks прокликивать по одному нудно).

**Backfill в unclaimed:**
- One-shot для existing players в `init_game_state` — `backfill_unclaimed_from_existing(state)` синтезирует entries для уже-unlocked tier'ов (только если queue пустая, чтобы не дублировать).
- Manual backfill через menu → `backfill_from_history` / `backfill_from_sheets_history` тоже append'ят newly-unlocked tier'ы в queue.

**Entry kinds:**
- `'triumph'` (default) — tier unlock конкретного triumph'а.
- `'seal'` — seal unlock категории. `triumph_id` = category key, `tier = 0` (unused).

**Engine API claim:**
- `claim_one_tier(state, id, kind='triumph') -> Optional[dict]` — per-tier, returns removed entry или None (since 0.2.5z, default UI path).
- `next_unclaimed_tier(state, id, kind='triumph') -> Optional[int]` — UI helper для button label.
- `claim_triumph(state, id, kind='triumph') -> int` — batch (all tiers for triumph), used by CLI [a] / future bulk operations (since 0.2.5u).
- `claim_all(state) -> int` — clear весь queue, used by banner [✓ Собрать всё].

Все методы фильтруют по `kind` — без него triumph 'foo' и seal 'foo' конфликтовали бы.

---

## 8. Seals & Titles (4.62.3)

- `SEALS` catalog в `triumphs_data.py` — один seal per category.
- При unlock последнего capstone'а → seal через `check_seal_unlocks` → в claim queue.
- После claim seal'а в Seals view игрок может **надеть title** (один за раз).
- Active title рендерится в `functions.status_bar` отдельной строкой `👑 <title>` над «Вы находитесь в локации».

UI access: `[s] 🏅 Seals & Titles` в Triumphs main menu → Seals view (текущий title + 5 seals со статусом UNLOCKED/LOCKED + Носить/Снять toggle).

---

## 9. Auto-hook architecture

Один common pattern — **avoid отдельных hook'ов в каждом mutation site**. Вместо `gym.skill_training`/`work.start_work`/etc дёргать триумфы явно, всё идёт через **существующий** `history.log_event`:

```python
# history.py:log_event
event = _build_event(event_type, payload)
_write_local(event)
_write_sheets(event)

# 4.62 auto-hook
try:
    from triumphs import register_event, append_unclaimed, check_seal_unlocks
    from characteristics import game
    if game.state is not None:
        unlocks = register_event(game.state, event_type, **payload)
        if unlocks:
            append_unclaimed(game.state, unlocks)
        seal_unlocks = check_seal_unlocks(game.state)
        if seal_unlocks:
            append_unclaimed(game.state, seal_unlocks)
except Exception:  # silent fail — triumph hook не должен ломать log_event
    pass
```

**Преимущество:** добавляя новый event-based triumph — НЕ нужно искать call site, нужно только убедиться что соответствующий `log_event(event_type, ...)` уже вызывается где надо. Если event'а нет — добавить вызов (как, например, было сделано для `forge.py:item_crafted` payload — добавили `cost_energy` в 0.2.5p для Energy triumph'ов).

Lazy imports + try/except чтобы избежать circular dependency.

---

## 9.5 Web UI architecture (4.62.7 / 0.2.5y, UX-polished 4.62.7.1 / 0.2.5z)

Параллельная вёрстка к CLI menu. 3 слоя UI в `web/templates/_status_fragment.html`:

**1. Top banners над Stats** (conditional render, всегда visible если active):
- **Unclaimed banner** `🎁 N закрытых не собрано` + sample names + `[✓ Собрать все]` button → POST `/web/triumphs/claim_all` (batch quick-clear).
- **Pinned banner** `📌 Pinned N/3` + 3 строки с progress bars (HTML5 `<progress>`) + ✨ marker если pinned имеет unclaimed.

**2. Title badge** в Stats header (`📊 Stats   👑 <title>` float-right) — visible если `state.title` non-None. Match с CLI placement над локацией.

**3. Main `<section id="triumphs">`** — **в самом конце dashboard'а после Inventory** (перемещена в 4.62.7.1 / 0.2.5z; до этого была между Gym и Bank — занимала прайм-real-estate выше gameplay-блоков). Collapsible `<details>`:
- Header: `🏆 Triumphs · Score: N · X/Y категорий · Z/M seals`
- 5 sub-collapsibles per category (🏃 / 🔋 / 🗺 / 🏋 / 🏭) с triumph rows внутри: name + 📌/✨ markers + progress bar + tier label + `[📌 Pin/Unpin]` + `[✓ Собрать tier N (M ост.)]` buttons (per-tier — см. ниже)
- Sub-collapsible `🏅 Seals & Titles` (5 seals со статусом UNLOCKED/LOCKED + `[Носить/Снять]` toggle для unlocked)
- `[🌐 Backfill из Sheets (cross-device)]` button внизу с `hx-confirm`

**Per-tier claim semantic (4.62.7.1 / 0.2.5z):** до 0.2.5z один клик на `[✓ Собрать (N)]` clear'ил все N unclaimed tier'ов одним batch'ем — это не давало emotional payoff per-tier. После polish:
- Button label: `[✓ Собрать tier N (M ост.)]` — показывает следующий oldest tier number + остаток.
- Один клик = один tier (oldest first by `unlocked_ts ASC, tier ASC`).
- После claim re-render обновляет label на next tier или убирает кнопку если queue для triumph'а пустой.
- `[a] Собрать всё` в banner остаётся как batch для quick-clear (через `claim_all`).
- Engine API: `claim_one_tier(state, id, kind) -> Optional[dict]` (returns removed entry или None), `next_unclaimed_tier(state, id, kind) -> Optional[int]` (UI label helper).

**Endpoints (10 total в `web/main.py`):** все mutation endpoints через `_validate_and_apply_*` helper'ы с STALE handling через `_persist_and_handle_stale`. Web endpoints возвращают `_render_dashboard_or_stale(...)` для HTMX swap. API mirrors возвращают JSON с Pydantic models (`TriumphPinRequest`, `TriumphClaimRequest`, `TriumphSealRequest`).

| Route | Что |
|---|---|
| `POST /web/triumphs/pin` + `/api/triumphs/pin` | Pin/Unpin toggle (form `triumph_id` / JSON `{triumph_id}`) |
| `POST /web/triumphs/claim` + `/api/triumphs/claim` | Claim one triumph's unclaimed entries (form/JSON `triumph_id`, `kind`) |
| `POST /web/triumphs/claim_all` + `/api/triumphs/claim_all` | Clear весь queue |
| `POST /web/triumphs/seal_toggle` + `/api/triumphs/seal_toggle` | Wear/take-off title (form/JSON `cat_key`) |
| `POST /web/triumphs/backfill_sheets` + `/api/triumphs/backfill_sheets` | Cross-device manual backfill |

**Pin cap UX:** при cap 3 кнопка Pin **disabled** + tooltip «Сначала открепи (3/3 pinned)». Smart-replace prompt **только в CLI** (modal в HTMX overkill для single user app). Server-side safety net в `_validate_and_apply_pin` — returns error если cap (UI должен предотвратить, но защита от direct API calls).

**Auto-claim flow:** клик `[✓ Собрать]` → POST → engine clears unclaimed entries → persist → HTMX swap `#status-bar` → re-render показывает обновлённый banner (или его отсутствие если queue пустой). Так же для seal_toggle — клик «Носить» → state.title = name → re-render badge в Stats header.

---

## 10. Pytest защита

`tests/conftest.py:_disable_triumphs_register_event_for_non_triumphs_tests` (autouse) → `triumphs.register_event` → `lambda state, type, **p: []` для всех тестов кроме `test_triumphs.py` / `test_triumphs_catalog.py`. Без этого fixture'а auto-hook срабатывал бы во всех integration тестах (web endpoint'ы / CLI flows) и мутировал `state.triumphs` лишними счётчиками → ломал fine-grained assertions.

---

## 11. Каталог triumph'ов (0.2.5v, 25.05.2026)

**Score system:** `POINTS_PER_TIER = 10`. Capstone = 10 × num_tiers points (50 для 5-tier triumph'а, 40 для 4-tier). Очки начисляются только за **собранные (claimed)** tier'ы (`total_score` = Σ `max(0, tier − unclaimed_count) × points_per`, 0.2.6 fix) — несобранные unlock'и сидят в queue и дают 0 очков.

**Total: 47 triumph'ов в 7 категориях, 7 seals** (с 0.2.5w +1 Iron Worker в Work; с 0.2.6 +1 Veteran в Progression ⭐ + seal Veteran; +6 Drops 💎 — Collector + 5 per-grade, seal Treasure Hunter). NB: тиры Veteran 15-30 пока недостижимы — level-кэп = 12, расширение в TASKS 4.64 (отложено). Drops: event-based на `[drop, drop_pending, drop_force_sold]` с grade-фильтром, tiers 10/50/100/250/500/1000.

### 🏃 Steps (1) — 4.62.1.1 / 0.2.5m

| ID | Name | Tiers | Tracking | Metric / Hook |
|---|---|---|---|---|
| `marathoner` | Marathoner | `[100k, 500k, 1M, 5M, 10M]` | metric | `state.steps.total_used` |

**Seal:** Marathoner.

### 🔋 Energy (4) — 4.62.1.4 / 0.2.5p

Approach B (event-based через `cost_energy` в payload existing log_event'ов). Все 4 имеют одинаковые tiers `[1k, 5k, 10k, 50k]`.

| ID | Name | Hooks | Filter |
|---|---|---|---|
| `endurance` | Endurance | work_start, work_extend, skill_train_start, adventure_start, item_repaired, item_crafted | — |
| `workhorse` | Workhorse | work_start, work_extend | — |
| `disciplined` | Disciplined | skill_train_start | — |
| `pathfinder` | Pathfinder | adventure_start | — |

`count_delta = lambda p: int(p.get('cost_energy', 0))` для всех.

**Seal:** Indefatigable.

### 🗺 Adventures (8) — 4.62.1.2 + 4.62.1.3 / 0.2.5q

Metric-based через `state.adventure.counters` (counters обновляются в `Adventure.adventure_check_done`). Все 8 имеют одинаковые tiers `[10, 50, 100, 500, 1000]`.

| ID | Name | Metric |
|---|---|---|
| `adventurer` | Adventurer | `sum(state.adventure.counters.values())` |
| `stroller` | Stroller | `counters.get('walk_easy', 0)` |
| `hiker` | Hiker | `counters.get('walk_normal', 0)` |
| `trekker` | Trekker | `counters.get('walk_hard', 0)` |
| `roamer` | Roamer | `counters.get('walk_15k', 0)` |
| `voyager` | Voyager | `counters.get('walk_20k', 0)` |
| `explorer` | Explorer | `counters.get('walk_25k', 0)` |
| `conqueror` | Conqueror | `counters.get('walk_30k', 0)` |

**Seal:** Globetrotter.

### 🏋 Gym / Skill Mastery (21) — 4.62.1.6 / 0.2.5s

Metric-based через `state.gym.<field>`. Per-skill tiers `[10, 15, 20, 25, 30]`, aggregate Skill Master tiers `[50, 100, 250, 500, 1000]`.

20 per-skill triumph'ов (id = field name из `state.GymSkills`, name = title из `_GYM_SKILL_DISPLAY` в `web/main.py`):

| ID | Name | ID | Name |
|---|---|---|---|
| `stamina` | Stamina | `money_saving` | Экономия денег |
| `energy_max_skill` | Energy Max | `earnings_boost` | Бонус к зарплате |
| `energy_regen_skill` | Регенерация энергии | `trader` | Торговец |
| `speed_skill` | Speed | `banking_interest_rate` | Банковская ставка |
| `luck_skill` | Luck | `loan_capacity` | Кредитный лимит |
| `move_optimization_adventure` | Move Optimization (Adventure) | `loan_interest_reduction` | Снижение ставки по кредиту |
| `move_optimization_gym` | Move Optimization (Gym) | `inspiration` | Обучение |
| `move_optimization_work` | Move Optimization (Work) | `backpack_skill` | Размер инвентаря |
| `energy_optimization_adventure` | Экономия энергии в Adventure | `neatness_in_using_things` | Neatness |
| `energy_optimization_gym` | Экономия энергии в Gym | | |
| `energy_optimization_work` | Экономия энергии в Work | | |

`metric: lambda s: s.gym.<field>` для каждого.

Plus 1 aggregate:

| ID | Name | Metric |
|---|---|---|
| `skill_master` | Skill Master | `sum(getattr(s.gym, f) for f in _GYM_SKILL_FIELDS)` (20 fields) |

Legacy fields `mechanics` / `it_technologies` из `GymSkills` намеренно исключены — не trainable через Gym menu.

**Seal:** Polymath.

### 🏭 Work (6) — 4.62.1.5 / 0.2.5t + 4.62.1.5.1 / 0.2.5w

Event-based через `work_done` payload (`vacancy + hours`). Все 5 имеют одинаковые tiers `[100, 500, 1000, 5000, 10000]`.

| ID | Name | Hooks | Filter |
|---|---|---|---|
| `hard_worker` | Hard Worker | work_done | — |
| `watchman` | Сторож | work_done | `payload['vacancy'] == 'watchman'` |
| `factory` | Заводчанин | work_done | `payload['vacancy'] == 'factory'` |
| `courier_foot` | Курьер | work_done | `payload['vacancy'] == 'courier_foot'` |
| `forwarder` | Экспедитор | work_done | `payload['vacancy'] == 'forwarder'` |

`count_delta = lambda p: int(p.get('hours', 0))` для всех. **Tracking semantics:** счётчик растёт на **завершении** смены (`work_done` event, который fire'ит auto-finalize в `work.py:work_check_done`), не на старте. Симметрично с Energy: Workhorse/Endurance hook'аются на старт (энергия в момент траты = факт), Hard Worker — на финиш (часы — accumulator за время смены). Активная смена в RAM не учитывается до finalize.

Plus 1 metric-based (4.62.1.5.1 / 0.2.5w):

| ID | Name | Tiers | Metric |
|---|---|---|---|
| `iron_worker` | Iron Worker | `[24, 72, 168, 336, 720]` (1сут/3дн/1нед/2нед/**1 месяц**) | `state.work.longest_shift_hours` |

**Iron Worker semantics — unique в catalog'е** (единственный max-tracking triumph). Поле `state.work.longest_shift_hours` обновляется в `work.py:work_check_done` ПЕРЕД log_event: `state.work.longest_shift_hours = max(current, finished_hours)`. Backfill для existing players через `characteristics._backfill_longest_shift_from_history` — scan local jsonl для `max(payload['hours'])` из work_done events (one-shot, запускается только если field == 0). Cross-device limitation: только local jsonl, см. 4.62.6.

**Seal:** Workaholic.

---

## 12. Как добавить новый triumph (recipe)

### Metric-based (счётчик уже в state)

Простейший случай. Backfill не нужен — auto-unlock через `init_metric_check`.

1. Открыть `triumphs_data.py:TRIUMPHS`, добавить entry:
   ```python
   'veteran': {
       'name': 'Veteran',
       'category': 'progression',  # должна быть в CATEGORIES
       'tiers': [5, 10, 25, 50, 100],
       'metric': lambda state: state.char_level.level,
   },
   ```
2. Тесты в `tests/test_triumphs_catalog.py::TestVeteran` (см. existing для образца).
3. Bump version + changelog.

### Event-based (нужен новый счётчик / событие)

1. Убедиться что нужный `log_event(event_type, **payload)` уже fire'ится где надо. Если нет — добавить вызов в соответствующую mutation function.
2. Если payload не содержит нужный numeric field (например `hours`/`cost_energy`/etc) — добавить его в payload в call site.
3. Добавить entry в `TRIUMPHS`:
   ```python
   'investor': {
       'name': 'Investor',
       'category': 'money',
       'tiers': [1_000, 10_000, 100_000, 1_000_000],
       'event_hooks': ['gym_payment'],  # тип события
       'count_delta': lambda p: int(p.get('amount', 0) or 0),
   },
   ```
4. Опционально `event_filter` если триумф учитывает подмножество events.
5. Тесты — accumulator correctness, tier unlock, capstone.
6. **Backfill:** если payload format стабилен — `backfill_from_history` автоматически подберёт events из старой `history.jsonl`.

### Max-tracking semantic (один-в-один как Iron Worker)

Engine не поддерживает `count_mode='max'` напрямую — `count_delta` лямбда всегда **adds**. Для триумфов «максимум одного события» (longest shift, biggest drop, highest streak в один день) использовать гибрид «metric + hook»:

1. Добавить новое state-поле для max-tracker'а:
   ```python
   # state.py — внутри подходящего dataclass
   biggest_drop_value: int = 0
   ```
2. Round-trip через flat-key в `from_dict` / `to_dict` (default 0 для legacy).
3. **Hook в mutation function** — обновлять max перед log_event чтобы register_event сразу увидел fresh value:
   ```python
   # drop.py:Drop_Item.item_collect (например)
   if drop.price > state.work.biggest_drop_value:
       state.biggest_drop_value = drop.price
   log_event('drop', item=drop, ...)
   ```
4. Triumph entry — metric-based:
   ```python
   'collector_king': {
       'name': 'Collector King',
       'category': 'drops',
       'tiers': [100, 500, 1000, 5000],
       'metric': lambda s: s.biggest_drop_value,
   },
   ```
5. **One-shot backfill для existing players** — helper в `characteristics.py` который scan'ит `history.jsonl` для `max(payload[field])` из соответствующих events. Запускается в `init_game_state` only-if `field == 0`. См. `_backfill_longest_shift_from_history` как референс.
6. Тесты + changelog.

### Новая категория

1. Добавить в `triumphs_data.py:CATEGORIES`:
   ```python
   'progression': {'label': '⭐ Уровень', 'order': 7},
   ```
2. Опционально seal в `SEALS`:
   ```python
   'progression': {'name': 'Veteran', 'icon': '⭐'},
   ```
3. Тесты + changelog.

### Что **НЕ нужно** менять при добавлении нового triumph'а / категории

- **CLI menu** — `triumphs_menu.py` читает catalog dynamically (через `TRIUMPHS.items()` + `CATEGORIES.keys()`). Новый triumph автоматически появится в category view, новая категория — в main menu.
- **Web UI** (`web/main.py:_build_triumphs_view` + template) — те же dynamic patterns. Новые entries автоматически рендерятся в banners / main section / Seals. Pin/Unpin/Claim buttons работают через generic endpoints.
- **State schema** — `state.triumphs` это dict[str, dict] — новые ID просто добавляют entry на первом progress.
- **Auto-hook** — `history.log_event` уже всё подключено через `register_event`/`check_seal_unlocks`.

То есть для metric-based triumph: один edit в `triumphs_data.py:TRIUMPHS` + тесты = done. Для event-based: + проверить что нужный `log_event` уже вызывается. **Это by-design simplicity** — система спроектирована для быстрого расширения caталога без touchpoint'ов в UI или mutation modules.

---

## 13. Связанные документы

- [`TASKS.md`](../TASKS.md) — секция «4.62. Triumphs» с полным breakdown подзадач (Phase 1-6, 23 granular tasks).
- [`CLAUDE.md`](../CLAUDE.md) — module map entry `triumphs.py + triumphs_data.py + triumphs_menu.py` с архитектурным overview.
- [`changelog.txt`](../changelog.txt) — версии 0.2.5j..0.2.6 содержат подробное описание каждого этапа имплементации (foundation 0.2.5j-l, catalog 0.2.5m-t + 0.2.5w Iron Worker, pinned 0.2.5u, seals 0.2.5v, backfill UX 0.2.5x, web UI 0.2.5y, per-tier claim + section move 0.2.5z, **0.2.6:** UX polish + critical synth-backfill fix + claimed tier counts).

---

## 14. Будущие фазы (см. TASKS.md)

| Phase | Что | Status |
|---|---|---|
| **2 Catalog (cont.)** | 8 категорий ещё не реализованы: Drops / Forge / Bank / Streak / Level / Money / Lifestyle / Collection | todo |
| **4.62.2.1 Bonuses** | Gameplay-эффекты на capstones (Marathoner 10M → +5% Stamina, Hard Worker 10k → +5% ЗП, и т.п.) | **deferred** — отложено до balance design (25.05.2026) |
| **4.62.2.2 Active rewards** | Active abilities (Lucky Day, Streak Saver, Premium Shift) | blocked by 4.58 |
| **4.62.5 Hidden** | `???` маска до unlock'а — surprise discovery | optional |
| **4.62.6 Backfill UX** | `[b]` Sheets `history` cross-device + auto-fallback на local jsonl | **done (0.2.5x)** |
| **4.62.7 Web UI** | Web section для Triumphs + pinned banner + title badge + 10 endpoints | **done (0.2.5y)** |
| **4.62.7.1 Web UX polish** | Per-tier claim (один клик = один tier oldest first) + section move в конец dashboard'а | **done (0.2.5z)** |
| **4.62.7.2/3 Category labels** | Claimed tier counts (`3/5` вместо `1/1`); growing по мере claim'ов | **done (0.2.6)** |
| **4.62.4.1 Synth-backfill fix** | Persist after init + anti-loop flag — fix critical race где 17 backfilled entries silently терялись на первом GET / | **done (0.2.6)** |
