# game.spec
# Пример использования PyInstaller с Kivy-приложением

# Импортируйте нужные библиотеки
from kivy.deps import sdl2, glew
from kivy import require
import os

# Настройки PyInstaller
a = Analysis(
    ['game.py'],
    pathex=['.'],
    binaries=[(sdl2, 'kivy/deps/sdl2'), (glew, 'kivy/deps/glew')],
    datas=[('icons/2walks.ico', 'icons/2walks.ico')],
    hiddenimports=['kivy.core.text', 'kivy.core.window'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[]
)

pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='game', debug=False, bootloader_ignore_signals=False, strip=False, upx=True, console=False)
