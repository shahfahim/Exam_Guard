# app/paths.py — ExamGuard Runtime Path Resolution
#
# Provides correct paths whether running:
#   - From source:        python main.py
#   - As frozen bundle:   ExamGuard.exe  (PyInstaller)
#
# All user data lives under %APPDATA%\ExamGuard\ so it survives
# app updates and never requires admin access at runtime.

import os
import sys


def _appdata_root() -> str:
    """Return %APPDATA%\\ExamGuard, creating it if it doesn't exist."""
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
    path = os.path.join(base, "ExamGuard")
    os.makedirs(path, exist_ok=True)
    return path


def get_appdata_dir() -> str:
    """Return the root ExamGuard user-data directory."""
    return _appdata_root()


def get_db_path() -> str:
    """Return the full path to the SQLite database file."""
    return os.path.join(_appdata_root(), "examguard.db")


def get_vault_dir() -> str:
    """Return the encrypted screenshot vault directory."""
    path = os.path.join(_appdata_root(), ".vault")
    os.makedirs(path, exist_ok=True)
    return path


def get_screenshots_dir() -> str:
    """Return the screenshots directory."""
    path = os.path.join(_appdata_root(), "screenshots")
    os.makedirs(path, exist_ok=True)
    return path


def get_logs_dir() -> str:
    """Return the logs directory."""
    path = os.path.join(_appdata_root(), "logs")
    os.makedirs(path, exist_ok=True)
    return path


def get_install_dir() -> str:
    """
    Return the directory where the app binary/scripts live.
    - Frozen (PyInstaller one-folder): directory of ExamGuard.exe
    - Source:                          project root
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_resource_path(relative_path: str) -> str:
    """
    Resolve a path to a bundled resource file.
    PyInstaller extracts resources to sys._MEIPASS; from source, use project root.
    """
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)
