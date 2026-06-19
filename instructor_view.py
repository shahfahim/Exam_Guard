# instructor_view.py — ExamGuard v4 — Instructor Dashboard (CTkFrame, single-window)

import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog, messagebox
import csv, os
from datetime import datetime

import database, security, settings_manager
from theme import *
from config import (
    RISK_W_WINDOW, RISK_W_CLIPBOARD, RISK_W_FILE_COPY,
    RISK_W_USB_INSERT, RISK_W_FILE_ACCESS, RISK_W_IDLE,
)

# ── Event display map ─────────────────────────────────────────
_EV = {
    "window_switch":   ("🖥", INFO,    "Window Switch"),
    "clipboard_change":("📋", SUCCESS, "Clipboard Copy"),
    "file_copy":       ("📁", WARNING, "File(s) Copied"),
    "screenshot":      ("📸", "#F472B6", "Screenshot"),
    "keystroke_count": ("⌨",  MUTED,  "Keystroke Count"),
    "usb_insert":      ("🔌", DANGER, "USB Inserted"),
    "usb_remove":      ("🔌", MUTED,  "USB Removed"),
    "file_access":     ("📂", WARNING, "File Access"),
    "ide_preexisting": ("⚠",  WARNING, "IDE Pre-content"),
    "screen_locked":   ("🔒", DANGER, "Screen Locked"),
}

_ENCRYPT_TYPES = {
    "clipboard_change", "screenshot", "file_copy",
    "usb_insert", "file_access", "ide_preexisting",
}


def _risk(s: dict) -> int:
    sc = (s.get("window_switches",  0) * RISK_W_WINDOW
        + s.get("clipboard_events", 0) * RISK_W_CLIPBOARD
        + s.get("file_copies",      0) * RISK_W_FILE_COPY
        + s.get("usb_inserts",      0) * RISK_W_USB_INSERT
        + s.get("file_accesses",    0) * RISK_W_FILE_ACCESS)
    if s.get("end_time") and s.get("total_keystrokes", 0) < 50:
        sc += RISK_W_IDLE
    return sc


def _risk_color(score: int) -> str:
    gm = settings_manager.get("risk_green_max",  20)
    ym = settings_manager.get("risk_yellow_max", 50)
    if score <= gm:  return SUCCESS
    if score <= ym:  return WARNING
    return DANGER


def _dur(start, end=None) -> str:
    try:
        fmt = "%Y-%m-%d %H:%M:%S"
        t0  = datetime.strptime(start, fmt)
        t1  = datetime.strptime(end, fmt) if end else datetime.now()
        d   = int((t1 - t0).total_seconds())
        return f"{d//3600:02d}:{(d%3600)//60:02d}:{d%60:02d}"
    except Exception:
        return "—"


def _rel(start, ts) -> str:
    try:
        fmt = "%Y-%m-%d %H:%M:%S"
        d = int((datetime.strptime(ts, fmt) - datetime.strptime(start, fmt)).total_seconds())
        return f"+{max(d,0)//60:02d}:{max(d,0)%60:02d}"
    except Exception:
        return "——"


# ─────────────────────────────────────────────────────────────
class InstructorView(ctk.CTkFrame):

    def __init__(self, parent, app, focus_session: int | None = None):
        super().__init__(parent, fg_color=BG)
        self._app          = app
        self._sessions:  list  = []
        self._selected:  dict | None = None
        self._focus_sid = focus_session
        self._session_cards: dict = {}   # session_id → card frame
        self._build()
        self._load_sessions()

    # ── Layout ─────────────────────────────────────────────────

    def _build(self):
        # ── Header ─────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=56)
        hdr.pack(fill="x"); hdr.pack_propagate(False)

        ctk.CTkLabel(hdr, text="Instructor Dashboard",
                     font=ctk.CTkFont("Segoe UI", 16, "bold"), text_color=TEXT
                     ).pack(side="left", padx=24, pady=16)

        rc = ctk.CTkFrame(hdr, fg_color="transparent")
        rc.pack(side="right", padx=16, pady=12)

        self._filter_var = tk.StringVar(value="All Sessions")
        ctk.CTkOptionMenu(rc, variable=self._filter_var,
                          values=["All Sessions", "Today's Exams"],
                          width=140, height=32, corner_radius=8,
                          fg_color=CARD2, button_color=ACCENT,
                          button_hover_color=ACCENT_H, text_color=TEXT,
                          command=lambda _: self._load_sessions()
                          ).pack(side="left", padx=(0, 6))

        self._btn(rc, "⟳  Refresh", self._load_sessions, w=90).pack(side="left", padx=(0, 6))
        self._btn(rc, "📊  Export", self._export_csv, w=80).pack(side="left", padx=(0, 6))
        self._btn(rc, "📋  Log",    self._show_access_log, w=70).pack(side="left")

        # ── Tamper banner (hidden by default) ──────────────────
        self._tamper_bar = ctk.CTkFrame(self, fg_color="#7C2D12", corner_radius=0, height=0)
        self._tamper_bar.pack(fill="x"); self._tamper_bar.pack_propagate(False)
        self._tamper_lbl = ctk.CTkLabel(self._tamper_bar, text="",
                                         font=ctk.CTkFont("Segoe UI", 11, "bold"),
                                         text_color="#FEF2F2")
        self._tamper_lbl.pack(pady=7, padx=16)

        ctk.CTkFrame(self, fg_color=BORDER, height=1).pack(fill="x")

        # ── Split body ─────────────────────────────────────────
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=36, minsize=300)
        body.columnconfigure(1, weight=64)
        body.rowconfigure(0, weight=1)

        self._build_left(body)
        self._build_right(body)

    def _btn(self, parent, text, cmd, w=None, danger=False):
        kw = dict(height=32, corner_radius=8, font=ctk.CTkFont("Segoe UI", 11),
                  fg_color="#7F1D1D" if danger else CARD2,
                  hover_color="#991B1B" if danger else BORDER,
                  border_width=0 if danger else 1, border_color=BORDER,
                  command=cmd)
        if w: kw["width"] = w
        return ctk.CTkButton(parent, text=text, **kw)

    # ── Left: session list ─────────────────────────────────────

    def _build_left(self, parent):
        lf = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=0)
        lf.grid(row=0, column=0, sticky="nsew")
        lf.rowconfigure(1, weight=1)
        lf.columnconfigure(0, weight=1)

        # Search + count bar
        top = ctk.CTkFrame(lf, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=14, pady=12)
        self._count_lbl = ctk.CTkLabel(top, text="",
                                        font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=LABEL)
        self._count_lbl.pack(side="left")
        self._btn(top, "🗑  Clear Old", self._clear_old, danger=True).pack(side="right")

        # Session list
        self._list_frame = ctk.CTkScrollableFrame(lf, fg_color="transparent")
        self._list_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self._list_frame.columnconfigure(0, weight=1)

        ctk.CTkFrame(parent, fg_color=BORDER, width=1).grid(
            row=0, column=0, sticky="nse")

    # ── Right: detail panel ────────────────────────────────────

    def _build_right(self, parent):
        self._right = ctk.CTkFrame(parent, fg_color=BG, corner_radius=0)
        self._right.grid(row=0, column=1, sticky="nsew")
        self._right.rowconfigure(2, weight=1)
        self._right.columnconfigure(0, weight=1)

        # Placeholder
        self._detail_placeholder = ctk.CTkFrame(self._right, fg_color="transparent")
        self._detail_placeholder.grid(row=0, column=0, rowspan=3, sticky="nsew")
        cf = ctk.CTkFrame(self._detail_placeholder, fg_color="transparent")
        cf.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(cf, text="📊", font=ctk.CTkFont("Segoe UI", 48)).pack()
        ctk.CTkLabel(cf, text="Select a session",
                     font=ctk.CTkFont("Segoe UI", 16, "bold"), text_color=MUTED).pack(pady=(8, 2))
        ctk.CTkLabel(cf, text="Click any session in the list to view details.",
                     font=ctk.CTkFont("Segoe UI", 11), text_color=SUBTLE).pack()

        # Detail widgets (hidden until session selected)
        self._detail_header = ctk.CTkFrame(self._right, fg_color=CARD, corner_radius=0, height=0)
        self._detail_header.grid(row=0, column=0, sticky="ew"); self._detail_header.pack_propagate(False)

        self._detail_stats = ctk.CTkFrame(self._right, fg_color=CARD2, corner_radius=0, height=0)
        self._detail_stats.grid(row=1, column=0, sticky="ew"); self._detail_stats.pack_propagate(False)

        self._detail_timeline = ctk.CTkScrollableFrame(self._right, fg_color="transparent")
        # grid row=2 with weight=1 (added when session selected)

    # ── Data loading ───────────────────────────────────────────

    def _load_sessions(self):
        self._sessions = database.get_sessions_with_stats()
        if self._filter_var.get() == "Today's Exams":
            today = datetime.now().strftime("%Y-%m-%d")
            self._sessions = [s for s in self._sessions
                              if (s.get("start_time") or "").startswith(today)]

        # Clear list
        for w in self._list_frame.winfo_children():
            w.destroy()
        self._session_cards.clear()

        self._count_lbl.configure(
            text=f"{len(self._sessions)} session{'s' if len(self._sessions)!=1 else ''}")

        if not self._sessions:
            ctk.CTkLabel(self._list_frame, text="No sessions found.",
                         font=ctk.CTkFont("Segoe UI", 11), text_color=MUTED
                         ).pack(pady=40)
            return

        for s in self._sessions:
            self._build_session_card(s)

        # Auto-select focus session
        if self._focus_sid:
            fs = next((s for s in self._sessions if s["id"] == self._focus_sid), None)
            if fs:
                self._select_session(fs)
            self._focus_sid = None

    def _build_session_card(self, s: dict):
        rs    = _risk(s)
        rc    = _risk_color(rs)
        active= not s.get("end_time")
        dur   = _dur(s.get("start_time",""), s.get("end_time"))

        card = ctk.CTkFrame(
            self._list_frame, fg_color=CARD2, corner_radius=10,
            border_width=1, border_color=BORDER, cursor="hand2")
        card.pack(fill="x", padx=4, pady=3)
        card.columnconfigure(1, weight=1)

        # Status dot
        dot_color = SUCCESS if active else MUTED
        dot = ctk.CTkFrame(card, fg_color=dot_color, corner_radius=5,
                           width=10, height=10)
        dot.grid(row=0, column=0, rowspan=2, padx=(12, 8), pady=14, sticky="n")
        dot.grid_propagate(False)

        # Name + ID
        ctk.CTkLabel(card, text=s.get("student_name","")[:22],
                     font=ctk.CTkFont("Segoe UI", 12, "bold"), text_color=TEXT, anchor="w"
                     ).grid(row=0, column=1, sticky="w", pady=(10, 0))
        ctk.CTkLabel(card, text=f"{s.get('student_id','')}  ·  {dur}",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=MUTED, anchor="w"
                     ).grid(row=1, column=1, sticky="w", pady=(0, 10))

        # Risk badge
        rb = ctk.CTkFrame(card, fg_color=CARD, corner_radius=8, width=50)
        rb.grid(row=0, column=2, rowspan=2, padx=(8, 12), pady=10, sticky="e")
        rb.grid_propagate(False)
        ctk.CTkLabel(rb, text=str(rs),
                     font=ctk.CTkFont("Segoe UI", 13, "bold"), text_color=rc
                     ).place(relx=0.5, rely=0.42, anchor="center")
        ctk.CTkLabel(rb, text="risk",
                     font=ctk.CTkFont("Segoe UI", 8), text_color=MUTED
                     ).place(relx=0.5, rely=0.78, anchor="center")

        # Active badge
        if active:
            ba = ctk.CTkFrame(card, fg_color="#14532D", corner_radius=6)
            ba.grid(row=0, column=3, padx=(0, 10), pady=(10, 0), sticky="e")
            ctk.CTkLabel(ba, text="LIVE", font=ctk.CTkFont("Segoe UI", 8, "bold"),
                         text_color=SUCCESS).pack(padx=6, pady=3)

        # Bind click
        for widget in (card, dot, rb):
            widget.bind("<Button-1>", lambda e, _s=s: self._select_session(_s))
        for child in card.winfo_children():
            try:
                child.bind("<Button-1>", lambda e, _s=s: self._select_session(_s))
            except Exception:
                pass

        self._session_cards[s["id"]] = card

    def _select_session(self, s: dict):
        # Un-highlight previous
        for sid, card in self._session_cards.items():
            card.configure(border_color=BORDER, fg_color=CARD2)

        # Highlight selected
        card = self._session_cards.get(s["id"])
        if card:
            card.configure(border_color=ACCENT, fg_color=CARD)

        self._selected = s
        self._render_detail(s)

    # ── Detail rendering ───────────────────────────────────────

    def _render_detail(self, s: dict):
        self._detail_placeholder.grid_forget()

        # ── Header ─────────────────────────────────────────────
        hdr = self._detail_header
        hdr.configure(height=60)
        for w in hdr.winfo_children(): w.destroy()

        status = "● LIVE" if not s.get("end_time") else "Ended"
        sc     = SUCCESS if not s.get("end_time") else MUTED

        ctk.CTkLabel(hdr, text=f"{s['student_name']}",
                     font=ctk.CTkFont("Segoe UI", 15, "bold"), text_color=TEXT
                     ).pack(side="left", padx=(20, 0), pady=18)
        ctk.CTkLabel(hdr, text=f"  ·  {s['student_id']}  ·  {s.get('pc_hostname','?')}",
                     font=ctk.CTkFont("Segoe UI", 11), text_color=MUTED
                     ).pack(side="left", pady=18)
        ctk.CTkLabel(hdr, text=status,
                     font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=sc
                     ).pack(side="left", padx=(10, 0), pady=18)

        # Action buttons
        acts = ctk.CTkFrame(hdr, fg_color="transparent")
        acts.pack(side="right", padx=14, pady=14)
        self._btn(acts, "📸 Screenshots", self._view_screenshots, w=110
                  ).pack(side="left", padx=(0, 5))
        self._btn(acts, "📊 Export", self._export_csv, w=70
                  ).pack(side="left")

        # ── Stats strip ────────────────────────────────────────
        stats = self._detail_stats
        stats.configure(height=78)
        for w in stats.winfo_children(): w.destroy()

        rs = _risk(s)
        rc = _risk_color(rs)
        lock_thresh = settings_manager.get("risk_lock_threshold", 150)

        stat_items = [
            ("⌨", "Keystrokes",    s.get("total_keystrokes", 0), ACCENT),
            ("🖥", "Win Switches",  s.get("window_switches",  0),
             _risk_color(s.get("window_switches",0)*RISK_W_WINDOW)),
            ("📋", "Clipboard",     s.get("clipboard_events", 0),
             DANGER if s.get("clipboard_events",0)>0 else MUTED),
            ("📁", "File Copies",   s.get("file_copies",      0),
             DANGER if s.get("file_copies",0)>0 else MUTED),
            ("🔌", "USB Inserts",   s.get("usb_inserts",      0),
             DANGER if s.get("usb_inserts",0)>0 else MUTED),
            ("📂", "Ext. Files",    s.get("file_accesses",    0),
             WARNING if s.get("file_accesses",0)>0 else MUTED),
        ]
        for icon, label, val, col in stat_items:
            col_f = ctk.CTkFrame(stats, fg_color="transparent")
            col_f.pack(side="left", expand=True, pady=10)
            ctk.CTkLabel(col_f, text=str(val),
                         font=ctk.CTkFont("Segoe UI", 18, "bold"), text_color=col).pack()
            ctk.CTkLabel(col_f, text=f"{icon} {label}",
                         font=ctk.CTkFont("Segoe UI", 9), text_color=MUTED).pack()

        # Risk score pill
        sep = ctk.CTkFrame(stats, fg_color=BORDER, width=1)
        sep.pack(side="left", fill="y", pady=12)
        rpill = ctk.CTkFrame(stats, fg_color="transparent")
        rpill.pack(side="left", padx=16, pady=10, expand=True)
        ctk.CTkLabel(rpill, text=str(rs),
                     font=ctk.CTkFont("Segoe UI", 22, "bold"), text_color=rc).pack()
        ctk.CTkLabel(rpill, text=f"Risk  (lock≥{lock_thresh})",
                     font=ctk.CTkFont("Segoe UI", 9), text_color=MUTED).pack()
        # Mini risk bar
        rb_host = ctk.CTkFrame(rpill, fg_color=CARD3, corner_radius=4, height=4, width=80)
        rb_host.pack()
        rb_host.pack_propagate(False)
        frac = min(rs / max(lock_thresh, 1), 1.0)
        ctk.CTkFrame(rb_host, fg_color=rc, corner_radius=4, height=4,
                     width=max(2, int(80*frac))).place(x=0, y=0, relheight=1)

        ctk.CTkFrame(stats, fg_color=BORDER, width=1).pack(side="left", fill="y", pady=12)

        # ── Timeline ───────────────────────────────────────────
        tl = self._detail_timeline
        for w in tl.winfo_children(): w.destroy()
        tl.grid(row=2, column=0, sticky="nsew", padx=14, pady=(0, 10))

        # Timeline header
        th = ctk.CTkFrame(self._right, fg_color="transparent")
        th.grid(row=2, column=0, sticky="nw", padx=18, pady=(10, 0))
        ctk.CTkLabel(th, text="Event Timeline",
                     font=ctk.CTkFont("Segoe UI", 12, "bold"), text_color=LABEL).pack(side="left")

        # Load events
        events = database.get_events_for_session(s["id"], decrypt_sensitive=True)
        tampered = sum(1 for e in events if e.get("tampered"))
        self._show_tamper(tampered)

        if not events:
            ctk.CTkLabel(tl, text="No events recorded.",
                         font=ctk.CTkFont("Segoe UI", 11), text_color=MUTED).pack(pady=30)
            return

        start_ts = s.get("start_time", "")
        for ev in events:
            self._render_event(tl, ev, start_ts)

    def _render_event(self, parent, ev: dict, start_ts: str):
        etype   = ev.get("event_type", "")
        icon, color, lbl = _EV.get(etype, ("•", MUTED, etype))
        detail  = ev.get("detail_plain", ev.get("detail","")) or ""
        tampered= ev.get("tampered", False)
        rel     = _rel(start_ts, ev.get("timestamp",""))

        row = ctk.CTkFrame(
            parent, fg_color="#1A0A0A" if tampered else CARD2,
            corner_radius=8, border_width=1,
            border_color="#7F1D1D" if tampered else BORDER)
        row.pack(fill="x", pady=2, padx=2)
        row.columnconfigure(3, weight=1)

        # Time
        ctk.CTkLabel(row, text=rel, width=56,
                     font=ctk.CTkFont("Courier New", 10),
                     text_color=MUTED, anchor="w").grid(row=0, column=0, padx=(10, 4), pady=8)

        # Icon badge
        ib = ctk.CTkFrame(row, fg_color=CARD, corner_radius=6, width=26, height=26)
        ib.grid(row=0, column=1, padx=(0, 6)); ib.grid_propagate(False)
        ctk.CTkLabel(ib, text=icon, font=ctk.CTkFont("Segoe UI", 12),
                     text_color=color).place(relx=0.5, rely=0.5, anchor="center")

        # Label
        ctk.CTkLabel(row, text=lbl, width=110,
                     font=ctk.CTkFont("Segoe UI", 10, "bold"),
                     text_color=color, anchor="w").grid(row=0, column=2, padx=(0, 8))

        # Detail / screenshot button
        if etype == "screenshot" and detail and os.path.exists(detail):
            ctk.CTkButton(
                row, text=f"📷  View Screenshot",
                font=ctk.CTkFont("Segoe UI", 10), text_color="#F472B6",
                fg_color="transparent", hover_color=CARD, anchor="w", height=26,
                command=lambda p=detail: self._view_single_shot(p)
            ).grid(row=0, column=3, sticky="w", padx=(0, 10))
        else:
            tc  = "#FCA5A5" if tampered else TEXT2
            txt = detail[:130] + ("…" if len(detail) > 130 else "")
            ctk.CTkLabel(row, text=txt, font=ctk.CTkFont("Segoe UI", 10),
                         text_color=tc, anchor="w", justify="left", wraplength=400
                         ).grid(row=0, column=3, sticky="ew", padx=(0, 10), pady=7)

        if tampered:
            ctk.CTkLabel(row, text="⚠ TAMPERED",
                         font=ctk.CTkFont("Segoe UI", 9, "bold"),
                         text_color=DANGER).grid(row=0, column=4, padx=(0, 10))

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
            return
        evts  = database.get_events_for_session(self._selected["id"], decrypt_sensitive=True)
        shots = [e["detail_plain"] for e in evts
                 if e["event_type"] == "screenshot" and e.get("detail_plain")
                 and os.path.exists(e["detail_plain"])]
        if not shots:
            self._toast("No screenshots found for this session.", WARNING)
            return
        self._app.show_lightbox(shots, 0)

    def _view_single_shot(self, path: str):
        self._app.show_lightbox([path], 0)

    def _export_csv(self):
        if not self._selected:
            self._toast("Select a session first.", WARNING)
            return
        s     = self._selected
        evts  = database.get_events_for_session(s["id"], decrypt_sensitive=True)
        fname = f"examguard_{s['student_name'].replace(' ','_')}_{s['student_id']}.csv"
        path  = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV","*.csv")],
            initialfile=fname, title="Export Session Report")
        if not path: return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["ExamGuard Session Report"])
                for k, v in [("Student", s["student_name"]),("ID", s["student_id"]),
                              ("PC", s.get("pc_hostname","")),("Start", s.get("start_time","")),
                              ("End", s.get("end_time","")),("Keystrokes", s.get("total_keystrokes",0)),
                              ("Risk Score", _risk(s))]:
                    w.writerow([k, v])
                w.writerow([])
                w.writerow(["Timestamp","Event","Detail","Tampered"])
                for ev in evts:
                    w.writerow([ev.get("timestamp",""), ev.get("event_type",""),
                                ev.get("detail_plain",""), "YES" if ev.get("tampered") else "no"])
            database.log_access("export_csv", f"session_id={s['id']}")
            self._toast(f"Exported → {os.path.basename(path)}", SUCCESS)
        except Exception as e:
            self._toast(str(e), DANGER)

    def _show_access_log(self):
        # Render inline in right panel
        for w in self._right.winfo_children():
            w.grid_forget()
            w.destroy()

        self._right.rowconfigure(0, weight=0)
        self._right.rowconfigure(1, weight=1)

        bar = ctk.CTkFrame(self._right, fg_color=CARD, corner_radius=0, height=56)
        bar.grid(row=0, column=0, sticky="ew"); bar.pack_propagate(False)
        ctk.CTkLabel(bar, text="Instructor Access Log",
                     font=ctk.CTkFont("Segoe UI", 14, "bold"), text_color=TEXT
                     ).pack(side="left", padx=20, pady=16)
        ctk.CTkButton(bar, text="← Back", height=32, corner_radius=8, width=80,
                      fg_color="transparent", hover_color=CARD2, text_color=MUTED,
                      command=self._restore_right).pack(side="right", padx=14, pady=12)

        sf = ctk.CTkScrollableFrame(self._right, fg_color="transparent")
        sf.grid(row=1, column=0, sticky="nsew", padx=14, pady=10)

        logs = database.get_access_log(200)
        for log in (logs or []):
            r = ctk.CTkFrame(sf, fg_color=CARD2, corner_radius=8)
            r.pack(fill="x", pady=2)
            ac = DANGER if "fail" in log.get("action","") else SUCCESS
            ctk.CTkLabel(r, text=log.get("timestamp",""),
                         font=ctk.CTkFont("Courier New", 10),
                         text_color=MUTED, width=140).pack(side="left", padx=(10,6), pady=7)
            ctk.CTkLabel(r, text=log.get("action",""),
                         font=ctk.CTkFont("Segoe UI", 10, "bold"),
                         text_color=ac, width=170).pack(side="left", padx=(0,6))
            ctk.CTkLabel(r, text=log.get("detail",""),
                         font=ctk.CTkFont("Segoe UI", 10),
                         text_color=LABEL).pack(side="left", fill="x", padx=(0,10))
        if not logs:
            ctk.CTkLabel(sf, text="No access records.", text_color=MUTED,
                         font=ctk.CTkFont("Segoe UI", 11)).pack(pady=30)

    def _restore_right(self):
        for w in self._right.winfo_children():
            w.destroy()
        # Rebuild right panel
        self._right.rowconfigure(2, weight=1)
        self._detail_header = ctk.CTkFrame(self._right, fg_color=CARD, corner_radius=0, height=0)
        self._detail_header.grid(row=0, column=0, sticky="ew"); self._detail_header.pack_propagate(False)
        self._detail_stats = ctk.CTkFrame(self._right, fg_color=CARD2, corner_radius=0, height=0)
        self._detail_stats.grid(row=1, column=0, sticky="ew"); self._detail_stats.pack_propagate(False)
        self._detail_timeline = ctk.CTkScrollableFrame(self._right, fg_color="transparent")

        self._detail_placeholder = ctk.CTkFrame(self._right, fg_color="transparent")
        self._detail_placeholder.grid(row=0, column=0, rowspan=3, sticky="nsew")
        cf = ctk.CTkFrame(self._detail_placeholder, fg_color="transparent")
        cf.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(cf, text="Select a session from the list.",
                     font=ctk.CTkFont("Segoe UI", 12), text_color=MUTED).pack()

        if self._selected:
            self._render_detail(self._selected)

    def _clear_old(self):
        if messagebox.askyesno("Confirm",
                               "Delete all sessions older than 30 days?\nThis cannot be undone.",
                               icon="warning"):
            database.delete_old_sessions(30)
            database.log_access("clear_old_sessions")
            self._load_sessions()
            self._toast("Old sessions deleted.", SUCCESS)

    def _toast(self, msg: str, color: str = WARNING):
        try:
            t = ctk.CTkFrame(self, fg_color=color, corner_radius=0, height=36)
            t.place(x=0, rely=1.0, relwidth=1.0, anchor="sw")
            t.pack_propagate(False)
            ctk.CTkLabel(t, text=msg,
                         font=ctk.CTkFont("Segoe UI", 11, "bold"),
                         text_color="#fff").pack(pady=8)
            self.after(3500, t.destroy)
        except Exception:
            pass
