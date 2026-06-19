# instructor_app.py — ExamGuard v3 — Instructor Dashboard

import tkinter as tk
import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog
import csv, os
from datetime import datetime
from PIL import Image, ImageTk

import database, security, settings_manager
from config import (
    RISK_GREEN_MAX, RISK_YELLOW_MAX, RISK_LOCK_THRESHOLD,
    RISK_W_WINDOW, RISK_W_CLIPBOARD, RISK_W_FILE_COPY,
    RISK_W_USB_INSERT, RISK_W_FILE_ACCESS, RISK_W_IDLE,
)

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

# ── Event palette ──────────────────────────────────────────────
_EV = {
    "window_switch":   ("🖥", "#818cf8", "Window Switch"),
    "clipboard_change":("📋", "#34d399", "Clipboard Copy"),
    "file_copy":       ("📁", "#fb923c", "File(s) Copied"),
    "screenshot":      ("📸", "#f472b6", "Screenshot"),
    "keystroke_count": ("⌨",  MUTED,    "Keystroke Count"),
    "usb_insert":      ("🔌", "#f87171", "USB Inserted"),
    "usb_remove":      ("🔌", MUTED,    "USB Removed"),
    "file_access":     ("📂", "#fbbf24", "File Access"),
    "ide_preexisting": ("⚠",  "#fb923c", "IDE Pre-content"),
    "screen_locked":   ("🔒", DANGER,   "Screen Locked"),
}

# ── Risk weights (mirrors config) ─────────────────────────────
_W = {
    "window_switches":  RISK_W_WINDOW,
    "clipboard_events": RISK_W_CLIPBOARD,
    "file_copies":      RISK_W_FILE_COPY,
    "usb_inserts":      RISK_W_USB_INSERT,
    "file_accesses":    RISK_W_FILE_ACCESS,
}


def _risk_score(s: dict) -> int:
    score = (s.get("window_switches",  0) * RISK_W_WINDOW
           + s.get("clipboard_events", 0) * RISK_W_CLIPBOARD
           + s.get("file_copies",      0) * RISK_W_FILE_COPY
           + s.get("usb_inserts",      0) * RISK_W_USB_INSERT
           + s.get("file_accesses",    0) * RISK_W_FILE_ACCESS)
    if s.get("end_time") and s.get("total_keystrokes", 0) < 50:
        score += RISK_W_IDLE
    return score


def _risk_tag(score: int) -> str:
    if score <= RISK_GREEN_MAX:  return "green"
    if score <= RISK_YELLOW_MAX: return "yellow"
    return "red"


def _risk_color(score: int) -> str:
    if score <= RISK_GREEN_MAX:  return SUCCESS
    if score <= RISK_YELLOW_MAX: return WARNING
    return DANGER


def _dur(start, end) -> str:
    try:
        fmt = "%Y-%m-%d %H:%M:%S"
        t0 = datetime.strptime(start, fmt)
        t1 = datetime.strptime(end,   fmt) if end else datetime.now()
        d  = int((t1 - t0).total_seconds())
        return f"{d//3600:02d}:{(d%3600)//60:02d}:{d%60:02d}"
    except Exception:
        return "—"


def _rel(start, ts) -> str:
    try:
        fmt = "%Y-%m-%d %H:%M:%S"
        d = int((datetime.strptime(ts, fmt) - datetime.strptime(start, fmt)).total_seconds())
        if d < 0: d = 0
        return f"{d//3600:02d}:{(d%3600)//60:02d}:{d%60:02d}"
    except Exception:
        return "——"


# ─────────────────────────────────────────────────────────────
class InstructorApp(ctk.CTkToplevel):
    def __init__(self, master=None, focus_session: int | None = None):
        super().__init__(master)
        self.title("ExamGuard — Instructor Dashboard")
        self.geometry("1180x740")
        self.minsize(980, 620)
        self.configure(fg_color=BG)

        self._sessions: list[dict] = []
        self._selected: dict | None = None
        self._focus_session = focus_session

        self._build_ui()
        self._load_sessions()
        self.lift()
        self.focus_force()

    # ── Build UI ───────────────────────────────────────────────

    def _build_ui(self):
        # Header
        bar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=54)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        ctk.CTkLabel(bar, text="🛡  ExamGuard",
                     font=ctk.CTkFont("Segoe UI", 15, "bold"),
                     text_color=ACCENT).pack(side="left", padx=20)
        ctk.CTkLabel(bar, text="Instructor Dashboard",
                     font=ctk.CTkFont("Segoe UI", 11), text_color=MUTED).pack(side="left")

        rc = ctk.CTkFrame(bar, fg_color="transparent")
        rc.pack(side="right", padx=14, pady=10)
        self._filter_var = tk.StringVar(value="All Sessions")
        ctk.CTkOptionMenu(rc, variable=self._filter_var,
                          values=["All Sessions", "Today's Exams"],
                          width=148, height=34,
                          fg_color=CARD2, button_color=ACCENT,
                          button_hover_color=ACCENT_H,
                          command=lambda _: self._load_sessions()).pack(side="left", padx=(0, 8))
        ctk.CTkButton(rc, text="⟳  Refresh", width=90, height=34, corner_radius=8,
                      fg_color=CARD2, hover_color=BORDER,
                      border_width=1, border_color=BORDER,
                      command=self._load_sessions).pack(side="left")

        # Tamper banner (hidden until needed)
        self._tamper_bar = ctk.CTkFrame(self, fg_color="#7c2d12", corner_radius=0, height=0)
        self._tamper_bar.pack(fill="x")
        self._tamper_bar.pack_propagate(False)
        self._tamper_lbl = ctk.CTkLabel(
            self._tamper_bar,
            text="",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            text_color="#fef2f2")
        self._tamper_lbl.pack(pady=7, padx=16)

        # Body
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=(10, 0))
        body.columnconfigure(0, weight=38)
        body.columnconfigure(1, weight=62)
        body.rowconfigure(0, weight=1)

        self._build_left(body)
        self._build_right(body)
        self._build_bottom()

    # ── Left panel ─────────────────────────────────────────────

    def _build_left(self, parent):
        frame = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=10,
                             border_width=1, border_color=BORDER)
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        ctk.CTkLabel(frame, text="Sessions",
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color=LABEL, anchor="w").pack(fill="x", padx=14, pady=(12, 8))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("EG.Treeview",
                        background=CARD, foreground=TEXT, fieldbackground=CARD,
                        rowheight=30, font=("Segoe UI", 10), borderwidth=0)
        style.configure("EG.Treeview.Heading",
                        background="#16181f", foreground=ACCENT,
                        font=("Segoe UI", 10, "bold"), borderwidth=0, relief="flat")
        style.map("EG.Treeview",
                  background=[("selected", "#312e81")],
                  foreground=[("selected", "#ffffff")])

        cols = ("name", "id", "dur", "ws", "clip", "usb", "risk")
        self._tree = ttk.Treeview(frame, columns=cols, show="headings",
                                   style="EG.Treeview", selectmode="browse")
        for col, heading, w in [
            ("name", "Name",     112), ("id",   "ID",      80),
            ("dur",  "Duration",  68), ("ws",   "Win",     36),
            ("clip", "Clip",      36), ("usb",  "USB",     36),
            ("risk", "Risk",      46),
        ]:
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=w, minwidth=28,
                              anchor="w" if col == "name" else "center")

        self._tree.tag_configure("green",  foreground="#4ade80", background="#052e16")
        self._tree.tag_configure("yellow", foreground="#fbbf24", background="#451a03")
        self._tree.tag_configure("red",    foreground="#f87171", background="#450a0a")
        self._tree.tag_configure("active", foreground="#93c5fd")

        sb = ttk.Scrollbar(frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=(0, 10))
        sb.pack(side="right", fill="y", pady=(0, 10), padx=(0, 8))
        self._tree.bind("<<TreeviewSelect>>", self._on_select)

    # ── Right panel ────────────────────────────────────────────

    def _build_right(self, parent):
        self._right = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=10,
                                   border_width=1, border_color=BORDER)
        self._right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self._right.columnconfigure(0, weight=1)
        self._right.rowconfigure(3, weight=1)   # row 3 = timeline (expandable)

        # Info label  (row 0)
        self._info_var = tk.StringVar(value="Select a student session")
        ctk.CTkLabel(self._right, textvariable=self._info_var,
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color=TEXT, anchor="w",
                     wraplength=700).grid(row=0, column=0, sticky="ew",
                                          padx=16, pady=(14, 6))

        # Stats strip  (row 1)
        self._stats_frame = ctk.CTkFrame(self._right, fg_color=BG, corner_radius=8)
        self._stats_frame.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 6))
        self._stat_lbl: dict[str, ctk.CTkLabel] = {}
        for key, icon, lbl in [
            ("keystrokes",      "⌨", "Keystrokes"),
            ("window_switches", "🖥", "Win"),
            ("clipboard_events","📋", "Clipboard"),
            ("file_copies",     "📁", "Files"),
            ("usb_inserts",     "🔌", "USB"),
            ("file_accesses",   "📂", "Ext. Files"),
        ]:
            col = ctk.CTkFrame(self._stats_frame, fg_color="transparent")
            col.pack(side="left", expand=True, pady=8)
            v = ctk.CTkLabel(col, text="—", font=ctk.CTkFont("Segoe UI", 17, "bold"),
                             text_color=ACCENT)
            v.pack()
            ctk.CTkLabel(col, text=f"{icon} {lbl}",
                         font=ctk.CTkFont("Segoe UI", 9), text_color=MUTED).pack()
            self._stat_lbl[key] = v

        # Risk score card  (row 2) — placeholder, replaced on select
        self._risk_card_frame = ctk.CTkFrame(self._right, fg_color="transparent", height=0)
        self._risk_card_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 4))

        # Timeline  (row 3)
        ctk.CTkLabel(self._right, text="Event Timeline",
                     font=ctk.CTkFont("Segoe UI", 11, "bold"),
                     text_color=MUTED, anchor="w"
                     ).grid(row=3, column=0, sticky="nw", padx=16, pady=(0, 4))

        self._timeline = ctk.CTkScrollableFrame(
            self._right, fg_color=BG, corner_radius=8)
        self._timeline.grid(row=4, column=0, sticky="nsew", padx=16, pady=(0, 14))
        self._right.rowconfigure(4, weight=1)

        ctk.CTkLabel(self._timeline, text="Select a student to view their timeline.",
                     font=ctk.CTkFont("Segoe UI", 11), text_color=MUTED).pack(pady=40)

    # ── Bottom bar ─────────────────────────────────────────────

    def _build_bottom(self):
        bar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0,
                           border_width=1, border_color=BORDER, height=52)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        def _btn(parent, text, cmd, danger=False):
            return ctk.CTkButton(
                parent, text=text, height=34, corner_radius=8,
                font=ctk.CTkFont("Segoe UI", 11),
                fg_color=("#7f1d1d" if danger else CARD2),
                hover_color=("#991b1b" if danger else BORDER),
                border_width=0 if danger else 1, border_color=BORDER,
                command=cmd)

        lf = ctk.CTkFrame(bar, fg_color="transparent")
        lf.pack(side="left", padx=12, pady=9)
        _btn(lf, "📸  Screenshots",  self._view_screenshots).pack(side="left", padx=(0, 6))
        _btn(lf, "📊  Export CSV",   self._export_csv).pack(side="left", padx=(0, 6))
        _btn(lf, "📋  Access Log",   self._show_access_log).pack(side="left")

        rf = ctk.CTkFrame(bar, fg_color="transparent")
        rf.pack(side="right", padx=12, pady=9)
        _btn(rf, "⚙  Settings",            self._show_settings).pack(side="right", padx=(6, 0))
        _btn(rf, "🗑  Clear Old (30+ days)", self._clear_old, danger=True).pack(side="right")

    def _show_settings(self):
        _SettingsDialog(self)

    # ── Data loading ───────────────────────────────────────────

    def _load_sessions(self):
        self._sessions = database.get_sessions_with_stats()
        if self._filter_var.get() == "Today's Exams":
            today = datetime.now().strftime("%Y-%m-%d")
            self._sessions = [s for s in self._sessions
                              if (s.get("start_time") or "").startswith(today)]

        for item in self._tree.get_children():
            self._tree.delete(item)

        for s in self._sessions:
            rs  = _risk_score(s)
            tag = _risk_tag(rs)
            if not s.get("end_time"):
                tag = "active"
            self._tree.insert("", "end", iid=str(s["id"]), tags=(tag,),
                values=(
                    s.get("student_name", "")[:16],
                    s.get("student_id",   "")[:12],
                    _dur(s.get("start_time", ""), s.get("end_time")),
                    s.get("window_switches",  0),
                    s.get("clipboard_events", 0),
                    s.get("usb_inserts",      0),
                    rs,
                ))

        if self._focus_session:
            iid = str(self._focus_session)
            if self._tree.exists(iid):
                self._tree.selection_set(iid)
                self._tree.see(iid)
            self._focus_session = None

    def _on_select(self, _=None):
        sel = self._tree.selection()
        if not sel:
            return
        self._selected = next((s for s in self._sessions if s["id"] == int(sel[0])), None)
        if self._selected:
            self._load_detail()

    # ── Detail panel ───────────────────────────────────────────

    def _load_detail(self):
        s   = self._selected
        dur = _dur(s.get("start_time", ""), s.get("end_time"))
        status = "ACTIVE" if not s.get("end_time") else "Ended"
        self._info_var.set(
            f"{s['student_name']}  ·  {s['student_id']}  ·  "
            f"{dur}  ·  PC: {s.get('pc_hostname','?')}  ·  {status}"
        )

        rs = _risk_score(s)
        for key, val, color in [
            ("keystrokes",       s.get("total_keystrokes", 0), ACCENT),
            ("window_switches",  s.get("window_switches",  0), _risk_color(s.get("window_switches",0)*RISK_W_WINDOW)),
            ("clipboard_events", s.get("clipboard_events", 0), _risk_color(s.get("clipboard_events",0)*RISK_W_CLIPBOARD)),
            ("file_copies",      s.get("file_copies",      0), DANGER if s.get("file_copies",0) > 0 else MUTED),
            ("usb_inserts",      s.get("usb_inserts",      0), DANGER if s.get("usb_inserts",0) > 0 else MUTED),
            ("file_accesses",    s.get("file_accesses",    0), WARNING if s.get("file_accesses",0) > 0 else MUTED),
        ]:
            self._stat_lbl[key].configure(text=str(val), text_color=color)

        self._render_risk_card(rs, s)

        # Timeline
        for w in self._timeline.winfo_children():
            w.destroy()

        events = database.get_events_for_session(s["id"], decrypt_sensitive=True)
        tampered = sum(1 for e in events if e.get("tampered"))
        self._show_tamper(tampered)

        if not events:
            ctk.CTkLabel(self._timeline, text="No events recorded.",
                         font=ctk.CTkFont("Segoe UI", 11), text_color=MUTED).pack(pady=40)
            return

        start_ts = s.get("start_time", "")
        for ev in events:
            self._render_event(ev, start_ts)

    # ── Risk card ──────────────────────────────────────────────

    def _render_risk_card(self, score: int, s: dict):
        for w in self._risk_card_frame.winfo_children():
            w.destroy()
        self._risk_card_frame.configure(height=44)

        color = _risk_color(score)
        label = ("Low Risk" if score <= RISK_GREEN_MAX else
                 "Suspicious" if score <= RISK_YELLOW_MAX else "High Risk")

        inner = ctk.CTkFrame(self._risk_card_frame, fg_color=BG, corner_radius=8,
                             border_width=1, border_color=BORDER)
        inner.pack(fill="x")
        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=8)

        ctk.CTkLabel(row, text="Risk Score", font=ctk.CTkFont("Segoe UI", 10),
                     text_color=MUTED).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(row, text=str(score),
                     font=ctk.CTkFont("Segoe UI", 18, "bold"),
                     text_color=color).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(row, text=f"({label})  ·  Lock at {RISK_LOCK_THRESHOLD}",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=MUTED).pack(side="left", padx=(0, 16))
        ctk.CTkButton(row, text="How calculated? ▸",
                      font=ctk.CTkFont("Segoe UI", 10), text_color=ACCENT,
                      fg_color="transparent", hover_color=CARD2, height=24, corner_radius=6,
                      command=lambda: _RiskDialog(self, s)).pack(side="left")

    # ── Event row ──────────────────────────────────────────────

    def _render_event(self, ev: dict, start_ts: str):
        etype    = ev.get("event_type", "")
        icon, color, lbl = _EV.get(etype, ("•", MUTED, etype))
        detail   = ev.get("detail_plain", ev.get("detail", "")) or ""
        tampered = ev.get("tampered", False)
        rel      = _rel(start_ts, ev.get("timestamp", ""))

        row = ctk.CTkFrame(self._timeline,
                           fg_color="#1a0a0a" if tampered else CARD2,
                           corner_radius=7, border_width=1,
                           border_color="#7f1d1d" if tampered else BORDER)
        row.pack(fill="x", pady=2)
        row.columnconfigure(3, weight=1)

        ctk.CTkLabel(row, text=rel, width=68,
                     font=ctk.CTkFont("Courier New", 11),
                     text_color=MUTED, anchor="w").grid(row=0, column=0, padx=(10, 4), pady=7)

        badge = ctk.CTkFrame(row, fg_color=BG, corner_radius=5, width=22, height=22)
        badge.grid(row=0, column=1, padx=(0, 6))
        badge.pack_propagate(False)
        ctk.CTkLabel(badge, text=icon, font=ctk.CTkFont("Segoe UI", 11),
                     text_color=color).place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(row, text=lbl, width=118,
                     font=ctk.CTkFont("Segoe UI", 10, "bold"),
                     text_color=color, anchor="w").grid(row=0, column=2, padx=(0, 8))

        if etype == "screenshot" and detail and os.path.exists(detail):
            ctk.CTkButton(
                row, text=f"📷 View  [{ev.get('timestamp','')}]",
                font=ctk.CTkFont("Segoe UI", 10), text_color="#f472b6",
                fg_color="transparent", hover_color=BG, anchor="w", height=26,
                command=lambda p=detail: _ScreenshotViewer(self, p)
            ).grid(row=0, column=3, sticky="ew", padx=(0, 10))
        else:
            text_color = "#fca5a5" if tampered else TEXT
            disp = detail[:120] + ("…" if len(detail) > 120 else "")
            ctk.CTkLabel(row, text=disp,
                         font=ctk.CTkFont("Segoe UI", 10),
                         text_color=text_color, anchor="w",
                         wraplength=380, justify="left"
                         ).grid(row=0, column=3, sticky="ew", padx=(0, 10), pady=6)

        if tampered:
            ctk.CTkLabel(row, text="⚠ TAMPERED",
                         font=ctk.CTkFont("Segoe UI", 9, "bold"),
                         text_color=DANGER).grid(row=0, column=4, padx=(0, 8))

    # ── Tamper banner ──────────────────────────────────────────

    def _show_tamper(self, count: int):
        if count > 0:
            self._tamper_bar.configure(height=36)
            self._tamper_lbl.configure(
                text=f"⚠  INTEGRITY ALERT — {count} record(s) show signs of external tampering.")
        else:
            self._tamper_bar.configure(height=0)

    # ── Actions ────────────────────────────────────────────────

    def _view_screenshots(self):
        if not self._selected:
            messagebox.showinfo("Info", "Select a student session first.")
            return
        events = database.get_events_for_session(self._selected["id"], decrypt_sensitive=True)
        shots  = [e["detail_plain"] for e in events
                  if e["event_type"] == "screenshot" and e.get("detail_plain")]
        if not shots:
            messagebox.showinfo("No Screenshots", "No screenshots for this session.")
            return
        _Gallery(self, shots)

    def _export_csv(self):
        if not self._selected:
            messagebox.showinfo("Info", "Select a session first.")
            return
        s      = self._selected
        events = database.get_events_for_session(s["id"], decrypt_sensitive=True)
        fname  = f"examguard_{s['student_name'].replace(' ','_')}_{s['student_id']}.csv"
        path   = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")],
            initialfile=fname, title="Save Report")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["ExamGuard Session Report"])
                for k, v in [
                    ("Student", s["student_name"]), ("ID", s["student_id"]),
                    ("PC", s.get("pc_hostname","")), ("Start", s.get("start_time","")),
                    ("End", s.get("end_time","")),   ("Keystrokes", s.get("total_keystrokes",0)),
                    ("Risk Score", _risk_score(s)),
                ]:
                    w.writerow([k, v])
                w.writerow([])
                w.writerow(["Timestamp", "Event Type", "Detail", "Tampered"])
                for ev in events:
                    w.writerow([ev.get("timestamp",""), ev.get("event_type",""),
                                ev.get("detail_plain",""),
                                "YES" if ev.get("tampered") else "no"])
            database.log_access("export_csv", f"session_id={s['id']}")
            messagebox.showinfo("Exported", f"Saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _show_access_log(self):
        _AccessLogViewer(self)

    def _clear_old(self):
        if messagebox.askyesno("Confirm",
                               "Delete all sessions older than 30 days?\nThis cannot be undone.",
                               icon="warning"):
            database.delete_old_sessions(30)
            database.log_access("clear_old_sessions")
            self._load_sessions()
            messagebox.showinfo("Done", "Old sessions deleted.")


# ─────────────────────────────────────────────────────────────
#  Risk breakdown dialog
# ─────────────────────────────────────────────────────────────

class _RiskDialog(ctk.CTkToplevel):
    def __init__(self, master, s: dict):
        super().__init__(master)
        self.title("Risk Score — Breakdown")
        self.resizable(False, False)
        self.configure(fg_color=BG)
        score = _risk_score(s)
        color = _risk_color(score)
        label = ("Low Risk" if score <= RISK_GREEN_MAX else
                 "Suspicious" if score <= RISK_YELLOW_MAX else "High Risk")

        hdr = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=58)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="Risk Score Breakdown",
                     font=ctk.CTkFont("Segoe UI", 14, "bold"),
                     text_color=TEXT).pack(side="left", padx=20, pady=16)
        ctk.CTkLabel(hdr, text=f"{score}  —  {label}",
                     font=ctk.CTkFont("Segoe UI", 13, "bold"),
                     text_color=color).pack(side="right", padx=20)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=16)

        rows = [
            ("Window Switches",  s.get("window_switches",0),  RISK_W_WINDOW,    "Alt-Tab is normal but frequent switching is suspicious"),
            ("Clipboard Copies", s.get("clipboard_events",0), RISK_W_CLIPBOARD, "Pasting code from outside the IDE"),
            ("File Copies",      s.get("file_copies",0),      RISK_W_FILE_COPY, "File paths copied to clipboard"),
            ("USB Inserts",      s.get("usb_inserts",0),      RISK_W_USB_INSERT,"USB/pendrive plugged in during exam"),
            ("Ext. File Access", s.get("file_accesses",0),    RISK_W_FILE_ACCESS,"Code files opened from external sources"),
        ]
        total = 0
        for lbl, cnt, w, note in rows:
            pts = cnt * w
            total += pts
            rf = ctk.CTkFrame(body, fg_color=CARD2, corner_radius=8,
                              border_width=1, border_color=BORDER)
            rf.pack(fill="x", pady=3)
            rf.columnconfigure(1, weight=1)
            pc = _risk_color(pts) if pts > 0 else SUCCESS
            pf = ctk.CTkFrame(rf, fg_color=BG, corner_radius=6, width=52, height=40)
            pf.grid(row=0, column=0, rowspan=2, padx=10, pady=8, sticky="ns")
            pf.pack_propagate(False)
            ctk.CTkLabel(pf, text=f"+{pts}" if pts else "0",
                         font=ctk.CTkFont("Segoe UI", 13, "bold"),
                         text_color=pc).place(relx=0.5, rely=0.5, anchor="center")
            ctk.CTkLabel(rf, text=f"{lbl}  (×{w})",
                         font=ctk.CTkFont("Segoe UI", 11, "bold"),
                         text_color=TEXT, anchor="w"
                         ).grid(row=0, column=1, sticky="sw", padx=(0, 12), pady=(8, 0))
            ctk.CTkLabel(rf, text=f"{cnt} event{'s' if cnt!=1 else ''}  —  {note}",
                         font=ctk.CTkFont("Segoe UI", 9),
                         text_color=MUTED, anchor="w"
                         ).grid(row=1, column=1, sticky="nw", padx=(0, 12), pady=(0, 8))

        if s.get("end_time") and s.get("total_keystrokes", 0) < 50:
            total += RISK_W_IDLE
            rf = ctk.CTkFrame(body, fg_color=CARD2, corner_radius=8,
                              border_width=1, border_color=BORDER)
            rf.pack(fill="x", pady=3)
            rf.columnconfigure(1, weight=1)
            pf = ctk.CTkFrame(rf, fg_color=BG, corner_radius=6, width=52, height=40)
            pf.grid(row=0, column=0, rowspan=2, padx=10, pady=8, sticky="ns")
            pf.pack_propagate(False)
            ctk.CTkLabel(pf, text=f"+{RISK_W_IDLE}",
                         font=ctk.CTkFont("Segoe UI", 13, "bold"),
                         text_color=WARNING).place(relx=0.5, rely=0.5, anchor="center")
            ctk.CTkLabel(rf, text="Idle Penalty",
                         font=ctk.CTkFont("Segoe UI", 11, "bold"),
                         text_color=TEXT, anchor="w"
                         ).grid(row=0, column=1, sticky="sw", padx=(0,12), pady=(8,0))
            ctk.CTkLabel(rf, text=f"Only {s.get('total_keystrokes',0)} keystrokes — student may not have typed the solution",
                         font=ctk.CTkFont("Segoe UI", 9),
                         text_color=MUTED, anchor="w"
                         ).grid(row=1, column=1, sticky="nw", padx=(0,12), pady=(0,8))

        ctk.CTkFrame(body, fg_color=BORDER, height=1).pack(fill="x", pady=(10, 8))
        tr = ctk.CTkFrame(body, fg_color="transparent")
        tr.pack(fill="x")
        ctk.CTkLabel(tr, text="Total  =",
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color=LABEL).pack(side="left")
        ctk.CTkLabel(tr, text=f"  {total}  ({label})",
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color=color).pack(side="left")

        leg = ctk.CTkFrame(body, fg_color=CARD2, corner_radius=8)
        leg.pack(fill="x", pady=(12, 0))
        ctk.CTkLabel(leg,
                     text=f"🟢 0–{RISK_GREEN_MAX} = Low    "
                          f"🟡 {RISK_GREEN_MAX+1}–{RISK_YELLOW_MAX} = Suspicious    "
                          f"🔴 {RISK_YELLOW_MAX+1}+ = High Risk    "
                          f"🔒 {RISK_LOCK_THRESHOLD}+ = Screen Locked",
                     font=ctk.CTkFont("Segoe UI", 9), text_color=MUTED
                     ).pack(pady=8, padx=12)

        self.update_idletasks()
        w = 480
        h = self.winfo_reqheight() + 24
        mx, my = master.winfo_x(), master.winfo_y()
        mw, mh = master.winfo_width(), master.winfo_height()
        self.geometry(f"{w}x{h}+{mx+(mw-w)//2}+{my+(mh-h)//2}")
        self.grab_set(); self.lift(); self.focus_force()


# ─────────────────────────────────────────────────────────────
#  Screenshot viewer / gallery
# ─────────────────────────────────────────────────────────────

class _ScreenshotViewer(ctk.CTkToplevel):
    def __init__(self, master, path: str):
        super().__init__(master)
        self.title(f"Screenshot — {os.path.basename(path)}")
        self.configure(fg_color=BG)
        self.geometry("900x580")
        img = Image.open(path)
        img.thumbnail((860, 520), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(img)
        tk.Label(self, image=self._photo, bg=BG).pack(expand=True, fill="both", padx=16, pady=16)
        ctk.CTkLabel(self, text=path, font=ctk.CTkFont("Segoe UI", 9),
                     text_color=MUTED).pack(pady=(0, 10))
        self.lift(); self.focus_force()


class _Gallery(ctk.CTkToplevel):
    def __init__(self, master, paths: list[str]):
        super().__init__(master)
        self.title("Screenshot Gallery")
        self.configure(fg_color=BG)
        self.geometry("960x620")
        self._paths = [p for p in paths if os.path.exists(p)]
        self._idx = 0; self._photo = None
        if not self._paths:
            messagebox.showinfo("Info", "No screenshot files found.")
            self.destroy(); return

        bar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=42)
        bar.pack(fill="x"); bar.pack_propagate(False)
        self._title_var = tk.StringVar()
        ctk.CTkLabel(bar, textvariable=self._title_var,
                     font=ctk.CTkFont("Segoe UI", 11), text_color=LABEL
                     ).pack(side="left", padx=16, pady=10)
        nav = ctk.CTkFrame(bar, fg_color="transparent")
        nav.pack(side="right", padx=12, pady=8)
        for text, cmd in [("◀", self._prev), ("▶", self._next)]:
            ctk.CTkButton(nav, text=text, width=34, height=28, corner_radius=6,
                          fg_color=CARD2, hover_color=BORDER,
                          command=cmd).pack(side="left", padx=3)

        self._img_lbl = tk.Label(self, bg=BG)
        self._img_lbl.pack(expand=True, fill="both", padx=16, pady=12)
        self._show(); self.lift(); self.focus_force()

    def _show(self):
        p = self._paths[self._idx]
        self._title_var.set(f"{self._idx+1} / {len(self._paths)}  —  {os.path.basename(p)}")
        img = Image.open(p); img.thumbnail((900, 530), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(img)
        self._img_lbl.configure(image=self._photo)

    def _prev(self): self._idx = (self._idx-1) % len(self._paths); self._show()
    def _next(self): self._idx = (self._idx+1) % len(self._paths); self._show()


# ─────────────────────────────────────────────────────────────
#  Access log viewer
# ─────────────────────────────────────────────────────────────

class _AccessLogViewer(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Instructor Access Log")
        self.geometry("620x430")
        self.configure(fg_color=BG)
        ctk.CTkLabel(self, text="Access Log",
                     font=ctk.CTkFont("Segoe UI", 14, "bold"),
                     text_color=TEXT).pack(pady=(16, 6), padx=20, anchor="w")
        sf = ctk.CTkScrollableFrame(self, fg_color=CARD, corner_radius=8)
        sf.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        logs = database.get_access_log(200)
        if not logs:
            ctk.CTkLabel(sf, text="No access records.",
                         font=ctk.CTkFont("Segoe UI", 11), text_color=MUTED).pack(pady=30)
        else:
            for log in logs:
                row = ctk.CTkFrame(sf, fg_color=BG, corner_radius=6)
                row.pack(fill="x", pady=2)
                ctk.CTkLabel(row, text=log.get("timestamp",""),
                             font=ctk.CTkFont("Courier New", 10),
                             text_color=MUTED, width=138).pack(side="left", padx=(10,6), pady=6)
                ac = DANGER if "fail" in log.get("action","") else SUCCESS
                ctk.CTkLabel(row, text=log.get("action",""),
                             font=ctk.CTkFont("Segoe UI", 10, "bold"),
                             text_color=ac, width=160).pack(side="left", padx=(0,6))
                ctk.CTkLabel(row, text=log.get("detail",""),
                             font=ctk.CTkFont("Segoe UI", 10),
                             text_color=LABEL).pack(side="left", fill="x", padx=(0,10))
        self.lift(); self.focus_force()


# ─────────────────────────────────────────────────────────────
#  Settings Dialog
# ─────────────────────────────────────────────────────────────

class _SettingsDialog(ctk.CTkToplevel):
    """
    Instructor settings panel.
    Sections:
      1. Change PIN
      2. Risk thresholds
      3. Screenshot triggers
    """

    def __init__(self, master):
        super().__init__(master)
        self.title("ExamGuard — Settings")
        self.geometry("520x680")
        self.resizable(False, False)
        self.configure(fg_color=BG)
        self.grab_set()

        self._s = settings_manager.load()   # working copy
        self._vars: dict = {}               # StringVar / BooleanVar per key
        self._msg_lbl: ctk.CTkLabel | None = None

        self._build_ui()
        self._center(master)
        self.lift()
        self.focus_force()

    def _center(self, master):
        self.update_idletasks()
        mx, my = master.winfo_x(), master.winfo_y()
        mw, mh = master.winfo_width(), master.winfo_height()
        w, h = 520, 680
        self.geometry(f"{w}x{h}+{mx+(mw-w)//2}+{my+(mh-h)//2}")

    def _build_ui(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=54)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="⚙  Settings",
                     font=ctk.CTkFont("Segoe UI", 15, "bold"),
                     text_color=ACCENT).pack(side="left", padx=20, pady=14)

        # Scrollable body
        sf = ctk.CTkScrollableFrame(self, fg_color="transparent")
        sf.pack(fill="both", expand=True, padx=20, pady=12)

        # ── Section 1: Change PIN ──────────────────────────────
        self._section(sf, "🔐  Instructor PIN")
        current_card = ctk.CTkFrame(sf, fg_color=CARD2, corner_radius=10,
                                    border_width=1, border_color=BORDER)
        current_card.pack(fill="x", pady=(0, 8))

        for row_label, key, placeholder, show in [
            ("Current PIN",    "_old_pin",     "Enter current PIN",  "●"),
            ("New PIN",        "_new_pin",     "Enter new PIN",      "●"),
            ("Confirm New PIN","_confirm_pin", "Repeat new PIN",     "●"),
        ]:
            r = ctk.CTkFrame(current_card, fg_color="transparent")
            r.pack(fill="x", padx=14, pady=4)
            ctk.CTkLabel(r, text=row_label, width=130, anchor="w",
                         font=ctk.CTkFont("Segoe UI", 11),
                         text_color=LABEL).pack(side="left")
            v = tk.StringVar()
            self._vars[key] = v
            ctk.CTkEntry(r, textvariable=v, show=show,
                         placeholder_text=placeholder,
                         height=36, corner_radius=8,
                         font=ctk.CTkFont("Segoe UI", 12),
                         fg_color=BG, border_color=BORDER, border_width=1,
                         text_color=TEXT).pack(side="left", fill="x", expand=True, padx=(8, 0))

        self._pin_msg = ctk.CTkLabel(current_card, text="",
                                     font=ctk.CTkFont("Segoe UI", 10),
                                     text_color=DANGER)
        self._pin_msg.pack(pady=(0, 4), padx=14, anchor="w")

        ctk.CTkButton(
            current_card, text="Change PIN",
            height=36, corner_radius=8, width=130,
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_H,
            command=self._change_pin
        ).pack(pady=(0, 12), padx=14, anchor="w")

        # ── Section 2: Risk thresholds ─────────────────────────
        self._section(sf, "🎯  Risk Thresholds")
        thresh_card = ctk.CTkFrame(sf, fg_color=CARD2, corner_radius=10,
                                   border_width=1, border_color=BORDER)
        thresh_card.pack(fill="x", pady=(0, 8))

        for lbl, key, note in [
            ("Green ≤ (safe)",      "risk_green_max",      "Score ≤ this → green"),
            ("Yellow ≤ (caution)",  "risk_yellow_max",     "Score ≤ this → yellow; above → red"),
            ("Lock threshold",      "risk_lock_threshold", "Screen locks when score ≥ this"),
        ]:
            r = ctk.CTkFrame(thresh_card, fg_color="transparent")
            r.pack(fill="x", padx=14, pady=6)
            ctk.CTkLabel(r, text=lbl, width=160, anchor="w",
                         font=ctk.CTkFont("Segoe UI", 11),
                         text_color=TEXT).pack(side="left")
            v = tk.StringVar(value=str(self._s.get(key, "")))
            self._vars[key] = v
            ctk.CTkEntry(r, textvariable=v, width=80, height=34,
                         corner_radius=8, font=ctk.CTkFont("Segoe UI", 12),
                         fg_color=BG, border_color=BORDER, border_width=1,
                         text_color=ACCENT, justify="center").pack(side="left", padx=8)
            ctk.CTkLabel(r, text=note, font=ctk.CTkFont("Segoe UI", 9),
                         text_color=MUTED, anchor="w").pack(side="left")

        # ── Section 3: Screenshot triggers ────────────────────
        self._section(sf, "📸  Screenshot Triggers")
        ss_card = ctk.CTkFrame(sf, fg_color=CARD2, corner_radius=10,
                               border_width=1, border_color=BORDER)
        ss_card.pack(fill="x", pady=(0, 8))

        for lbl, key in [
            ("On browser open",     "screenshot_on_browser"),
            ("On USB insertion",    "screenshot_on_usb"),
            ("On code clipboard",   "screenshot_on_clipboard"),
            ("On file copy",        "screenshot_on_file_copy"),
            ("On file access",      "screenshot_on_file_access"),
        ]:
            r = ctk.CTkFrame(ss_card, fg_color="transparent")
            r.pack(fill="x", padx=14, pady=4)
            v = tk.BooleanVar(value=bool(self._s.get(key, True)))
            self._vars[key] = v
            ctk.CTkSwitch(r, text=lbl, variable=v,
                          font=ctk.CTkFont("Segoe UI", 11),
                          text_color=TEXT,
                          button_color=ACCENT,
                          button_hover_color=ACCENT_H,
                          progress_color=ACCENT).pack(side="left")

        # ── Save / Reset ───────────────────────────────────────
        btn_row = ctk.CTkFrame(sf, fg_color="transparent")
        btn_row.pack(fill="x", pady=(12, 4))
        ctk.CTkButton(
            btn_row, text="💾  Save Changes",
            height=42, corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_H,
            command=self._save
        ).pack(side="left", expand=True, fill="x", padx=(0, 6))
        ctk.CTkButton(
            btn_row, text="↺  Reset Defaults",
            height=42, corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 12),
            fg_color=CARD2, hover_color=BORDER,
            border_width=1, border_color=BORDER,
            command=self._reset
        ).pack(side="left", expand=True, fill="x", padx=(6, 0))

        self._msg_lbl = ctk.CTkLabel(sf, text="",
                                     font=ctk.CTkFont("Segoe UI", 11),
                                     text_color=SUCCESS)
        self._msg_lbl.pack(pady=(6, 0))

    def _section(self, parent, title: str):
        ctk.CTkLabel(parent, text=title,
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color=LABEL, anchor="w").pack(fill="x", pady=(12, 4))

    # ── Actions ────────────────────────────────────────────────

    def _change_pin(self):
        old = self._vars["_old_pin"].get().strip()
        new = self._vars["_new_pin"].get().strip()
        cnf = self._vars["_confirm_pin"].get().strip()

        if not security.verify_pin(old):
            self._pin_msg.configure(text="Current PIN is incorrect.", text_color=DANGER)
            return
        if len(new) < 4:
            self._pin_msg.configure(text="New PIN must be at least 4 characters.", text_color=DANGER)
            return
        if new != cnf:
            self._pin_msg.configure(text="New PINs do not match.", text_color=DANGER)
            return

        settings_manager.set_value("instructor_pin", new)
        database.log_access("pin_changed", "Instructor changed PIN via Settings")
        self._pin_msg.configure(text="✓  PIN changed successfully.", text_color=SUCCESS)
        for k in ("_old_pin", "_new_pin", "_confirm_pin"):
            self._vars[k].set("")

    def _save(self):
        updated = dict(self._s)
        # Numeric threshold fields
        for key in ("risk_green_max", "risk_yellow_max", "risk_lock_threshold"):
            try:
                updated[key] = int(self._vars[key].get())
            except ValueError:
                if self._msg_lbl:
                    self._msg_lbl.configure(
                        text=f"Invalid number for '{key}'.", text_color=DANGER)
                return
        # Boolean fields
        for key in ("screenshot_on_browser", "screenshot_on_usb",
                    "screenshot_on_clipboard", "screenshot_on_file_copy",
                    "screenshot_on_file_access"):
            updated[key] = bool(self._vars[key].get())

        settings_manager.save(updated)
        database.log_access("settings_saved")
        if self._msg_lbl:
            self._msg_lbl.configure(text="✓  Settings saved.", text_color=SUCCESS)

    def _reset(self):
        settings_manager.reset()
        database.log_access("settings_reset")
        # Reload vars
        s = settings_manager.load()
        for key in ("risk_green_max", "risk_yellow_max", "risk_lock_threshold"):
            if key in self._vars:
                self._vars[key].set(str(s.get(key, "")))
        for key in ("screenshot_on_browser", "screenshot_on_usb",
                    "screenshot_on_clipboard", "screenshot_on_file_copy",
                    "screenshot_on_file_access"):
            if key in self._vars:
                self._vars[key].set(bool(s.get(key, True)))
        if self._msg_lbl:
            self._msg_lbl.configure(text="✓  Reset to defaults.", text_color=SUCCESS)
