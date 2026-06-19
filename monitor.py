# monitor.py — ExamGuard v3.1 — Background Monitoring Engine

"""
Monitoring threads:
  A) Window switch        — detects app/browser changes; screenshot on browser
  B) Clipboard text       — screenshot only on code-like content
  C) File clipboard       — CF_HDROP detection; screenshot on file copy
  D) Keystroke counter    — flushed every 30 s
  E) USB insertion        — screenshot on insert
  F) File access monitor  — watchdog on home/USB dirs

Screenshots are taken ONLY on suspicious events (not periodically).
Each event that carries risk calls risk_cb(event_type, points).
"""

import threading
import time
import os
import sys
from datetime import datetime

import pyperclip
from PIL import ImageGrab
from pynput import keyboard

try:
    import pygetwindow as gw
    _HAS_GW = True
except Exception:
    _HAS_GW = False

_HAS_WIN32 = False
if sys.platform == "win32":
    try:
        import win32clipboard, win32con
        _HAS_WIN32 = True
    except ImportError:
        pass

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    _HAS_WATCHDOG = True
except ImportError:
    _HAS_WATCHDOG = False

import database
import security
import settings_manager
from usb_monitor import USBMonitor
from config import (
    KEYSTROKE_SAVE_INTERVAL,
    RISK_W_WINDOW, RISK_W_CLIPBOARD, RISK_W_FILE_COPY,
    RISK_W_USB_INSERT, RISK_W_IDE_PREEXIST, RISK_W_FILE_ACCESS,
    IDE_PROCESSES, CODE_EXTENSIONS, WATCHED_SUBDIRS,
)

# ── Browser detection ─────────────────────────────────────────
BROWSER_KEYWORDS = [
    "google chrome", "mozilla firefox", "microsoft edge",
    "opera", "brave", "internet explorer", "safari", "chromium",
    "vivaldi", "tor browser",
]

# Code keywords for clipboard check
_CODE_KEYWORDS = [
    'def ', 'function ', 'int main', 'class ', 'import ',
    '#include', 'return;', 'void ', 'public static',
    'print(', 'printf(', 'cout <<', 'System.out', '#!/',
    'lambda ', 'for (', 'while (', 'if (',
]


# ─────────────────────────────────────────────────────────────
#  File-access watchdog handler
# ─────────────────────────────────────────────────────────────

class _CodeFileHandler(FileSystemEventHandler):
    def __init__(self, callback: callable):
        super().__init__()
        self._cb = callback
        self._debounce: dict[str, float] = {}

    def _should_report(self, path: str) -> bool:
        now  = time.time()
        last = self._debounce.get(path, 0.0)
        if now - last >= 10.0:
            self._debounce[path] = now
            return True
        return False

    def _check(self, event):
        if event.is_directory:
            return
        ext = os.path.splitext(event.src_path)[1].lower()
        if ext in CODE_EXTENSIONS and self._should_report(event.src_path):
            self._cb(event.src_path)

    def on_created(self,  event): self._check(event)
    def on_modified(self, event): self._check(event)


# ─────────────────────────────────────────────────────────────
#  Pre-exam IDE content check
# ─────────────────────────────────────────────────────────────

def check_ide_preexisting(session_id: int, risk_cb: callable) -> int:
    """Run ONCE at exam start. Returns total risk points added."""
    total = 0

    # Clipboard check
    try:
        clip = pyperclip.paste() or ""
        if len(clip) > 30 and any(kw in clip for kw in _CODE_KEYWORDS):
            snippet = clip[:150].replace("\n", " ")
            database.log_event(session_id, "ide_preexisting",
                               f"Code-like content in clipboard at exam start: {snippet}")
            risk_cb("ide_preexisting", RISK_W_IDE_PREEXIST)
            total += RISK_W_IDE_PREEXIST
    except Exception:
        pass

    # Running IDE check
    if _HAS_PSUTIL:
        seen = set()
        try:
            for proc in psutil.process_iter(["name", "cmdline"]):
                pname = (proc.info.get("name") or "").lower()
                if pname in IDE_PROCESSES and pname not in seen:
                    seen.add(pname)
                    try:
                        cmdline = proc.cmdline() or []
                        open_files = [
                            a for a in cmdline[1:]
                            if os.path.isfile(a)
                            and os.path.splitext(a)[1].lower() in CODE_EXTENSIONS
                        ]
                        if open_files:
                            database.log_event(session_id, "ide_preexisting",
                                               f"IDE '{pname}' had file open: {open_files[0]}")
                            risk_cb("ide_preexisting", RISK_W_IDE_PREEXIST // 2)
                            total += RISK_W_IDE_PREEXIST // 2
                    except Exception:
                        pass
        except Exception:
            pass

    return total


# ─────────────────────────────────────────────────────────────
#  Main monitoring engine
# ─────────────────────────────────────────────────────────────

class MonitorEngine:
    def __init__(self, session_id: int, risk_cb: callable = None):
        self.session_id  = session_id
        self._risk_cb    = risk_cb or (lambda *_: None)
        self._stop       = threading.Event()

        self._last_window    = ""
        self._last_clipboard = ""
        self._keystrokes     = 0
        self._backspaces     = 0

        self._vault          = security.ensure_vault()
        self._threads: list  = []
        self._kb_listener    = None
        self._usb_monitor    = None
        self._fs_observer    = None

        # Debounce browser screenshots
        self._last_browser_shot = 0.0
        self._BROWSER_SHOT_DEBOUNCE = 15.0   # max 1 shot per 15 s per browser open

    # ── Public API ─────────────────────────────────────────────

    def start(self):
        self._stop.clear()

        for name, fn in [
            ("WinMon",  self._window_loop),
            ("ClipMon", self._clipboard_loop),
            ("KsFlush", self._keystroke_flush_loop),
        ]:
            t = threading.Thread(target=fn, name=name, daemon=True)
            t.start()
            self._threads.append(t)

        self._kb_listener = keyboard.Listener(
            on_press=self._on_key, suppress=False)
        self._kb_listener.start()

        self._usb_monitor = USBMonitor(
            on_insert=self._on_usb_insert,
            on_remove=self._on_usb_remove)
        self._usb_monitor.start()

        if _HAS_WATCHDOG:
            self._start_fs_observer()

    def stop(self):
        self._stop.set()
        if self._kb_listener:
            try: self._kb_listener.stop()
            except Exception: pass
        if self._usb_monitor:
            self._usb_monitor.stop()
        if self._fs_observer:
            try: self._fs_observer.stop()
            except Exception: pass
        try:
            database.update_keystroke_count(self.session_id, self._keystrokes)
        except Exception:
            pass

    # ── Keystroke ──────────────────────────────────────────────

    def _on_key(self, key):
        if self._stop.is_set():
            return False
        self._keystrokes += 1
        try:
            if key == keyboard.Key.backspace:
                self._backspaces += 1
        except Exception:
            pass

    def _keystroke_flush_loop(self):
        while not self._stop.wait(KEYSTROKE_SAVE_INTERVAL):
            try:
                database.update_keystroke_count(self.session_id, self._keystrokes)
                database.log_event(
                    self.session_id, "keystroke_count",
                    f"total={self._keystrokes} backspaces={self._backspaces}")
            except Exception as e:
                print(f"[KsFlush] {e}")

    # ── Window monitor ─────────────────────────────────────────

    def _window_loop(self):
        if not _HAS_GW:
            return
        interval = settings_manager.get("window_check_interval", 0.5)
        while not self._stop.wait(interval):
            try:
                win   = gw.getActiveWindow()
                title = (win.title or "").strip() if win else ""
                if not title or title == self._last_window:
                    continue

                self._last_window = title
                database.log_event(self.session_id, "window_switch", title[:300])
                self._risk_cb("window_switch", RISK_W_WINDOW)

                # ── Browser detection: instant screenshot ──────
                title_lower = title.lower()
                is_browser = any(kw in title_lower for kw in BROWSER_KEYWORDS)
                if is_browser and settings_manager.get("screenshot_on_browser", True):
                    now = time.time()
                    if now - self._last_browser_shot >= self._BROWSER_SHOT_DEBOUNCE:
                        self._last_browser_shot = now
                        self._take_screenshot(label="BROWSER")

            except Exception:
                pass

    # ── Clipboard (text + files) ───────────────────────────────

    def _clipboard_loop(self):
        try:
            self._last_clipboard = pyperclip.paste() or ""
        except Exception:
            self._last_clipboard = ""

        interval = settings_manager.get("clipboard_check_interval", 1.0)
        while not self._stop.wait(interval):
            # Text clipboard
            try:
                text = pyperclip.paste() or ""
                if text and text != self._last_clipboard:
                    self._last_clipboard = text
                    snippet = text[:200].replace("\n", " ").replace("\r", "")
                    database.log_event(self.session_id, "clipboard_change", snippet)
                    self._risk_cb("clipboard_change", RISK_W_CLIPBOARD)

                    # Screenshot if content looks like code
                    if (settings_manager.get("screenshot_on_clipboard", True)
                            and len(text) > 20
                            and any(kw in text for kw in _CODE_KEYWORDS)):
                        self._take_screenshot(label="CLIPBOARD")

            except Exception:
                pass

            # File clipboard (CF_HDROP)
            if _HAS_WIN32:
                try:
                    win32clipboard.OpenClipboard()
                    if win32clipboard.IsClipboardFormatAvailable(win32con.CF_HDROP):
                        files = win32clipboard.GetClipboardData(win32con.CF_HDROP)
                        win32clipboard.CloseClipboard()
                        if files:
                            joined = " | ".join(files[:10])
                            if joined != self._last_clipboard:
                                self._last_clipboard = joined
                                database.log_event(
                                    self.session_id, "file_copy",
                                    f"[FILES] {joined[:300]}")
                                self._risk_cb("file_copy", RISK_W_FILE_COPY)
                                if settings_manager.get("screenshot_on_file_copy", True):
                                    self._take_screenshot(label="FILE_COPY")
                    else:
                        win32clipboard.CloseClipboard()
                except Exception:
                    try: win32clipboard.CloseClipboard()
                    except Exception: pass

    # ── Screenshot (event-driven only) ─────────────────────────

    def _take_screenshot(self, label: str = "") -> str | None:
        try:
            ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
            suffix   = f"_{label}" if label else ""
            filename = f"s{self.session_id}_{ts}{suffix}.png"
            filepath = os.path.join(self._vault, filename)
            img      = ImageGrab.grab()
            img.save(filepath, "PNG", optimize=True)
            if sys.platform == "win32":
                try:
                    import ctypes
                    ctypes.windll.kernel32.SetFileAttributesW(filepath, 0x2)
                except Exception:
                    pass
            database.log_event(self.session_id, "screenshot", filepath)
            return filepath
        except Exception as e:
            print(f"[Screenshot] {e}")
            return None

    # ── USB events ─────────────────────────────────────────────

    def _on_usb_insert(self, drive: str, label: str):
        detail = f"USB INSERTED: {label}"
        database.log_event(self.session_id, "usb_insert", detail)
        self._risk_cb("usb_insert", RISK_W_USB_INSERT)
        if settings_manager.get("screenshot_on_usb", True):
            self._take_screenshot(label="USB_INSERT")
        if _HAS_WATCHDOG and self._fs_observer:
            try:
                handler = _CodeFileHandler(self._on_file_access)
                self._fs_observer.schedule(handler, drive, recursive=True)
            except Exception:
                pass

    def _on_usb_remove(self, drive: str):
        database.log_event(self.session_id, "usb_remove", f"USB REMOVED: {drive}")

    # ── File access ────────────────────────────────────────────

    def _start_fs_observer(self):
        home    = os.path.expanduser("~")
        handler = _CodeFileHandler(self._on_file_access)
        obs     = Observer()
        for subdir in WATCHED_SUBDIRS:
            path = os.path.join(home, subdir)
            if os.path.isdir(path):
                try:
                    obs.schedule(handler, path, recursive=True)
                except Exception:
                    pass
        obs.start()
        self._fs_observer = obs

    def _on_file_access(self, filepath: str):
        database.log_event(self.session_id, "file_access",
                           f"Code file accessed: {filepath}")
        self._risk_cb("file_access", RISK_W_FILE_ACCESS)
        if settings_manager.get("screenshot_on_file_access", True):
            self._take_screenshot(label="FILE_ACCESS")
