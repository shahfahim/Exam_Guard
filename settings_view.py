# settings_view.py — ExamGuard v4 — Settings View (CTkFrame, single-window)

import tkinter as tk
import customtkinter as ctk
import database, security, settings_manager
from theme import *


class SettingsView(ctk.CTkFrame):
    """
    Instructor settings panel — fully inline, no separate windows.
    Sections: PIN Change · Risk Thresholds · Screenshot Triggers · About
    """

    def __init__(self, parent, app):
        super().__init__(parent, fg_color=BG)
        self._app  = app
        self._vars: dict = {}
        self._build()

    # ── Layout ─────────────────────────────────────────────────

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=56)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="Settings",
                     font=ctk.CTkFont("Segoe UI", 16, "bold"), text_color=TEXT
                     ).pack(side="left", padx=24, pady=16)
        ctk.CTkLabel(hdr, text="Instructor-only configuration",
                     font=ctk.CTkFont("Segoe UI", 11), text_color=MUTED
                     ).pack(side="left", pady=16)
        ctk.CTkFrame(self, fg_color=BORDER, height=1).pack(fill="x")

        # Two-column body
        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=32, pady=20)
        body.columnconfigure(0, weight=1, minsize=380)
        body.columnconfigure(1, weight=1, minsize=320)

        left  = ctk.CTkFrame(body, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")

        # Left column: PIN + Risk thresholds
        self._build_pin_section(left)
        self._build_thresholds_section(left)

        # Right column: Screenshot triggers + About
        self._build_screenshots_section(right)
        self._build_about_section(right)

        # Save / Reset row
        self._build_action_row(body)

    # ── Sections ───────────────────────────────────────────────

    def _build_pin_section(self, parent):
        self._section_title(parent, "🔐  Instructor PIN")
        card = self._card(parent)

        self._pin_msg = ctk.CTkLabel(card, text="",
                                     font=ctk.CTkFont("Segoe UI", 10),
                                     text_color=DANGER)

        for row_label, key, ph in [
            ("Current PIN",    "_old_pin",     "Current PIN"),
            ("New PIN",        "_new_pin",     "At least 4 characters"),
            ("Confirm New",    "_confirm_pin", "Repeat new PIN"),
        ]:
            r = ctk.CTkFrame(card, fg_color="transparent")
            r.pack(fill="x", padx=16, pady=(0, 8))
            ctk.CTkLabel(r, text=row_label, width=110, anchor="w",
                         font=ctk.CTkFont("Segoe UI", 11), text_color=LABEL).pack(side="left")
            v = tk.StringVar()
            self._vars[key] = v
            ctk.CTkEntry(r, textvariable=v, show="●", placeholder_text=ph,
                         height=36, corner_radius=8, fg_color=CARD3,
                         border_color=BORDER, border_width=1,
                         font=ctk.CTkFont("Segoe UI", 12), text_color=TEXT
                         ).pack(side="left", fill="x", expand=True, padx=(8, 0))

        self._pin_msg.pack(padx=16, anchor="w", pady=(0, 4))

        ctk.CTkButton(card, text="Change PIN",
                      height=38, corner_radius=8,
                      font=ctk.CTkFont("Segoe UI", 12, "bold"),
                      fg_color=ACCENT, hover_color=ACCENT_H,
                      command=self._change_pin
                      ).pack(padx=16, anchor="w", pady=(4, 16))

    def _build_thresholds_section(self, parent):
        self._section_title(parent, "🎯  Risk Thresholds")
        card = self._card(parent)
        s    = settings_manager.load()

        items = [
            ("Green  ≤",  "risk_green_max",      "Score ≤ this → green / safe"),
            ("Yellow ≤",  "risk_yellow_max",     "Score ≤ this → yellow / caution"),
            ("Lock   ≥",  "risk_lock_threshold", "Screen locks when score hits this"),
        ]
        for lbl, key, note in items:
            r = ctk.CTkFrame(card, fg_color="transparent")
            r.pack(fill="x", padx=16, pady=(0, 10))

            ctk.CTkLabel(r, text=lbl, width=76, anchor="w",
                         font=ctk.CTkFont("Segoe UI", 11), text_color=TEXT).pack(side="left")

            v = tk.StringVar(value=str(s.get(key, "")))
            self._vars[key] = v
            ctk.CTkEntry(r, textvariable=v, width=70, height=36, corner_radius=8,
                         fg_color=CARD3, border_color=BORDER, border_width=1,
                         font=ctk.CTkFont("Segoe UI", 12, "bold"),
                         text_color=ACCENT, justify="center").pack(side="left", padx=(8, 8))

            ctk.CTkLabel(r, text=note,
                         font=ctk.CTkFont("Segoe UI", 9), text_color=MUTED,
                         anchor="w").pack(side="left", fill="x", expand=True)

        ctk.CTkFrame(card, fg_color="transparent", height=8).pack()

    def _build_screenshots_section(self, parent):
        self._section_title(parent, "📸  Screenshot Triggers")
        card = self._card(parent)
        s    = settings_manager.load()

        ctk.CTkLabel(card, text="Choose when screenshots are automatically captured:",
                     font=ctk.CTkFont("Segoe UI", 10), text_color=MUTED, anchor="w"
                     ).pack(fill="x", padx=16, pady=(4, 10))

        items = [
            ("screenshot_on_browser",     "On browser open (Chrome, Firefox, Edge…)"),
            ("screenshot_on_usb",         "On USB device insertion"),
            ("screenshot_on_clipboard",   "On code-like content pasted"),
            ("screenshot_on_file_copy",   "On file paths copied to clipboard"),
            ("screenshot_on_file_access", "On external code file access"),
        ]
        for key, label in items:
            r = ctk.CTkFrame(card, fg_color="transparent")
            r.pack(fill="x", padx=16, pady=(0, 6))
            v = tk.BooleanVar(value=bool(s.get(key, True)))
            self._vars[key] = v
            ctk.CTkSwitch(r, text=label, variable=v,
                          font=ctk.CTkFont("Segoe UI", 11), text_color=TEXT,
                          button_color=ACCENT, button_hover_color=ACCENT_H,
                          progress_color=ACCENT, onvalue=True, offvalue=False
                          ).pack(side="left")

        ctk.CTkFrame(card, fg_color="transparent", height=10).pack()

    def _build_about_section(self, parent):
        self._section_title(parent, "ℹ  About")
        card = self._card(parent)
        info = [
            ("Version",      "ExamGuard 4.0"),
            ("Architecture", "Single-window, Python + CustomTkinter"),
            ("Database",     "SQLite (examguard.db)"),
            ("Encryption",   "Fernet (PBKDF2-SHA256)"),
            ("Integrity",    "HMAC-SHA256 per event row"),
            ("Storage",      "All data local, nothing sent externally"),
        ]
        for k, v in info:
            r = ctk.CTkFrame(card, fg_color="transparent")
            r.pack(fill="x", padx=16, pady=(0, 6))
            ctk.CTkLabel(r, text=k, width=110, anchor="w",
                         font=ctk.CTkFont("Segoe UI", 10), text_color=MUTED).pack(side="left")
            ctk.CTkLabel(r, text=v, anchor="w",
                         font=ctk.CTkFont("Segoe UI", 10), text_color=LABEL).pack(side="left")

        ctk.CTkFrame(card, fg_color="transparent", height=8).pack()

    def _build_action_row(self, parent):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(16, 4))

        ctk.CTkButton(row, text="💾  Save Changes",
                      height=44, corner_radius=10,
                      font=ctk.CTkFont("Segoe UI", 13, "bold"),
                      fg_color=ACCENT, hover_color=ACCENT_H,
                      command=self._save).pack(side="left", padx=(0, 10))

        ctk.CTkButton(row, text="↺  Reset to Defaults",
                      height=44, corner_radius=10,
                      font=ctk.CTkFont("Segoe UI", 12),
                      fg_color=CARD, hover_color=CARD2,
                      border_width=1, border_color=BORDER2, text_color=TEXT,
                      command=self._reset).pack(side="left")

        self._save_msg = ctk.CTkLabel(row, text="",
                                       font=ctk.CTkFont("Segoe UI", 11), text_color=SUCCESS)
        self._save_msg.pack(side="left", padx=16)

    # ── Helpers ────────────────────────────────────────────────

    def _section_title(self, parent, text: str):
        ctk.CTkLabel(parent, text=text, anchor="w",
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color=LABEL).pack(fill="x", pady=(16, 6))

    def _card(self, parent) -> ctk.CTkFrame:
        c = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=12,
                         border_width=1, border_color=BORDER)
        c.pack(fill="x", pady=(0, 4))
        ctk.CTkFrame(c, fg_color="transparent", height=14).pack()
        return c

    # ── Actions ────────────────────────────────────────────────

    def _change_pin(self):
        old = self._vars["_old_pin"].get().strip()
        new = self._vars["_new_pin"].get().strip()
        cnf = self._vars["_confirm_pin"].get().strip()

        if not security.verify_pin(old):
            self._pin_msg.configure(text="Current PIN is incorrect.", text_color=DANGER); return
        if len(new) < 4:
            self._pin_msg.configure(text="New PIN must be at least 4 characters.", text_color=DANGER); return
        if new != cnf:
            self._pin_msg.configure(text="New PINs do not match.", text_color=DANGER); return

        settings_manager.set_value("instructor_pin", new)
        # Reset auth so new PIN is required on next instructor action
        self._app._authed = False
        database.log_access("pin_changed", "PIN updated via Settings")
        self._pin_msg.configure(text="✓  PIN changed. Re-authentication required.", text_color=SUCCESS)
        for k in ("_old_pin", "_new_pin", "_confirm_pin"):
            self._vars[k].set("")

    def _save(self):
        updated = settings_manager.load()

        # Numeric fields
        numeric_keys = ("risk_green_max", "risk_yellow_max", "risk_lock_threshold")
        for key in numeric_keys:
            try:
                updated[key] = int(self._vars[key].get())
            except (ValueError, KeyError):
                self._save_msg.configure(
                    text=f"Invalid value for '{key}'.", text_color=DANGER)
                return

        # Validation
        if not (0 < updated["risk_green_max"]
                  < updated["risk_yellow_max"]
                  < updated["risk_lock_threshold"]):
            self._save_msg.configure(
                text="Thresholds must satisfy: Green < Yellow < Lock.", text_color=DANGER)
            return

        # Boolean fields
        bool_keys = ("screenshot_on_browser", "screenshot_on_usb",
                     "screenshot_on_clipboard", "screenshot_on_file_copy",
                     "screenshot_on_file_access")
        for key in bool_keys:
            updated[key] = bool(self._vars[key].get())

        settings_manager.save(updated)
        database.log_access("settings_saved")
        self._save_msg.configure(text="✓  Settings saved.", text_color=SUCCESS)
        self.after(3000, lambda: self._save_msg.configure(text=""))

    def _reset(self):
        settings_manager.reset()
        database.log_access("settings_reset")
        s = settings_manager.load()
        for key in ("risk_green_max", "risk_yellow_max", "risk_lock_threshold"):
            if key in self._vars:
                self._vars[key].set(str(s.get(key, "")))
        for key in ("screenshot_on_browser", "screenshot_on_usb",
                    "screenshot_on_clipboard", "screenshot_on_file_copy",
                    "screenshot_on_file_access"):
            if key in self._vars:
                self._vars[key].set(bool(s.get(key, True)))
        for k in ("_old_pin", "_new_pin", "_confirm_pin"):
            if k in self._vars:
                self._vars[k].set("")
        if hasattr(self, "_pin_msg"):
            self._pin_msg.configure(text="")
        self._save_msg.configure(text="✓  Reset to defaults.", text_color=SUCCESS)
        self.after(3000, lambda: self._save_msg.configure(text=""))
