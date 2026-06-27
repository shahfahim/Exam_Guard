# settings_manager.py — ExamGuard v4.1 — Runtime Settings

"""
Persists instructor-configurable settings to a JSON file in AppData.
All modules should call settings_manager.get() instead of reading
config.py constants directly for any user-changeable value.

SECURITY FIXES (v4.1):
  - Default PIN is stored as PBKDF2 hash (computed lazily at import time)
  - settings.json is written atomically via temp-file + os.replace() to
    prevent corruption on crash mid-write
"""

import json
import os
import logging
import threading
import tempfile

logger = logging.getLogger("examguard.settings")

_SETTINGS_DIR  = os.path.join(os.environ.get("APPDATA", "."), "ExamGuard")
_SETTINGS_FILE = os.path.join(_SETTINGS_DIR, "settings.json")
_lock          = threading.Lock()
_cache: "dict | None" = None

# ── Default PIN hash ───────────────────────────────────────────
# We cannot import security here at module level (circular import risk).
# Compute the default hash lazily on first use.
_DEFAULT_PIN_HASH: "str | None" = None

def _get_default_pin_hash() -> str:
    global _DEFAULT_PIN_HASH
    if _DEFAULT_PIN_HASH is None:
        # Lazy import to avoid circular dependency
        import security
        _DEFAULT_PIN_HASH = security.hash_pin("1234")
    return _DEFAULT_PIN_HASH


# ── Defaults ──────────────────────────────────────────────────
# NOTE: "instructor_pin" is intentionally absent from this dict.
# It is resolved via _get_default_pin_hash() to avoid plaintext storage.
_STATIC_DEFAULTS: dict = {
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


def _defaults() -> dict:
    """Return STATIC_DEFAULTS plus the hashed default PIN."""
    d = dict(_STATIC_DEFAULTS)
    d["instructor_pin"] = _get_default_pin_hash()
    return d


# ── Public API ────────────────────────────────────────────────

def load() -> dict:
    """Return a copy of the current settings (loads from disk if needed)."""
    global _cache
    with _lock:
        if _cache is None:
            _cache = _load_from_disk()
        return dict(_cache)


def save(settings: dict):
    """Merge settings with defaults and persist atomically to disk."""
    global _cache
    os.makedirs(_SETTINGS_DIR, exist_ok=True)
    with _lock:
        merged = {**_defaults(), **settings}
        _cache = merged
        _write_atomic(merged)


def get(key: str, default=None):
    """Get a single setting value."""
    d = _defaults()
    return load().get(key, d.get(key, default))


def set_value(key: str, value):
    """Update a single setting and persist atomically."""
    s = load()
    s[key] = value
    save(s)


def reset():
    """Reset all settings to defaults (PIN is reset to hashed '1234')."""
    save(_defaults())


# ── Internal ──────────────────────────────────────────────────

def _load_from_disk() -> dict:
    defaults = _defaults()
    if os.path.exists(_SETTINGS_FILE):
        try:
            with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {**defaults, **data}   # new keys get defaults
        except Exception as e:
            logger.warning("Could not read settings file: %s", e)
    return defaults


def _write_atomic(data: dict):
    """
    Write settings to a temp file then atomically rename to the target.
    This prevents corruption if the process crashes mid-write.
    """
    try:
        dir_ = _SETTINGS_DIR
        os.makedirs(dir_, exist_ok=True)
        # Write to a sibling temp file in the same directory
        fd, tmp_path = tempfile.mkstemp(dir=dir_, suffix=".tmp", prefix="settings_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, _SETTINGS_FILE)  # atomic on POSIX & Windows
        except Exception:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            raise
    except Exception as e:
        logger.error("Could not save settings: %s", e)
