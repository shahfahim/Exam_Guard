# screen_lock.py — ExamGuard v3 — Full-Screen Lock Overlay

"""
Creates a borderless full-screen Tk window that:
  - Sits above everything (topmost)
  - Grabs all keyboard + mouse events (no click-through)
  - Intercepts Alt+F4, Escape, etc.
  - Only dismisses on correct instructor PIN

Usage:
    lock = ScreenLock(root_widget, on_unlock_callback)
    lock.lock("USB device detected")   # triggers the overlay
    # Instructor enters PIN → overlay destroys itself → on_unlock_callback()
"""

import tkinter as tk
import customtkinter as ctk
import threading

import security
import database

# ── Design tokens ─────────────────────────────────────────────
_BG     = "#070a10"
_CARD   = "#111318"
_BORDER = "#1e2130"
_ACCENT = "#6366f1"
_DANGER = "#ef4444"
_TEXT   = "#f1f5f9"
_MUTED  = "#475569"
_SUCCESS= "#22c55e"


class ScreenLock:
    """
    Manages the full-screen lock overlay lifecycle.
    Thread-safe: lock() / unlock() can be called from any thread.
    """

    def __init__(self, root: tk.Misc, on_unlock: callable):
        self._root      = root
        self._on_unlock = on_unlock
        self._win: ctk.CTkToplevel | None = None
        self._locked    = False

    # ── Public API ────────────────────────────────────────────

    def is_locked(self) -> bool:
        return self._locked

    def lock(self, reason: str = "Risk threshold exceeded"):
        """Call from any thread — schedules on the Tk main thread."""
        if self._locked:
            return
        self._locked = True
        self._root.after(0, lambda: self._show(reason))

    def unlock(self):
        """Destroy the overlay. Called after successful PIN."""
        if self._win:
            try:
                self._win.grab_release()
                self._win.destroy()
            except Exception:
                pass
            self._win = None
        self._locked = False

    # ── Build overlay ─────────────────────────────────────────

    def _show(self, reason: str):
        # Destroy any leftover overlay
        if self._win:
            try:
                self._win.destroy()
            except Exception:
                pass

        win = ctk.CTkToplevel(self._root)
        self._win = win

        # Full-screen, no decorations, always on top
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        win.geometry(f"{sw}x{sh}+0+0")
        win.overrideredirect(True)
        win.configure(fg_color=_BG)
        win.attributes("-topmost", True)

        # Block close attempts
        for seq in ("<Alt-F4>", "<Escape>", "<Alt-Tab>"):
            win.bind(seq, lambda e: "break")

        win.update_idletasks()
        win.lift()
        win.focus_force()
        win.grab_set()

        self._build_ui(win, reason, sw, sh)

    def _build_ui(self, win: ctk.CTkToplevel, reason: str,
                  sw: int, sh: int):
        # ── Centre column ──────────────────────────────────────
        # We use a canvas-like centering via place
        centre = ctk.CTkFrame(win, fg_color=_CARD, corner_radius=16,
                              border_width=1, border_color=_BORDER,
                              width=440, height=480)
        centre.place(relx=0.5, rely=0.5, anchor="center")
        centre.pack_propagate(False)

        # Lock icon
        ctk.CTkLabel(centre, text="🔒",
                     font=ctk.CTkFont("Segoe UI", 64)).pack(pady=(44, 0))

        ctk.CTkLabel(centre, text="Session Locked",
                     font=ctk.CTkFont("Segoe UI", 26, "bold"),
                     text_color=_DANGER).pack(pady=(10, 4))

        ctk.CTkLabel(centre, text=reason,
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=_MUTED,
                     wraplength=360,
                     justify="center").pack(pady=(0, 28))

        ctk.CTkFrame(centre, fg_color=_BORDER, height=1).pack(fill="x", padx=32)

        ctk.CTkLabel(centre, text="Instructor PIN required to continue",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=_MUTED).pack(pady=(20, 8))

        pin_var = tk.StringVar()
        pin_entry = ctk.CTkEntry(
            centre, textvariable=pin_var,
            show="●", placeholder_text="Enter PIN",
            justify="center", height=48, width=220,
            font=ctk.CTkFont("Segoe UI", 20),
            fg_color=_BG, border_color=_ACCENT,
            border_width=1, corner_radius=10,
            text_color=_TEXT)
        pin_entry.pack()
        pin_entry.focus()

        err_lbl = ctk.CTkLabel(centre, text="",
                               font=ctk.CTkFont("Segoe UI", 11),
                               text_color=_DANGER)
        err_lbl.pack(pady=(6, 0))

        # Use nonlocal-capable vars — clean Python 3 approach (no mutable list)
        attempt_count  = 0
        locked_until   = 0.0  # epoch seconds

        def _verify(_event=None):
            nonlocal attempt_count, locked_until
            import time
            now = time.time()

            # Respect active lockout
            if now < locked_until:
                remaining = int(locked_until - now)
                err_lbl.configure(text=f"Locked. Try again in {remaining}s.")
                return

            attempt_count += 1
            if security.verify_pin(pin_var.get()):
                database.log_access("screen_unlock",
                                    f"attempt={attempt_count}")
                self.unlock()
                self._on_unlock()
            else:
                database.log_access("screen_unlock_fail",
                                    f"attempt={attempt_count}")
                err_lbl.configure(
                    text=f"Incorrect PIN  "
                         f"({attempt_count} attempt"
                         f"{'s' if attempt_count > 1 else ''})")
                pin_var.set("")
                pin_entry.focus()

                if attempt_count >= 5:
                    import time as _t
                    locked_until = _t.time() + 30
                    err_lbl.configure(text="Too many attempts. Wait 30 seconds.")
                    pin_entry.configure(state="disabled")

                    def _reset_lockout():
                        nonlocal attempt_count, locked_until
                        attempt_count = 0
                        locked_until  = 0.0
                        try:
                            pin_entry.configure(state="normal")
                            err_lbl.configure(text="")
                            pin_entry.focus()
                        except Exception:
                            pass  # window may have been destroyed before 30s

                    try:
                        win.after(30_000, _reset_lockout)
                    except Exception:
                        pass  # win already destroyed

        pin_entry.bind("<Return>", _verify)

        ctk.CTkButton(
            centre, text="Unlock Session",
            height=46, width=220, corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            fg_color=_ACCENT, hover_color="#4f46e5",
            command=_verify).pack(pady=(12, 0))

        # Dim background label
        ctk.CTkLabel(win,
                     text="This workstation has been locked by ExamGuard.",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=_BORDER).place(relx=0.5, rely=0.96, anchor="center")
