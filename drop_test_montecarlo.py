"""Monte-Carlo симулятор drop-механики на реальном `Drop_Item`.

Standalone скрипт — запускается как `python drop_test_montecarlo.py`.

В отличие от старой версии (до 3.2.2 — локальная fork-копия Drop_Item с
другими процентами / другим набором типов / без walk_20k), теперь
используется реальный `Drop_Item.one_item_random_grade(hard, state)` из
`drop.py`. Это значит измерения соответствуют **актуальному балансу игры**
и пригодны для тюнинга `drop_percent_*` констант.

Вариант B (TASKS 3.2.2): мерим только распределение grade'ов через
`one_item_random_grade` — без полного `item_collect` (который печатает в
stdout и аппендит в `state.inventory`). Если когда-то потребуется
распределение по item_type / characteristic / quality — это отдельный
проход / отдельная функция.

Прогон: 5 значений luck × 7 difficulties × 10 000 итераций = 350 000
вызовов `one_item_random_grade`. Время на M1 ~5-10 секунд.
"""

from drop import Drop_Item
from state import GameState


DIFFICULTIES = [
    'walk_easy',
    'walk_normal',
    'walk_hard',
    'walk_15k',
    'walk_20k',
    'walk_25k',
    'walk_30k',
]
LUCK_VALUES = [0, 5, 10, 20, 30]
ITERATIONS = 10_000
GRADES = ['c-grade', 'b-grade', 'a-grade', 's-grade', 's+grade', 'none']


def run_simulation(luck_value: int) -> dict:
    """Прогоняет 10k итераций по каждой difficulty при заданном luck.

    Возвращает `{difficulty: {grade: count}}`. `none` — попытки, в которых
    `one_item_random_grade` вернула None (ничего не выпало).
    """
    state = GameState.default_new_game()
    state.gym.luck_skill = luck_value

    drop_item = Drop_Item()
    results = {d: {g: 0 for g in GRADES} for d in DIFFICULTIES}

    for difficulty in DIFFICULTIES:
        for _ in range(ITERATIONS):
            grade = drop_item.one_item_random_grade(difficulty, state)
            key = grade if grade in GRADES else 'none'
            results[difficulty][key] += 1

    return results


def format_table(luck_value: int, results: dict) -> str:
    """Текстовая таблица распределения grade'ов для одного luck-значения."""
    lines = [f"\n=== Luck = {luck_value} ({ITERATIONS:,} итераций × {len(DIFFICULTIES)} difficulties) ===\n"]
    header = f"{'difficulty':<12}" + "".join(f"{g:>10}" for g in GRADES)
    lines.append(header)
    lines.append("-" * len(header))
    for difficulty in DIFFICULTIES:
        row_data = results[difficulty]
        cells = []
        for grade in GRADES:
            count = row_data[grade]
            pct = count / ITERATIONS * 100
            cells.append(f"{pct:>9.2f}%")
        lines.append(f"{difficulty:<12}" + "".join(cells))
    return "\n".join(lines)


def main():
    print(f"Drop Monte-Carlo: luck × difficulty × grade ({ITERATIONS:,} iter / cell)")
    for luck_value in LUCK_VALUES:
        results = run_simulation(luck_value)
        print(format_table(luck_value, results))
    print()


if __name__ == "__main__":
    main()
