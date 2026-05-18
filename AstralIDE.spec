# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:\\computer\\documents\\coding\\python_projects\\astral_lang\\astral_ide.py'],
    pathex=['D:\\computer\\documents\\coding\\python_projects\\astral_lang'],
    binaries=[],
    datas=[],
    hiddenimports=[],
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
    name='AstralIDE',
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
    version='D:\\computer\\documents\\coding\\python_projects\\astral_lang\\version_info.txt',
    icon=['D:\\computer\\documents\\coding\\python_projects\\astral_lang\\assets\\icons\\astral.ico'],
)
