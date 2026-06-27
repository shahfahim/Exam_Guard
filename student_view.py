# student_view.py — ExamGuard v4 — Student Exam View (CTkFrame, single-window)

import tkinter as tk
import customtkinter as ctk
import threading, socket
from datetime import datetime

import database, security, settings_manager
from monitor import MonitorEngine, check_ide_preexisting
from screen_lock import ScreenLock
from theme import *


# Toast messages per event type
_TOAST = {
    "clipboard_change": (f"📋  Clipboard activity recorded", WARNING),
    "file_copy":        (f"📁  File copy detected — logged", DANGER),
    "usb_insert":       (f"🔌  USB device inserted — screenshot taken", DANGER),
    "file_access":      (f"📂  External file access logged", DANGER),
    "ide_preexisting":  (f"⚠   Pre-existing code found at exam start", DANGER),
}


class StudentView(ctk.CTkFrame):
    """
    Student exam view.
    - Shows name/ID form, timer, live risk bar.
    - Runs monitoring engine in background.
    - Communicates back to app via self._app callbacks.
    """

    def __init__(self, parent, app):
        super().__init__(parent, fg_color=BG)
        self._app = app

        # State
        self._session_id: int | None = None
        self._monitor: MonitorEngine | None = None
        self._lock: ScreenLock | None = None
        self._running     = False
        self._ended       = False
        self._elapsed     = 0
        self._tick_job    = None
        self._risk_score  = 0
        self._risk_lock   = threading.Lock()   # guards _risk_score mutations
        self._risk_events: list = []
        self._next_lock_at = settings_manager.get("risk_lock_threshold", 150)

        self._build()

    # ── Build UI ───────────────────────────────────────────────

    def _build(self):
        # ── Page header ────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=56)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="Student Exam",
                     font=ctk.CTkFont("Segoe UI", 16, "bold"), text_color=TEXT
                     ).pack(side="left", padx=24, pady=16)
        ctk.CTkLabel(hdr, text=socket.gethostname(),
                     font=ctk.CTkFont("Segoe UI", 10), text_color=MUTED
                     ).pack(side="right", padx=24)

        # ── Divider ────────────────────────────────────────────
        ctk.CTkFrame(self, fg_color=BORDER, height=1).pack(fill="x")

        # ── Centered content ───────────────────────────────────
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.52)

        # Student info card
        info_card = ctk.CTkFrame(body, fg_color=CARD, corner_radius=12,
                                 border_width=1, border_color=BORDER)
        info_card.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(info_card, text="Student Information",
                     font=ctk.CTkFont("Segoe UI", 12, "bold"), text_color=LABEL, anchor="w"
                     ).pack(fill="x", padx=20, pady=(18, 12))

        self._name_var = tk.StringVar()
        self._id_var   = tk.StringVar()

        for label, var, ph in [
            ("Full Name",   self._name_var, "Enter your full name"),
            ("Student ID",  self._id_var,   "e.g. 2024-0042"),
        ]:
            row = ctk.CTkFrame(info_card, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=(0, 10))
            ctk.CTkLabel(row, text=label, width=90, anchor="w",
                         font=ctk.CTkFont("Segoe UI", 11), text_color=LABEL).pack(side="left")
            e = ctk.CTkEntry(row, textvariable=var, placeholder_text=ph,
                             height=38, corner_radius=8, fg_color=CARD3,
                             border_color=BORDER, border_width=1,
                             font=ctk.CTkFont("Segoe UI", 12), text_color=TEXT)
            e.pack(side="left", fill="x", expand=True)
            if label == "Full Name":
                self._name_entry = e
            else:
                self._id_entry = e

        ctk.CTkFrame(info_card, fg_color=BORDER, height=1).pack(fill="x", padx=20, pady=(4, 14))

        # Exam card
        exam_card = ctk.CTkFrame(body, fg_color=CARD, corner_radius=12,
                                  border_width=1, border_color=BORDER)
        exam_card.pack(fill="x")

        # Timer
        timer_frame = ctk.CTkFrame(exam_card, fg_color="transparent")
        timer_frame.pack(pady=(24, 0))
        self._timer_lbl = ctk.CTkLabel(timer_frame, text="00:00:00",
                                        font=ctk.CTkFont("Courier New", 58, "bold"),
                                        text_color=SUBTLE)
        self._timer_lbl.pack()
        self._status_lbl = ctk.CTkLabel(timer_frame, text="Ready to start",
                                         font=ctk.CTkFont("Segoe UI", 12), text_color=MUTED)
        self._status_lbl.pack(pady=(2, 0))

        # Risk bar
        rb_frame = ctk.CTkFrame(exam_card, fg_color="transparent")
        rb_frame.pack(fill="x", padx=24, pady=(14, 0))
        self._risk_bg = ctk.CTkFrame(rb_frame, fg_color=CARD3, corner_radius=4, height=5)
        self._risk_bg.pack(fill="x")
        self._risk_bg.pack_propagate(False)
        self._risk_fill = ctk.CTkFrame(self._risk_bg, fg_color=MUTED, corner_radius=4, height=5, width=0)
        self._risk_fill.place(x=0, y=0, relheight=1)

        # Buttons
        btn_row = ctk.CTkFrame(exam_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=24, pady=(16, 22))

        self._start_btn = ctk.CTkButton(
            btn_row, text="▶  Start Exam",
            height=48, corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_H,
            command=self._start_exam)
        self._start_btn.pack(fill="x", pady=(0, 8))

        # End session (instructor only) - hidden until exam starts
        self._end_frame = ctk.CTkFrame(btn_row, fg_color="transparent")
        # Not packed yet; shown after MIN_EXAM_SECONDS

        self._pin_inline = _InlinePINForm(
            btn_row,
            on_success=self._on_instructor_verified,
            on_cancel=self._hide_pin_form)
        # Not packed yet

        # Error label
        self._err_lbl = ctk.CTkLabel(body, text="",
                                      font=ctk.CTkFont("Segoe UI", 11), text_color=DANGER)
        self._err_lbl.pack(pady=(8, 0))

        # Toast area (bottom of page)
        self._toast_host = ctk.CTkFrame(self, fg_color="transparent", height=40)
        self._toast_host.pack(side="bottom", fill="x")

    # ── Exam control ───────────────────────────────────────────

    def _start_exam(self):
        name = self._name_var.get().strip()
        sid  = self._id_var.get().strip()
        if not name: self._show_err("Please enter your full name."); return
        if not sid:  self._show_err("Please enter your student ID."); return

        self._name_entry.configure(state="disabled")
        self._id_entry.configure(state="disabled")
        self._start_btn.configure(state="disabled", text="Exam in progress…")

        self._session_id   = database.create_session(name, sid, socket.gethostname())
        self._next_lock_at = settings_manager.get("risk_lock_threshold", 150)

        # Pre-exam IDE check (background)
        def _pre():
            check_ide_preexisting(self._session_id, self._on_risk_event)
        threading.Thread(target=_pre, daemon=True).start()

        # Start monitor
        self._monitor = MonitorEngine(self._session_id, risk_cb=self._on_risk_event)
        self._monitor.start()

        # Screen lock
        self._lock = ScreenLock(self._app, on_unlock=self._on_unlock)

        self._running = True
        self._timer_lbl.configure(text_color=SUCCESS)
        self._status_lbl.configure(text="● Monitoring active", text_color=SUCCESS)
        self._tick()

        self._app.on_exam_started(self._session_id)

        # Show "End Session" after minimum time
        min_s = settings_manager.get("min_exam_seconds", 10)
        self.after(min_s * 1000, self._show_end_section)

    def _tick(self):
        if not self._running: return
        self._elapsed += 1
        h = self._elapsed // 3600
        m = (self._elapsed % 3600) // 60
        s = self._elapsed % 60
        self._timer_lbl.configure(text=f"{h:02d}:{m:02d}:{s:02d}")
        self._tick_job = self.after(1000, self._tick)

    def _show_end_section(self):
        if self._ended: return
        ef = self._end_frame
        ef.pack(fill="x")
        ctk.CTkFrame(ef, fg_color=BORDER, height=1).pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(ef, text="Instructor Only",
                     font=ctk.CTkFont("Segoe UI", 9), text_color=MUTED).pack(anchor="w")
        ctk.CTkButton(ef, text="🔐  End Session",
                      height=38, corner_radius=8,
                      font=ctk.CTkFont("Segoe UI", 12),
                      fg_color=CARD2, hover_color=BORDER,
                      border_width=1, border_color=BORDER2, text_color=LABEL,
                      command=self._show_pin_form).pack(fill="x", pady=(4, 0))

    def _show_pin_form(self):
        self._end_frame.pack_forget()
        self._pin_inline.pack(fill="x")
        self._pin_inline.focus_entry()

    def _hide_pin_form(self):
        self._pin_inline.pack_forget()
        self._end_frame.pack(fill="x")

    def _on_instructor_verified(self):
        self._stop_exam()
        self._show_done_overlay()
        self.after(800, lambda: self._app.on_exam_ended(self._session_id))

    def _stop_exam(self):
        if self._ended: return
        self._ended = self._running = False
        if self._tick_job: self.after_cancel(self._tick_job)
        if self._monitor:
            threading.Thread(target=self._monitor.stop, daemon=True).start()
        database.end_session(self._session_id)
        database.log_access("session_ended", f"session_id={self._session_id}")

    def _show_done_overlay(self):
        ov = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        ov.place(relx=0, rely=0, relwidth=1, relheight=1)
        cf = ctk.CTkFrame(ov, fg_color="transparent")
        cf.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(cf, text="✓", font=ctk.CTkFont("Segoe UI", 72), text_color=SUCCESS).pack()
        ctk.CTkLabel(cf, text="Session Ended",
                     font=ctk.CTkFont("Segoe UI", 24, "bold"), text_color=TEXT).pack(pady=(6, 0))
        ctk.CTkLabel(cf, text="Opening instructor dashboard…",
                     font=ctk.CTkFont("Segoe UI", 12), text_color=MUTED).pack(pady=(8, 0))

    # ── Risk ───────────────────────────────────────────────────

    def _on_risk_event(self, event_type: str, points: int):
        """Called from any thread. Thread-safe risk score update."""
        with self._risk_lock:
            self._risk_score += points
            self._risk_events.append((event_type, points))
        self.after(0, lambda et=event_type: self._update_risk(et))

    def _update_risk(self, event_type: str = ""):
        score     = self._risk_score
        threshold = self._next_lock_at
        green_max = settings_manager.get("risk_green_max", 20)
        yellow_max= settings_manager.get("risk_yellow_max", 50)

        try:
            bw = self._risk_bg.winfo_width()
            fraction = min(score / max(threshold, 1), 1.0)
            new_w = max(4, int(bw * fraction))
        except Exception:
            new_w = 4

        color = SUCCESS if score <= green_max else (WARNING if score <= yellow_max else DANGER)
        self._risk_fill.configure(fg_color=color, width=new_w)

        # Toast
        if event_type in _TOAST:
            msg, tc = _TOAST[event_type]
            self._show_toast(msg, tc)

        # Lock?
        if score >= threshold and self._running and not self._ended:
            if not (self._lock and self._lock.is_locked()):
                self._trigger_lock()

    def _trigger_lock(self):
        recent = ", ".join(t for t, _ in self._risk_events[-3:])
        database.log_event(self._session_id, "screen_locked", f"risk={self._risk_score}")
        if self._lock:
            self._lock.lock(
                f"Risk score ({self._risk_score}) exceeded limit "
                f"({self._next_lock_at}).\nRecent: {recent}")

    def _on_unlock(self):
        # ── Key fix: raise next threshold so no instant re-lock
        self._next_lock_at = self._risk_score + 50
        self._status_lbl.configure(text="● Monitoring active", text_color=SUCCESS)
        self._show_toast(f"🔓  Screen unlocked  (risk: {self._risk_score})", SUCCESS)

    # ── Toast ──────────────────────────────────────────────────

    def _show_toast(self, msg: str, color: str = WARNING):
        try:
            t = ctk.CTkFrame(self, fg_color=color, corner_radius=0, height=38)
            t.place(x=0, rely=1.0, relwidth=1.0, anchor="sw")
            t.pack_propagate(False)
            ctk.CTkLabel(t, text=msg,
                         font=ctk.CTkFont("Segoe UI", 11, "bold"),
                         text_color="#ffffff").pack(pady=9)
            self.after(3500, t.destroy)
        except Exception:
            pass

    def _show_err(self, msg):
        self._err_lbl.configure(text=f"⚠  {msg}")
        self.after(3500, lambda: self._err_lbl.configure(text=""))


# ─────────────────────────────────────────────────────────────
#  Inline PIN form (embedded in student view, no new window)
# ─────────────────────────────────────────────────────────────

class _InlinePINForm(ctk.CTkFrame):
    def __init__(self, parent, on_success, on_cancel):
        super().__init__(parent, fg_color="transparent")
        self._on_success   = on_success
        self._on_cancel    = on_cancel
        self._attempts     = 0
        self._locked_until = 0.0   # epoch seconds; 0 = not locked
        self._build()

    def _build(self):
        ctk.CTkFrame(self, fg_color=BORDER, height=1).pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(self, text="Instructor PIN required to end session",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=MUTED).pack(anchor="w")

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", pady=(6, 0))

        self._pin_var = tk.StringVar()
        self._entry = ctk.CTkEntry(row, textvariable=self._pin_var, show="\u25cf",
                                    placeholder_text="PIN", justify="center",
                                    height=38, corner_radius=8, width=140,
                                    font=ctk.CTkFont("Segoe UI", 16),
                                    fg_color=CARD3, border_color=ACCENT, border_width=1,
                                    text_color=TEXT)
        self._entry.pack(side="left", padx=(0, 8))
        self._entry.bind("<Return>", lambda _: self._verify())

        ctk.CTkButton(row, text="Verify", width=80, height=38, corner_radius=8,
                      font=ctk.CTkFont("Segoe UI", 12, "bold"),
                      fg_color=ACCENT, hover_color=ACCENT_H,
                      command=self._verify).pack(side="left", padx=(0, 4))

        self._cancel_btn = ctk.CTkButton(
            row, text="Cancel", width=70, height=38, corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 11),
            fg_color=CARD2, hover_color=BORDER, border_width=1, border_color=BORDER,
            command=self._cancel)
        self._cancel_btn.pack(side="left")

        self._msg = ctk.CTkLabel(self, text="", font=ctk.CTkFont("Segoe UI", 10),
                                  text_color=DANGER)
        self._msg.pack(anchor="w", pady=(4, 0))

    def focus_entry(self):
        self._entry.focus()

    def _verify(self):
        import time
        now = time.time()
        if now < self._locked_until:
            remaining = int(self._locked_until - now)
            self._msg.configure(text=f"Locked for {remaining}s more.")
            return

        self._attempts += 1
        if security.verify_pin(self._pin_var.get()):
            database.log_access("instructor_auth_ok", f"attempt={self._attempts}")
            self._on_success()
        else:
            database.log_access("instructor_auth_fail", f"attempt={self._attempts}")
            self._pin_var.set("")
            self._entry.focus()
            self._msg.configure(
                text=f"Incorrect PIN  ({self._attempts} attempt{'s' if self._attempts > 1 else ''})")

            if self._attempts >= 5:
                import time as _t
                self._locked_until = _t.time() + 30
                self._entry.configure(state="disabled")
                self._cancel_btn.configure(state="disabled")   # cannot bypass via Cancel
                self._msg.configure(text="Too many attempts. Locked for 30 seconds.")
                self.after(30_000, self._reset_lockout)

    def _reset_lockout(self):
        self._locked_until = 0.0
        self._attempts = 0
        try:
            self._entry.configure(state="normal")
            self._cancel_btn.configure(state="normal")
            self._msg.configure(text="")
            self._entry.focus()
        except Exception:
            pass   # widget may have been destroyed

    def _cancel(self):
        import time
        if time.time() < self._locked_until:
            return   # silently block cancel during lockout
        self._pin_var.set("")
        self._msg.configure(text="")
        self._attempts = 0
        self._entry.configure(state="normal")
        self._on_cancel()
