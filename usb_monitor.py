# usb_monitor.py — ExamGuard v3 — USB/Pendrive Detection

"""
Polls Windows drive letters every USB_CHECK_INTERVAL seconds.
When a removable drive appears/disappears, fires the callback.
Uses only pywin32 (already installed) — no WMI overhead.
"""

import sys
import string
import threading
import time

from config import USB_CHECK_INTERVAL


def _get_removable_drives() -> set[str]:
    """Return set of currently mounted removable drive paths e.g. {'E:\\\\', 'F:\\\\'} """
    if sys.platform != "win32":
        return set()
    try:
        import win32file
        import win32api
        drives = set()
        for letter in string.ascii_uppercase:
            path = f"{letter}:\\"
            try:
                if win32file.GetDriveType(path) == win32file.DRIVE_REMOVABLE:
                    # Confirm it's actually mounted/readable
                    win32api.GetVolumeInformation(path)
                    drives.add(path)
            except Exception:
                pass
        return drives
    except Exception:
        return set()


def _drive_label(path: str) -> str:
    """Return 'E:\\ (MyUSB)' style label for a removable drive."""
    try:
        import win32api
        vol_name, _, _, _, _ = win32api.GetVolumeInformation(path)
        return f"{path}  ({vol_name})" if vol_name else path
    except Exception:
        return path


class USBMonitor:
    """
    Background thread that detects USB insertion and removal.

    Callbacks:
        on_insert(drive_path, drive_label)  — called on new removable drive
        on_remove(drive_path)               — called when drive disappears
    """

    def __init__(self,
                 on_insert: callable,
                 on_remove: callable):
        self._on_insert = on_insert
        self._on_remove = on_remove
        self._stop      = threading.Event()
        self._known: set[str] = set()
        self._thread: threading.Thread | None = None

    # ── Public API ─────────────────────────────────────────────

    def start(self):
        self._known = _get_removable_drives()
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="USBMonitor", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    # ── Loop ───────────────────────────────────────────────────

    def _loop(self):
        while not self._stop.wait(USB_CHECK_INTERVAL):
            current = _get_removable_drives()
            inserted = current - self._known
            removed  = self._known - current

            for drive in inserted:
                try:
                    self._on_insert(drive, _drive_label(drive))
                except Exception as e:
                    print(f"[USBMonitor] insert callback error: {e}")

            for drive in removed:
                try:
                    self._on_remove(drive)
                except Exception as e:
                    print(f"[USBMonitor] remove callback error: {e}")

            self._known = current
