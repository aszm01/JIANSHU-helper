# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['keyboard_mouse_viz.py'],
    pathex=[],
    binaries=[],
    datas=[('初始.png', '.'), ('键鼠.svg', '.'), ('fa-solid-900.ttf', '.')],
    hiddenimports=['resvg_py'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='录屏键鼠助手',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='logo.ico',
)
