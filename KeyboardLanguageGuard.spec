# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

wordfreq_data, wordfreq_bins, wordfreq_hidden = collect_all('wordfreq')

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=wordfreq_bins,
    datas=wordfreq_data,
    hiddenimports=wordfreq_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Keyboard Language Guard',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
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
    name='Keyboard Language Guard',
)

app = BUNDLE(
    coll,
    name='Keyboard Language Guard.app',
    icon=None,
    bundle_identifier='com.keyboardlanguageguard.app',
    version='0.5.0',
    info_plist={
        'CFBundleDisplayName': 'Keyboard Language Guard',
        'CFBundleShortVersionString': '0.5.0',
        'CFBundleVersion': '5',
        'LSUIElement': True,
        'NSHumanReadableCopyright': 'Keyboard Language Guard',
    },
)
