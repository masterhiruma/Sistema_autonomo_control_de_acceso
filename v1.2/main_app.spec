# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main_app.py'],
    pathex=[],
    binaries=[],
    datas=[('encodings_faciales.pkl', '.'), ('rostros_conocidos', 'rostros_conocidos'), ('reportes_acceso', 'reportes_acceso')],
    hiddenimports=['cv2', 'face_recognition', 'pyzbar', 'numpy', 'tkinter', 'PIL', 'serial', 'json', 'datetime', 'threading', 'time'],
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
    name='main_app',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
