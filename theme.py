# theme.py — ExamGuard v4 — Shared Design Tokens

# ── Backgrounds ───────────────────────────────────────────────
BG      = "#0B0D14"   # App window background
SIDEBAR = "#0D0F18"   # Sidebar
CARD    = "#131720"   # Card surfaces
CARD2   = "#191E2D"   # Elevated card / hover state
CARD3   = "#0F1219"   # Depressed / input background

# ── Borders ───────────────────────────────────────────────────
BORDER  = "#1C2235"   # Default border
BORDER2 = "#252E42"   # Active / focus border

# ── Accent ────────────────────────────────────────────────────
ACCENT  = "#5B5EE8"   # Primary accent (indigo)
ACCENT_H= "#4B4DD8"   # Hover
ACCENT_L= "#3D3FAA"   # Active/pressed

# ── Semantic ──────────────────────────────────────────────────
SUCCESS = "#22C55E"
DANGER  = "#EF4444"
WARNING = "#F59E0B"
INFO    = "#3B82F6"

# ── Text ──────────────────────────────────────────────────────
TEXT    = "#F1F5F9"   # Primary text
TEXT2   = "#CBD5E1"   # Secondary text
LABEL   = "#94A3B8"   # Labels / captions
MUTED   = "#64748B"   # Muted / disabled
SUBTLE  = "#2D3748"   # Very subtle (dividers, meta)

# ── Font helpers (for ctk.CTkFont) ────────────────────────────
def F(size: int, weight: str = "normal"):
    return ("Segoe UI", size, weight)

def FM(size: int, weight: str = "normal"):
    return ("Courier New", size, weight)
