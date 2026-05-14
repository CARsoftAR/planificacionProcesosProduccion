# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['desktop_run.py'],
    pathex=[],
    binaries=[],
    datas=[('planificacion', 'planificacion'), ('produccion/templates', 'produccion/templates'), ('produccion/static', 'produccion/static'), ('db.sqlite3', '.')],
    hiddenimports=['webview', 'webview.platforms.winforms', 'django', 'django.core.management', 'django.db.backends.sqlite3', 'produccion'],
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
    [],
    exclude_binaries=True,
    name='ABBAMAT_PROD_Desktop',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ABBAMAT_PROD_Desktop',
)
