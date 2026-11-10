# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

ROOT = Path(SPECPATH).resolve()

a = Analysis(
    [str(ROOT / "AutoClicker.py")],
    pathex=[str(ROOT)],
    binaries=[
        (str(ROOT / "tk-data" / "tcl86t.dll"), "."),
        (str(ROOT / "tk-data" / "tk86t.dll"), "."),
        (str(__import__("imageio_ffmpeg").get_ffmpeg_exe()), "."),
    ],
    datas=[
        (str(ROOT / "ikon.ico"), "."),
        (str(ROOT / "background_ui.png"), "."),
        (str(ROOT / "tk-data" / "_tcl_data"), "_tcl_data"),
        (str(ROOT / "tk-data" / "_tk_data"), "_tk_data"),
    ],
    hiddenimports=["tkinter", "_tkinter"],
    hookspath=[str(ROOT / "hooks")],
    hooksconfig={},
    runtime_hooks=[str(ROOT / "tk_runtime_hook.py")],
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
    name="AutoClicker",
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
    icon=str(ROOT / "ikon.ico"),
)
