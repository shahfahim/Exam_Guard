# main.py — ExamGuard v4 — Single Window Application

import tkinter as tk
import customtkinter as ctk
import os
from PIL import Image, ImageTk

import database, security, settings_manager
import update_checker
from version import APP_NAME, VERSION
from config import CTK_APPEARANCE, CTK_COLOR
from theme import *

ctk.set_appearance_mode(CTK_APPEARANCE)
ctk.set_default_color_theme(CTK_COLOR)

# VERSION is now imported from version.py

# ── Nav definition ─────────────────────────────────────────────
_NAV = [
    ("student",    "🎓", "Student Exam",     False),   # (page, icon, label, needs_auth)
    ("instructor", "🔐", "Instructor",        True),
    ("settings",   "⚙ ", "Settings",          True),
]


class ExamGuardApp(ctk.CTk):
    """
    Single-window ExamGuard application.
    All views are CTkFrame widgets swapped inside self._area.
    No CTkToplevel is used except the fullscreen screen lock.
    """

    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME}  v{VERSION}")
        self.geometry("1280x800")
        self.minsize(1100, 700)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        database.initialize_db()
        security.ensure_vault()
        security.ensure_pin_hashed()   # migrate plaintext PIN to PBKDF2 hash on first run

        self._page: str = ""
        self._authed: bool = False
        self._exam_session_id: int | None = None
        self._nav_btns: dict = {}
        self._sb_visible: bool = False   # sidebar hidden by default
        self._update_banner = None        # update notification widget

        self._build_layout()
        self.navigate("welcome")
        self._center()

        # Check for updates silently in background (non-blocking)
        update_checker.check_in_background(
            lambda tag, url: self.after(0, lambda: self._show_update_banner(tag, url))
        )

    def _center(self):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    # ── Layout ─────────────────────────────────────────────────

    def _build_layout(self):
        # Sidebar wrapper — toggled by _set_sidebar_visible()
        self._sb_wrap = ctk.CTkFrame(self, fg_color="transparent")
        # sidebar + 1-px divider live inside wrapper
        self._sidebar = ctk.CTkFrame(self._sb_wrap, fg_color=SIDEBAR, width=224, corner_radius=0)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)
        ctk.CTkFrame(self._sb_wrap, fg_color=BORDER, width=1, corner_radius=0
                     ).pack(side="left", fill="y")
        self._build_sidebar()

        # Content area — always present, width adjusts when sidebar shown/hidden
        self._area = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self._area.pack(fill="both", expand=True)   # sidebar hidden initially

    def _set_sidebar_visible(self, visible: bool):
        """Toggle sidebar without creating/destroying widgets."""
        if visible == self._sb_visible:
            return
        self._sb_visible = visible
        # Unpack both, then repack in correct order
        self._sb_wrap.pack_forget()
        self._area.pack_forget()
        if visible:
            self._sb_wrap.pack(side="left", fill="y")
        self._area.pack(fill="both", expand=True)

    def _build_sidebar(self):
        sb = self._sidebar

        # Logo
        lf = ctk.CTkFrame(sb, fg_color="transparent", height=76)
        lf.pack(fill="x"); lf.pack_propagate(False)
        ctk.CTkLabel(lf, text="🛡  ExamGuard",
                     font=ctk.CTkFont("Segoe UI", 16, "bold"),
                     text_color=ACCENT).place(x=20, y=20)
        ctk.CTkLabel(lf, text="Integrity Monitor",
                     font=ctk.CTkFont("Segoe UI", 9),
                     text_color=MUTED).place(x=20, y=46)

        ctk.CTkFrame(sb, fg_color=BORDER, height=1).pack(fill="x", padx=16, pady=(0, 10))

        # Section label helper
        def _sec(text):
            ctk.CTkLabel(sb, text=text, font=ctk.CTkFont("Segoe UI", 9, "bold"),
                         text_color=SUBTLE, anchor="w").pack(fill="x", padx=20, pady=(10, 3))

        _sec("EXAM")
        for page, icon, label, needs_auth in _NAV[:2]:
            self._nav_btn(sb, page, icon, label)

        _sec("SYSTEM")
        for page, icon, label, needs_auth in _NAV[2:]:
            self._nav_btn(sb, page, icon, label)

        # Footer
        ctk.CTkFrame(sb, fg_color=BORDER, height=1).pack(side="bottom", fill="x", padx=16, pady=(0, 4))
        ft = ctk.CTkFrame(sb, fg_color="transparent")
        ft.pack(side="bottom", fill="x", padx=16, pady=8)
        ctk.CTkLabel(ft, text=f"ExamGuard  v{VERSION}",
                     font=ctk.CTkFont("Segoe UI", 9), text_color=MUTED).pack(anchor="w")
        ctk.CTkLabel(ft, text="All data stays local",
                     font=ctk.CTkFont("Segoe UI", 9), text_color=SUBTLE).pack(anchor="w")

    def _nav_btn(self, parent, page, icon, label):
        btn = ctk.CTkButton(
            parent, text=f"  {icon}  {label}",
            height=38, corner_radius=8,
            font=ctk.CTkFont("Segoe UI", 12),
            fg_color="transparent", hover_color=CARD2,
            text_color=MUTED, anchor="w",
            command=lambda p=page: self._nav_click(p))
        btn.pack(fill="x", padx=10, pady=1)
        self._nav_btns[page] = btn

    # ── Navigation ─────────────────────────────────────────────

    def _nav_click(self, page: str):
        needs_auth = next((a for p, i, l, a in _NAV if p == page), False)
        if needs_auth and not self._authed:
            self.show_pin_gate(on_success=lambda: self._nav_click(page),
                               title="Instructor Authentication")
            return
        self.navigate(page)

    def navigate(self, page: str, **kwargs):
        """Destroy current view content and build new page."""
        for w in self._area.winfo_children():
            w.destroy()

        # Sidebar only visible in instructor-mode pages
        self._set_sidebar_visible(page in ("instructor", "settings"))

        self._page = page
        self._highlight_nav(page)

        if page == "welcome":
            _WelcomePage(self._area, app=self).pack(fill="both", expand=True)
        elif page == "student":
            from student_view import StudentView
            StudentView(self._area, app=self, **kwargs).pack(fill="both", expand=True)
        elif page == "instructor":
            from instructor_view import InstructorView
            InstructorView(self._area, app=self, **kwargs).pack(fill="both", expand=True)
        elif page == "settings":
            from settings_view import SettingsView
            SettingsView(self._area, app=self).pack(fill="both", expand=True)

    def _highlight_nav(self, active: str):
        for name, btn in self._nav_btns.items():
            if name == active:
                btn.configure(fg_color=CARD2, text_color=TEXT)
            else:
                btn.configure(fg_color="transparent", text_color=MUTED)

    # ── PIN gate (full content-area page) ─────────────────────

    def show_pin_gate(self, on_success, title="Instructor Authentication",
                      subtitle="Enter your PIN to continue"):
        """Show a PIN entry page inside the content area."""
        for w in self._area.winfo_children():
            w.destroy()
        _PINGatePage(self._area, app=self,
                     on_success=on_success,
                     title=title, subtitle=subtitle).pack(fill="both", expand=True)

    # ── Inline PIN overlay (for mid-session instructor actions) ──

    def show_pin_overlay(self, on_success, title="Instructor Required"):
        """Overlay over whatever is currently shown (mid-exam end session)."""
        ov = _PINOverlay(self._area, on_success=on_success, title=title)
        ov.place(relx=0, rely=0, relwidth=1, relheight=1)
        ov.lift()

    # ── Lightbox overlay ──────────────────────────────────────

    def show_lightbox(self, paths: list, start_idx: int = 0):
        lb = _LightboxOverlay(self._area, paths=paths, start_idx=start_idx)
        lb.place(relx=0, rely=0, relwidth=1, relheight=1)
        lb.lift()

    # ── Session lifecycle callbacks ────────────────────────────

    def on_exam_started(self, session_id: int):
        self._exam_session_id = session_id
        btn = self._nav_btns.get("student")
        if btn:
            btn.configure(text="  🟢  Student Exam", text_color=SUCCESS, fg_color=CARD2)

    def on_exam_ended(self, session_id: int):
        self._exam_session_id = None
        btn = self._nav_btns.get("student")
        if btn:
            btn.configure(text="  🎓  Student Exam", text_color=MUTED, fg_color="transparent")
        self._authed = True
        self.navigate("instructor", focus_session=session_id)

    # ── Window close ───────────────────────────────────────────

    def _on_close(self):
        if self._exam_session_id is not None:
            pass  # Exam is active; block close (screen lock handles this)
        else:
            self.destroy()

    # ── Update notification banner ─────────────────────────────────

    def _show_update_banner(self, tag: str, url: str):
        """Show a dismissible update notification in the sidebar footer."""
        import webbrowser
        if self._update_banner is not None:
            return  # already shown
        sb = self._sidebar
        banner = ctk.CTkFrame(sb, fg_color="#1B2240", corner_radius=8,
                              border_width=1, border_color=ACCENT)
        banner.pack(side="bottom", fill="x", padx=10, pady=(0, 8))

        ctk.CTkLabel(banner, text=f"\u2b06  Update {tag} available",
                     font=ctk.CTkFont("Segoe UI", 10, "bold"),
                     text_color=ACCENT
                     ).pack(side="left", padx=(10, 4), pady=6)

        ctk.CTkButton(banner, text="View", width=48, height=24, corner_radius=6,
                      font=ctk.CTkFont("Segoe UI", 9),
                      fg_color=ACCENT, hover_color=ACCENT_H,
                      command=lambda: webbrowser.open(url)).pack(side="left", pady=6)

        ctk.CTkButton(banner, text="\u00d7", width=24, height=24, corner_radius=6,
                      font=ctk.CTkFont("Segoe UI", 10),
                      fg_color="transparent", hover_color=CARD2, text_color=MUTED,
                      command=lambda: (banner.destroy(),
                                       setattr(self, "_update_banner", None))
                      ).pack(side="right", padx=4, pady=6)

        self._update_banner = banner


# ───────────────────────────────────────────────────────────────
#  Welcome page
# ───────────────────────────────────────────────────────────────

class _WelcomePage(ctk.CTkFrame):
    def __init__(self, parent, app: ExamGuardApp):
        super().__init__(parent, fg_color=BG)
        self._app = app
        self._build()

    def _build(self):
        c = ctk.CTkFrame(self, fg_color="transparent")
        c.place(relx=0.5, rely=0.46, anchor="center")

        ctk.CTkLabel(c, text="🛡", font=ctk.CTkFont("Segoe UI", 64)).pack()
        ctk.CTkLabel(c, text="ExamGuard",
                     font=ctk.CTkFont("Segoe UI", 34, "bold"), text_color=TEXT).pack(pady=(6, 2))
        ctk.CTkLabel(c, text="Lab Exam Integrity Monitor",
                     font=ctk.CTkFont("Segoe UI", 13), text_color=MUTED).pack()

        ctk.CTkFrame(c, fg_color="transparent", height=36).pack()

        # Primary action — large, obvious
        ctk.CTkButton(c, text="Start Exam",
                      width=280, height=56, corner_radius=12,
                      font=ctk.CTkFont("Segoe UI", 16, "bold"),
                      fg_color=ACCENT, hover_color=ACCENT_H,
                      command=lambda: self._app.navigate("student")).pack()

        # Instructor link — small and discreet at the bottom
        ctk.CTkButton(c, text="Instructor Access",
                      width=280, height=32, corner_radius=8,
                      font=ctk.CTkFont("Segoe UI", 10),
                      fg_color="transparent", hover_color=CARD2,
                      text_color=SUBTLE,
                      command=lambda: self._app._nav_click("instructor")).pack(pady=(8, 0))


# ─────────────────────────────────────────────────────────────
#  PIN gate (full content-area page for sidebar auth)
# ─────────────────────────────────────────────────────────────

class _PINGatePage(ctk.CTkFrame):
    def __init__(self, parent, app, on_success, title, subtitle):
        super().__init__(parent, fg_color=BG)
        self._app = app
        self._on_success = on_success
        self._attempts = 0
        self._locked_until = 0

        c = ctk.CTkFrame(self, fg_color="transparent")
        c.place(relx=0.5, rely=0.44, anchor="center")

        ctk.CTkLabel(c, text="🔐", font=ctk.CTkFont("Segoe UI", 52)).pack()
        ctk.CTkLabel(c, text=title,
                     font=ctk.CTkFont("Segoe UI", 22, "bold"), text_color=TEXT).pack(pady=(8, 4))
        ctk.CTkLabel(c, text=subtitle,
                     font=ctk.CTkFont("Segoe UI", 12), text_color=MUTED).pack()

        card = ctk.CTkFrame(c, fg_color=CARD, corner_radius=14,
                            border_width=1, border_color=BORDER, width=360)
        card.pack(pady=28)
        card.pack_propagate(False)

        ctk.CTkLabel(card, text="Instructor PIN",
                     font=ctk.CTkFont("Segoe UI", 11), text_color=LABEL).pack(pady=(22, 6))

        self._pin_var = tk.StringVar()
        self._pin_entry = ctk.CTkEntry(
            card, textvariable=self._pin_var, show="●",
            justify="center", width=220, height=50,
            font=ctk.CTkFont("Segoe UI", 22),
            fg_color=CARD3, border_color=ACCENT, border_width=1,
            corner_radius=10, text_color=TEXT)
        self._pin_entry.pack(pady=(0, 6))
        self._pin_entry.bind("<Return>", lambda _: self._verify())
        self._pin_entry.focus()

        self._msg = ctk.CTkLabel(card, text="",
                                  font=ctk.CTkFont("Segoe UI", 11), text_color=DANGER)
        self._msg.pack(pady=(0, 6))

        ctk.CTkButton(card, text="Verify & Continue",
                      height=44, width=220, corner_radius=10,
                      font=ctk.CTkFont("Segoe UI", 13, "bold"),
                      fg_color=ACCENT, hover_color=ACCENT_H,
                      command=self._verify).pack(pady=(0, 22))

        ctk.CTkButton(c, text="← Back",
                      height=32, width=120, corner_radius=8,
                      font=ctk.CTkFont("Segoe UI", 11),
                      fg_color="transparent", hover_color=CARD2, text_color=MUTED,
                      command=lambda: self._app.navigate("welcome")).pack()

    def _verify(self):
        import time
        now = time.time()
        if now < self._locked_until:
            remaining = int(self._locked_until - now)
            self._msg.configure(text=f"Too many attempts. Wait {remaining}s.")
            return

        self._attempts += 1
        if security.verify_pin(self._pin_var.get()):
            database.log_access("instructor_auth_ok", f"attempts={self._attempts}")
            self._app._authed = True
            self._on_success()
        else:
            database.log_access("instructor_auth_fail", f"attempt={self._attempts}")
            self._pin_var.set("")
            self._pin_entry.focus()
            if self._attempts >= 5:
                import time as _t
                self._locked_until = _t.time() + 30
                self._msg.configure(text="5 failed attempts. Locked for 30 seconds.")
                self._pin_entry.configure(state="disabled")
                self.after(30000, lambda: (
                    self._pin_entry.configure(state="normal"),
                    self._msg.configure(text=""),
                    setattr(self, "_attempts", 0),
                    self._pin_entry.focus()
                ))
            else:
                self._msg.configure(
                    text=f"Incorrect PIN  ({self._attempts} attempt{'s' if self._attempts > 1 else ''})")


# ─────────────────────────────────────────────────────────────
#  PIN overlay (for mid-exam end-session)
# ─────────────────────────────────────────────────────────────

class _PINOverlay(ctk.CTkFrame):
    """Semi-transparent overlay placed over the content area."""
    def __init__(self, parent, on_success, title="Instructor Required"):
        super().__init__(parent, fg_color="#050709", corner_radius=0)
        self._on_success = on_success
        self._attempts = 0

        card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=14,
                            border_width=1, border_color=BORDER2, width=380, height=320)
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)

        ctk.CTkLabel(card, text="🔐  " + title,
                     font=ctk.CTkFont("Segoe UI", 16, "bold"), text_color=TEXT).pack(pady=(28, 4))
        ctk.CTkLabel(card, text="Enter instructor PIN to continue",
                     font=ctk.CTkFont("Segoe UI", 11), text_color=MUTED).pack(pady=(0, 20))

        self._pin_var = tk.StringVar()
        self._entry = ctk.CTkEntry(card, textvariable=self._pin_var, show="●",
                                    justify="center", width=200, height=48,
                                    font=ctk.CTkFont("Segoe UI", 20),
                                    fg_color=CARD3, border_color=ACCENT, border_width=1,
                                    corner_radius=10, text_color=TEXT)
        self._entry.pack()
        self._entry.bind("<Return>", lambda _: self._verify())
        self._entry.focus()

        self._msg = ctk.CTkLabel(card, text="", font=ctk.CTkFont("Segoe UI", 10),
                                  text_color=DANGER)
        self._msg.pack(pady=(4, 0))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(pady=(12, 22), padx=24)
        ctk.CTkButton(row, text="Verify", height=40, corner_radius=8, width=140,
                      font=ctk.CTkFont("Segoe UI", 12, "bold"),
                      fg_color=ACCENT, hover_color=ACCENT_H,
                      command=self._verify).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Cancel", height=40, corner_radius=8, width=100,
                      font=ctk.CTkFont("Segoe UI", 12),
                      fg_color=CARD2, hover_color=BORDER, border_width=1, border_color=BORDER,
                      command=self.destroy).pack(side="left")

        # Absorb clicks on background
        self.bind("<Button-1>", lambda e: None)

    def _verify(self):
        import time
        now = time.time()
        if hasattr(self, '_locked_until') and now < self._locked_until:
            remaining = int(self._locked_until - now)
            self._msg.configure(text=f"Locked. Wait {remaining}s.")
            return

        self._attempts += 1
        if security.verify_pin(self._pin_var.get()):
            database.log_access("instructor_auth_ok", f"attempt={self._attempts}")
            self.destroy()
            self._on_success()
        else:
            database.log_access("instructor_auth_fail", f"attempt={self._attempts}")
            self._pin_var.set("")
            self._entry.focus()
            self._msg.configure(
                text=f"Incorrect PIN  ({self._attempts} attempt{'s' if self._attempts > 1 else ''}")
            if self._attempts >= 5:
                import time as _t
                self._locked_until = _t.time() + 30
                self._entry.configure(state="disabled")
                self._msg.configure(text="Too many attempts. Locked for 30 seconds.")
                self.after(30_000, lambda: (
                    self._entry.configure(state="normal"),
                    self._msg.configure(text=""),
                    setattr(self, "_attempts", 0),
                    setattr(self, "_locked_until", 0),
                    self._entry.focus()
                ))


# ─────────────────────────────────────────────────────────────
#  Lightbox overlay
# ─────────────────────────────────────────────────────────────

class _LightboxOverlay(ctk.CTkFrame):
    def __init__(self, parent, paths: list, start_idx: int = 0):
        super().__init__(parent, fg_color="#05070A", corner_radius=0)
        self._paths  = [p for p in paths if os.path.exists(p)]
        self._idx    = max(0, min(start_idx, len(self._paths) - 1))
        self._photo  = None
        self._cache: dict = {}   # path+size → PhotoImage
        if not self._paths:
            self.destroy(); return
        self.bind("<Button-1>", lambda e: None)
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Left>",   lambda e: self._prev())
        self.bind("<Right>",  lambda e: self._next())
        self._build()
        self._show()
        self.focus_set()

    def _build(self):
        # Top bar
        bar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=48)
        bar.pack(fill="x"); bar.pack_propagate(False)

        self._title_var = tk.StringVar()
        ctk.CTkLabel(bar, textvariable=self._title_var,
                     font=ctk.CTkFont("Segoe UI", 11), text_color=LABEL).pack(side="left", padx=16, pady=12)

        nav = ctk.CTkFrame(bar, fg_color="transparent")
        nav.pack(side="right", padx=12, pady=8)
        for txt, cmd in [("◀", self._prev), ("▶", self._next)]:
            ctk.CTkButton(nav, text=txt, width=34, height=32, corner_radius=6,
                          fg_color=CARD2, hover_color=BORDER,
                          command=cmd).pack(side="left", padx=2)
        ctk.CTkButton(nav, text="✕  Close", width=80, height=32, corner_radius=6,
                      fg_color="transparent", hover_color=CARD2,
                      text_color=MUTED,
                      command=self.destroy).pack(side="left", padx=(8, 0))

        self._img_lbl = tk.Label(self, bg="#05070A", cursor="arrow")
        self._img_lbl.pack(expand=True, fill="both", padx=20, pady=16)

    def _show(self):
        path = self._paths[self._idx]
        self._title_var.set(f"{self._idx+1} / {len(self._paths)}  —  {os.path.basename(path)}")
        self.update_idletasks()
        w = max(self._img_lbl.winfo_width(), 800)
        h = max(self._img_lbl.winfo_height(), 500)
        cache_key = f"{path}|{w}x{h}"
        if cache_key not in self._cache:
            try:
                img = Image.open(path)
                img.thumbnail((w, h), Image.LANCZOS)
                self._cache[cache_key] = ImageTk.PhotoImage(img)
                # Keep cache small — evict oldest if >20 entries
                if len(self._cache) > 20:
                    oldest_key = next(iter(self._cache))
                    del self._cache[oldest_key]
            except Exception:
                return   # Skip unreadable image
        self._photo = self._cache[cache_key]
        self._img_lbl.configure(image=self._photo)

    def _prev(self): self._idx = (self._idx - 1) % len(self._paths); self._show()
    def _next(self): self._idx = (self._idx + 1) % len(self._paths); self._show()


# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ExamGuardApp().mainloop()
