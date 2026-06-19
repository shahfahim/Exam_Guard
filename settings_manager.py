# settings_manager.py — ExamGuard v3 — Runtime Settings

"""
Persists instructor-configurable settings to a JSON file in AppData.
All modules should call settings_manager.get() instead of reading
config.py constants directly for any user-changeable value.
"""

import json
import os
import threading

_SETTINGS_DIR  = os.path.join(os.environ.get("APPDATA", "."), "ExamGuard")
_SETTINGS_FILE = os.path.join(_SETTINGS_DIR, "settings.json")
_lock          = threading.Lock()
_cache: dict | None = None

# ── Defaults ──────────────────────────────────────────────────
DEFAULTS: dict = {
    # Auth
    "instructor_pin":        "1234",

    # Risk thresholds
    "risk_green_max":        20,
    "risk_yellow_max":       50,
    "risk_lock_threshold":   150,

    # Risk weights
    "risk_w_window":         3,
    "risk_w_clipboard":      8,
    "risk_w_file_copy":      15,
    "risk_w_usb_insert":     25,
    "risk_w_file_access":    10,
    "risk_w_ide_preexist":   20,
    "risk_w_idle":           10,

    # Screenshot triggers (bool)
    "screenshot_on_browser":   True,
    "screenshot_on_usb":       True,
    "screenshot_on_clipboard": True,
    "screenshot_on_file_copy": True,
    "screenshot_on_file_access": True,

    # Intervals (seconds)
    "window_check_interval":    0.5,
    "clipboard_check_interval": 1.0,
    "usb_check_interval":       1.5,
}


# ── Public API ────────────────────────────────────────────────

def load() -> dict:
    """Return a copy of the current settings (loads from disk if needed)."""
    global _cache
    with _lock:
        if _cache is None:
            _cache = _load_from_disk()
        return dict(_cache)


def save(settings: dict):
    """Merge settings with defaults and persist to disk."""
    global _cache
    os.makedirs(_SETTINGS_DIR, exist_ok=True)
    with _lock:
        merged = {**DEFAULTS, **settings}
        _cache = merged
        try:
            with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(merged, f, indent=2)
        except Exception as e:
            print(f"[Settings] Could not save: {e}")


def get(key: str, default=None):
    """Get a single setting value."""
    return load().get(key, DEFAULTS.get(key, default))


def set_value(key: str, value):
    """Update a single setting and persist."""
    s = load()
    s[key] = value
    save(s)


def reset():
    """Reset all settings to defaults."""
    save(dict(DEFAULTS))


# ── Internal ──────────────────────────────────────────────────

def _load_from_disk() -> dict:
    if os.path.exists(_SETTINGS_FILE):
        try:
            with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {**DEFAULTS, **data}   # new keys get defaults
        except Exception as e:
            print(f"[Settings] Could not read settings file: {e}")
    return dict(DEFAULTS)
