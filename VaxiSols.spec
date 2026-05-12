# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Bundled non-code assets (do not embed config/default.json — may contain secrets)
datas = [
    ("ui", "ui"),
    ("VaxiSolsIcon_transparent.png", "."),
    ("VaxiSolsIcon.png", "."),
    ("VaxiSolsIcon.ico", "."),
    ("config/resolution_profiles.json", "config"),
]

binaries = []
hiddenimports = [
    "webview",
    "json",
    "threading",
    "asyncio",
    "pathlib",
    "time",
    "ctypes",
    "ctypes.wintypes",
    "psutil",
    "PIL",
    "PIL.Image",
    "numpy",
    "cv2",
    "onnxruntime",
    "rapidocr_onnxruntime",
    "pytesseract",
    "tkinter",
    "tkinter.filedialog",
    "tkinter.messagebox",
]

# RapidOCR ships ONNX models + pulls onnxruntime where needed; avoid collect_all(onnxruntime)
# (pulls huge optional transformer tooling).
pkg_datas, pkg_binaries, pkg_hidden = collect_all("rapidocr_onnxruntime")
datas += pkg_datas
binaries += pkg_binaries
hiddenimports += pkg_hidden

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="VaxiSols",
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
    icon="VaxiSolsIcon.ico",
)
