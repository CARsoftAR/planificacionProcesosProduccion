# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

import os

spec_dir = os.path.abspath(os.getcwd())

datas_list = [
    (os.path.join(spec_dir, 'planificacion'), 'planificacion'),
    (os.path.join(spec_dir, 'db.sqlite3'), '.'),
]

for src_rel, dst in [('produccion/templates', 'produccion/templates'), ('produccion/static', 'produccion/static')]:
    src_abs = os.path.join(spec_dir, src_rel)
    os.makedirs(src_abs, exist_ok=True)
    datas_list.append((src_abs, dst))

a = Analysis(
    ['desktop_run.py'],
    pathex=[],
    binaries=[],
    datas=datas_list,
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
