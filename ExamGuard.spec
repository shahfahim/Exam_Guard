# ExamGuard.spec — PyInstaller Build Specification
# ExamGuard v4.0.0 | https://github.com/shahfahim/Exam_Guard
#
# Build with:
#   pyinstaller ExamGuard.spec --noconfirm --clean
#
# Output: dist/ExamGuard/ExamGuard.exe  (one-folder mode)

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# ── Collect customtkinter themes and assets ───────────────────────────────────
ctk_datas = collect_data_files("customtkinter")

# ── Hidden imports needed for Windows GUI + monitoring ────────────────────────
hidden = [
    # CustomTkinter
    "customtkinter",
    "customtkinter.windows",
    "customtkinter.windows.widgets",
    # Pillow
    "PIL._tkinter_finder",
    "PIL.Image",
    "PIL.ImageTk",
    "PIL.ImageGrab",
    # pynput — Windows backends loaded dynamically
    "pynput",
    "pynput.keyboard",
    "pynput.keyboard._win32",
    "pynput.keyboard._base",
    "pynput.mouse",
    "pynput.mouse._win32",
    "pynput.mouse._base",
    # pywin32
    "win32api",
    "win32con",
    "win32gui",
    "win32process",
    "win32security",
    "win32event",
    "winerror",
    "pywintypes",
    "winreg",
    # pygetwindow
    "pygetwindow",
    "pygetwindow._pygetwindow_win",
    # psutil
    "psutil",
    "psutil._pswindows",
    # watchdog
    "watchdog",
    "watchdog.observers",
    "watchdog.observers.winapi",
    "watchdog.events",
    # cryptography
    "cryptography",
    "cryptography.hazmat.primitives.ciphers",
    "cryptography.hazmat.primitives.hashes",
    "cryptography.hazmat.backends",
    "cryptography.fernet",
    # pyperclip
    "pyperclip",
    "pyperclip.handlers",
    # sqlite3 (bundled with Python, sometimes missed)
    "sqlite3",
    "_sqlite3",
    # ExamGuard modules
    "update_checker",
    "version",
    "app",
    "app.paths",
    # Standard lib that PyInstaller sometimes misses
    "pkg_resources",
    "packaging",
    "packaging.version",
    "packaging.specifiers",
    "packaging.requirements",
]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=ctk_datas + [
        # Bundle the icon so the app can reference it at runtime
        ("installer/assets/examguard.ico", "."),
    ],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Trim unused large packages
        "matplotlib",
        "numpy",
        "scipy",
        "pandas",
        "IPython",
        "notebook",
        "test",
        "tkinter.test",
        "unittest",
    ],
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
    name="ExamGuard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,                    # No black console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="installer/assets/examguard.ico",
    version="file_version_info.txt",  # Embeds Windows VERSIONINFO resource
    uac_admin=False,                  # Runtime does NOT need admin
    manifest=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[
        # Don't UPX these — known to cause issues
        "vcruntime140.dll",
        "python3*.dll",
        "tk*.dll",
        "tcl*.dll",
    ],
    name="ExamGuard",                 # → dist/ExamGuard/
)
