# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['can_app.py'],
    pathex=[],
    binaries=[('libs/Win64/libusb-1.0.dll', '.')],
    datas=[('CAN_Logo.png', '.')],
    hiddenimports=['openpyxl.cell._writer'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'scipy', 'pandas', 'numpy.py'],
    noarchive=False,
    optimize=0,
)

### Remove unused binaries ###
to_keep_bin = []
to_exclude_bin = {'opengl32sw.dll',
    'd3dcompiler_47.dll',
    'Qt5DBus.dll',
    'Qt5Qml.dll',
    'Qt5Quick.dll',
    'libGLESv2.dll',
    'Qt5Network.dll',
    'Qt5QmlModels.dll',
    'Qt5Qml.dll',
    'qwebp.dll',
    'qtiff.dll'
}

for (dest, source, kind) in a.binaries:
    if os.path.split(dest)[1] in to_exclude_bin:
        continue
    to_keep_bin.append((dest, source, kind))
a.binaries = to_keep_bin

### Remove language translations files ###
to_keep_data = []
for (dest, source, kind) in a.datas:
    if "translations\\qt" not in dest:
        to_keep_data.append((dest, source, kind))
a.datas = to_keep_data

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CanBusApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['CAN_Logo.png'],
)
