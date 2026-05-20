"""One-shot backup script — экспорт текущего game_state листа Sheets в .json
файл ДО deploy миграции 1.4.3 (JSON-blob layout).

Safety net на случай если автоматическая миграция Key/Value → JSON-blob
сломается на первом save после deploy. Backup можно прочитать через
`json.load()` и при необходимости вручную восстановить любое поле.

Запуск:
    python scripts/backup_sheets_before_migration.py

Создаёт файл `backup_before_1.4.3_YYYYMMDD_HHMMSS.json` в текущей директории.
Структура файла — flat-dict (тот же что `state.to_dict()` отдаёт).

Удалить файл / скрипт можно после успешного 1-2-недельного bake-test'а
новой схемы (вместе с задачей 1.4.3.1 Legacy cleanup).
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Скрипт лежит в scripts/, нужен root проекта в sys.path для импортов.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _json_default(obj: object) -> object:
    """Сериализация datetime / прочих non-JSON типов в строки."""
    if isinstance(obj, datetime):
        return obj.strftime('%Y-%m-%d %H:%M:%S.%f')
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def main() -> None:
    from google_sheets_db import GameStateRepo

    print('Loading game_state from Sheets...')
    repo = GameStateRepo()
    data = repo.load()
    if not data:
        print('⚠️ Sheets game_state пуст — нечего backup-ить.')
        sys.exit(1)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = Path(f'backup_before_1.4.3_{timestamp}.json')
    out_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=_json_default),
        encoding='utf-8',
    )
    print(f'✅ Backup сохранён: {out_path.resolve()}')
    print(f'   Размер: {out_path.stat().st_size:,} bytes')
    print(f'   Ключей: {len(data)}')


if __name__ == '__main__':
    main()
