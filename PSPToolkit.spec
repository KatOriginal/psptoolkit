# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:/Users/katki/Desktop/psptoolkit/main.py'],
    pathex=['C:/Users/katki/Desktop/psptoolkit'],
    binaries=[],
    datas=[],
    hiddenimports=['core', 'core.ps1_builder', 'core.iso_rebuilder', 'formats', 'formats.sfo', 'formats.iso', 'formats.cso', 'formats.pbp', 'formats.cue', 'gui', 'gui.widgets'],
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
    name='PSPToolkit',
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
)
