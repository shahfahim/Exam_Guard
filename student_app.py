# student_app.py — ExamGuard v3.1 — Student Exam Screen

import tkinter as tk
import customtkinter as ctk
import threading
import socket
from datetime import datetime

import database
import security
import settings_manager
from monitor import MonitorEngine, check_ide_preexisting
from screen_lock import ScreenLock

# ── Design tokens ──────────────────────────────────────────────
BG      = "#0d0f14"
CARD    = "#13161e"
CARD2   = "#1a1e28"
BORDER  = "#252936"
ACCENT  = "#6366f1"
ACCENT_H= "#4f46e5"
SUCCESS = "#22c55e"
DANGER  = "#ef4444"
WARNING = "#f59e0b"
TEXT    = "#f1f5f9"
MUTED   = "#64748b"
LABEL   = "#94a3b8"

# Toast messages shown to student for each event type
_TOASTS = {
    "clipboard_change": ("📋  Clipboard activity has been recorded", WARNING),
    "file_copy":        ("📁  File copy detected — this is logged", DANGER),
    "usb_insert":       ("🔌  USB device detected — screenshot taken", DANGER),
    "file_access":      ("📂  External file access has been logged", DANGER),
    "ide_preexisting":  ("⚠   Pre-existing code detected at start", DANGER),
}


class StudentApp(ctk.CTkToplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("ExamGuard — Student Exam")
        self.geometry("500x640")
        self.minsize(460, 600)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._session_id: int | None = None
        self._monitor: MonitorEngine | None = None
        self._lock: ScreenLock | None = None

        self._running    = False
        self._ended      = False
        self._elapsed    = 0
        self._tick_job   = None

        # Live risk tracking
        self._risk_score   = 0
        self._risk_events: list[tuple[str, int]] = []
        # ── FIX: after each unlock, raise threshold above current score ──
        self._next_lock_at = settings_manager.get("risk_lock_threshold", 150)

        self._build_ui()
        self._center()
        self.lift()
        self.focus_force()

    def _center(self):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h   = self.winfo_width(), self.winfo_height()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    # ── Build UI ───────────────────────────────────────────────

    def _build_ui(self):
        # Top bar
        bar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=52)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        ctk.CTkLabel(bar, text="🛡  ExamGuard",
                     font=ctk.CTkFont("Segoe UI", 15, "bold"),
                     text_color=ACCENT).pack(side="left", padx=20)
        ctk.CTkLabel(bar, text="Student",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=MUTED).pack(side="left")
        ctk.CTkLabel(bar, text=socket.gethostname(),
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color=BORDER).pack(side="right", padx=16)

        # Body
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=18)

        self._mk_label(body, "Full Name")
        self._name_var = tk.StringVar()
        self._name_entry = self._mk_entry(body, self._name_var, "Enter your full name")

        self._mk_label(body, "Student ID", top=14)
        self._id_var = tk.StringVar()
        self._id_entry = self._mk_entry(body, self._id_var, "e.g. 2024-0042")

        # Timer card
        tc = ctk.CTkFrame(body, fg_color=CARD, corner_radius=12,
                          border_width=1, border_color=BORDER)
        tc.pack(fill="x", pady=(22, 0))

        self._timer_lbl = ctk.CTkLabel(
            tc, text="00:00:00",
            font=ctk.CTkFont("Courier New", 56, "bold"),
            text_color=BORDER)
        self._timer_lbl.pack(pady=(18, 2))

        self._status_lbl = ctk.CTkLabel(
            tc, text="Ready to start",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=MUTED)
        self._status_lbl.pack(pady=(0, 6))

        # Risk meter — thin bar, grows silently (no number shown)
        meter_frame = ctk.CTkFrame(tc, fg_color="transparent")
        meter_frame.pack(fill="x", padx=20, pady=(4, 4))

        self._risk_bar_bg = ctk.CTkFrame(
            meter_frame, fg_color=CARD2, corner_radius=4, height=6)
        self._risk_bar_bg.pack(fill="x")
        self._risk_bar_bg.pack_propagate(False)
        self._risk_bar = ctk.CTkFrame(
            self._risk_bar_bg, fg_color=MUTED, corner_radius=4, height=6, width=0)
        self._risk_bar.place(x=0, y=0, relheight=1)

        # Risk label (discreet)
        self._risk_hint = ctk.CTkLabel(
            meter_frame, text="",
            font=ctk.CTkFont("Segoe UI", 9),
            text_color=BORDER)
        self._risk_hint.pack(anchor="e", pady=(2, 0))

        # Start button
        self._start_btn = ctk.CTkButton(
            tc, text="▶  Start Exam",
            height=48, corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 15, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_H,
            command=self._start_exam)
        self._start_btn.pack(fill="x", padx=20, pady=(10, 18))

        # Error
        self._err_lbl = ctk.CTkLabel(body, text="",
                                      font=ctk.CTkFont("Segoe UI", 11),
                                      text_color=DANGER)
        self._err_lbl.pack(pady=(6, 0))

        # Footer: instructor end link (hidden initially)
        footer = ctk.CTkFrame(self, fg_color="transparent", height=30)
        footer.pack(fill="x", side="bottom", padx=20, pady=(0, 8))
        footer.pack_propagate(False)
        self._end_link = ctk.CTkButton(
            footer, text="End Session  [Instructor Only]",
            font=ctk.CTkFont("Segoe UI", 10),
            text_color=BORDER, fg_color="transparent",
            hover_color=CARD, height=26, corner_radius=6,
            state="disabled",
            command=self._instructor_end_dialog)
        self._end_link.pack(side="right")

    def _mk_label(self, parent, text, top=0):
        ctk.CTkLabel(parent, text=text, anchor="w",
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color=LABEL).pack(fill="x", pady=(top, 4))

    def _mk_entry(self, parent, var, placeholder):
        e = ctk.CTkEntry(
            parent, textvariable=var, placeholder_text=placeholder,
            height=42, corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 13),
            fg_color=CARD, border_color=BORDER, border_width=1,
            text_color=TEXT)
        e.pack(fill="x")
        return e

    # ── Exam logic ─────────────────────────────────────────────

    def _start_exam(self):
        name = self._name_var.get().strip()
        sid  = self._id_var.get().strip()
        if not name:
            self._show_err("Enter your full name.")
            return
        if not sid:
            self._show_err("Enter your student ID.")
            return

        self._name_entry.configure(state="disabled")
        self._id_entry.configure(state="disabled")
        self._start_btn.configure(state="disabled", text="Monitoring active…")

        self._session_id = database.create_session(name, sid, socket.gethostname())
        self._next_lock_at = settings_manager.get("risk_lock_threshold", 150)

        def _precheck():
            pts = check_ide_preexisting(self._session_id, self._on_risk_event)
            if pts:
                self.after(0, lambda: self._on_risk_event("ide_preexisting", 0))

        threading.Thread(target=_precheck, daemon=True).start()

        self._monitor = MonitorEngine(
            session_id=self._session_id,
            risk_cb=self._on_risk_event)
        self._monitor.start()

        self._lock = ScreenLock(self.master or self, on_unlock=self._on_unlock)

        self._running = True
        self._elapsed = 0
        self._timer_lbl.configure(text_color=SUCCESS)
        self._status_lbl.configure(text="● Monitoring active", text_color=SUCCESS)
        self._tick()

        min_secs = settings_manager.get("min_exam_seconds", 10)
        self.after(min_secs * 1000,
                   lambda: self._end_link.configure(state="normal", text_color=MUTED))

    def _tick(self):
        if not self._running:
            return
        self._elapsed += 1
        h = self._elapsed // 3600
        m = (self._elapsed % 3600) // 60
        s = self._elapsed % 60
        self._timer_lbl.configure(text=f"{h:02d}:{m:02d}:{s:02d}")
        self._tick_job = self.after(1000, self._tick)

    # ── Risk tracking ──────────────────────────────────────────

    def _on_risk_event(self, event_type: str, points: int):
        """Called from any thread. Updates score + schedules UI refresh."""
        self._risk_score += points
        self._risk_events.append((event_type, points))
        self.after(0, lambda et=event_type: self._update_risk_ui(et))

    def _update_risk_ui(self, event_type: str = ""):
        score     = self._risk_score
        threshold = self._next_lock_at

        # Update bar width
        try:
            bar_max  = self._risk_bar_bg.winfo_width()
            fraction = min(score / max(threshold, 1), 1.0)
            new_w    = max(4, int(bar_max * fraction))
        except Exception:
            new_w = 4

        if score <= settings_manager.get("risk_green_max", 20):
            color = SUCCESS
        elif score <= settings_manager.get("risk_yellow_max", 50):
            color = WARNING
        else:
            color = DANGER

        self._risk_bar.configure(fg_color=color, width=new_w)

        # Show toast for this event
        if event_type in _TOASTS:
            msg, toast_color = _TOASTS[event_type]
            self._show_toast(msg, toast_color)

        # ── Trigger lock only if score ≥ current threshold ─────
        if score >= threshold and self._running and not self._ended:
            if not (self._lock and self._lock.is_locked()):
                self._trigger_lock()

    def _trigger_lock(self):
        recent = ", ".join(t for t, _ in self._risk_events[-3:])
        reason = (
            f"Cumulative risk score ({self._risk_score}) exceeded the limit "
            f"({self._next_lock_at}).\n"
            f"Recent events: {recent}"
        )
        database.log_event(self._session_id, "screen_locked",
                           f"risk={self._risk_score}")
        if self._lock:
            self._lock.lock(reason)

    def _on_unlock(self):
        """
        Called after screen-lock PIN verified.
        ── FIX: raise _next_lock_at by 50 above current score
           so the screen does NOT immediately re-lock.
        """
        self._next_lock_at = self._risk_score + 50
        self._status_lbl.configure(text="● Monitoring active", text_color=SUCCESS)
        self._show_toast(f"🔓  Session unlocked by instructor (risk: {self._risk_score})", SUCCESS)

    # ── Toast notifications ────────────────────────────────────

    def _show_toast(self, msg: str, color: str = WARNING):
        """Non-blocking alert strip at bottom — auto-dismisses after 3.5 s."""
        try:
            toast = ctk.CTkFrame(self, fg_color=color, corner_radius=0, height=36)
            toast.place(x=0, rely=1.0, relwidth=1.0, anchor="sw")
            toast.pack_propagate(False)
            ctk.CTkLabel(toast, text=msg,
                         font=ctk.CTkFont("Segoe UI", 11, "bold"),
                         text_color="#ffffff").pack(pady=8)
            self.after(3500, toast.destroy)
        except Exception:
            pass

    # ── Instructor end dialog ──────────────────────────────────

    def _instructor_end_dialog(self):
        if not self._running or self._ended:
            return
        _PINDialog(self, on_success=self._on_instructor_verified)

    def _on_instructor_verified(self):
        self._stop_exam()
        self._show_ended_overlay()
        self.after(700, self._open_dashboard)

    def _stop_exam(self):
        if self._ended:
            return
        self._ended  = True
        self._running = False
        if self._tick_job:
            self.after_cancel(self._tick_job)
        if self._monitor:
            threading.Thread(target=self._monitor.stop, daemon=True).start()
        database.end_session(self._session_id)
        database.log_access("session_ended", f"session_id={self._session_id}")

    def _open_dashboard(self):
        from instructor_app import InstructorApp
        dash = InstructorApp(self.master, focus_session=self._session_id)
        dash.grab_set()

    def _show_ended_overlay(self):
        ov = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        ov.place(relx=0, rely=0, relwidth=1, relheight=1)
        ctk.CTkLabel(ov, text="✓",
                     font=ctk.CTkFont("Segoe UI", 72),
                     text_color=SUCCESS).pack(pady=(120, 6))
        ctk.CTkLabel(ov, text="Session Ended",
                     font=ctk.CTkFont("Segoe UI", 26, "bold"),
                     text_color=TEXT).pack()
        ctk.CTkLabel(ov, text="Opening instructor dashboard…",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=MUTED).pack(pady=(8, 0))

    def _show_err(self, msg: str):
        self._err_lbl.configure(text=f"⚠  {msg}")
        self.after(3500, lambda: self._err_lbl.configure(text=""))

    def _on_close(self):
        if self._running and not self._ended:
            self._show_err("Use 'End Session' with instructor PIN before closing.")
        else:
            self.destroy()


# ─────────────────────────────────────────────────────────────
#  Reusable PIN Dialog
# ─────────────────────────────────────────────────────────────

class _PINDialog(ctk.CTkToplevel):
    def __init__(self, master, on_success: callable,
                 title: str = "Instructor Verification"):
        super().__init__(master)
        self.title(title)
        self.geometry("340x270")
        self.resizable(False, False)
        self.configure(fg_color=BG)
        self.grab_set()
        self._on_success = on_success
        self._attempts   = 0
        self._build_ui()
        self._center(master)
        self.lift()
        self.focus_force()

    def _center(self, master):
        self.update_idletasks()
        mx, my = master.winfo_x(), master.winfo_y()
        mw, mh = master.winfo_width(), master.winfo_height()
        w, h = 340, 270
        self.geometry(f"{w}x{h}+{mx+(mw-w)//2}+{my+(mh-h)//2}")

    def _build_ui(self):
        card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12,
                            border_width=1, border_color=BORDER)
        card.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(card, text="🔐  Instructor PIN Required",
                     font=ctk.CTkFont("Segoe UI", 15, "bold"),
                     text_color=TEXT).pack(pady=(22, 4))
        ctk.CTkLabel(card, text="Enter PIN to continue",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=MUTED).pack(pady=(0, 16))

        self._pin_var = tk.StringVar()
        self._pin_entry = ctk.CTkEntry(
            card, textvariable=self._pin_var, show="●",
            placeholder_text="PIN", justify="center",
            height=46, width=180,
            font=ctk.CTkFont("Segoe UI", 20),
            fg_color=BG, border_color=ACCENT, border_width=1,
            corner_radius=8, text_color=TEXT)
        self._pin_entry.pack()
        self._pin_entry.bind("<Return>", lambda _: self._verify())
        self._pin_entry.focus()

        self._msg_lbl = ctk.CTkLabel(card, text="",
                                      font=ctk.CTkFont("Segoe UI", 11),
                                      text_color=DANGER)
        self._msg_lbl.pack(pady=(6, 0))

        ctk.CTkButton(
            card, text="Verify", height=42, corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_H,
            command=self._verify).pack(pady=(10, 20), padx=24, fill="x")

    def _verify(self):
        self._attempts += 1
        if security.verify_pin(self._pin_var.get()):
            database.log_access("instructor_auth_ok", f"attempt={self._attempts}")
            self.destroy()
            self._on_success()
        else:
            database.log_access("instructor_auth_fail", f"attempt={self._attempts}")
            self._msg_lbl.configure(
                text=f"Incorrect PIN  ({self._attempts} attempt{'s' if self._attempts>1 else ''})")
            self._pin_var.set("")
            self._pin_entry.focus()
            if self._attempts >= 5:
                self._msg_lbl.configure(text="Too many attempts. Locked for this session.")
                self._pin_entry.configure(state="disabled")
