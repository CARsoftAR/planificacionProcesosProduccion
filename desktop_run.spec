# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['desktop_run.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('planificacion', 'planificacion'),
        ('produccion/templates', 'produccion/templates'),
        ('produccion/static', 'produccion/static'),
        ('db.sqlite3', '.'),
    ],
    hiddenimports=[
        'clr',
        'pythonnet',
        'webview',
        'webview.platforms.winforms',
        'openpyxl',
        'clr_loader',
        'django.core.management',
        'django.db.backends.sqlite3',
        'produccion',
        'planificacion.settings',
        'planificacion.urls',
        'planificacion.wsgi',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

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
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ABBAMAT_PROD_Desktop',
)
