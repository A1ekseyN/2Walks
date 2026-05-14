"""Генерация apple-touch-icon.png из эмодзи 🏃 для web (4.48).

Одноразовый dev-скрипт — не вызывается в runtime. Готовый PNG-файл
закоммичен в `web/static/apple-touch-icon.png`, так что обычно скрипт
не нужен. Перегенерация требуется только если меняем эмодзи или размер.

Pillow намеренно НЕ включён в requirements-dev.txt — это разовая
зависимость для регенерации, держать её в постоянных deps смысла нет.

Pre-requisites (одноразово, только при регенерации):
    source .venv/bin/activate
    pip install 'Pillow>=10.0'
    python scripts/generate_favicon.py
    pip uninstall Pillow -y  # вернуть venv к чистому состоянию

Требования к системе:
- macOS — использует системный шрифт Apple Color Emoji
  (`/System/Library/Fonts/Apple Color Emoji.ttc`) для color emoji rendering.
  На Linux / Windows нужен альтернативный шрифт
  (Noto Color Emoji / Segoe UI Emoji) — отредактировать FONT_PATH.
- Pillow >= 10.0 — поддержка `embedded_color=True` для color emoji.
"""

import os

from PIL import Image, ImageDraw, ImageFont


SIZE = 180  # apple-touch-icon рекомендованный размер iOS
EMOJI = '🏃'
OUTPUT = 'web/static/apple-touch-icon.png'

# macOS Apple Color Emoji — единственный системный шрифт с цветными эмодзи.
# На Linux/Windows этот скрипт не запустится без альтернативного шрифта
# (например, Noto Color Emoji / Segoe UI Emoji).
FONT_PATH = '/System/Library/Fonts/Apple Color Emoji.ttc'

# Apple Color Emoji содержит фиксированные размеры PNG-bitmap'ов:
# 20, 32, 40, 48, 64, 96, 160. Берём ближайший к нашему SIZE сверху.
FONT_SIZE = 160


def generate() -> None:
    img = Image.new('RGBA', (SIZE, SIZE), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT_PATH, size=FONT_SIZE)

    # Центрируем эмодзи по bbox (учитывает асимметрию глифа).
    bbox = font.getbbox(EMOJI)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (SIZE - text_w) // 2 - bbox[0]
    y = (SIZE - text_h) // 2 - bbox[1]

    draw.text((x, y), EMOJI, font=font, embedded_color=True)

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    img.save(OUTPUT, 'PNG')
    print(f'✓ Сохранено: {OUTPUT} ({SIZE}×{SIZE}px, эмодзи: {EMOJI})')


if __name__ == '__main__':
    generate()
