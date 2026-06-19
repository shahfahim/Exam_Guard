# config.py — ExamGuard v4 Configuration

import os
import base64

# ── Runtime-aware path resolution (works from source AND frozen exe) ────────
from app.paths import get_db_path, get_vault_dir, get_screenshots_dir

# ── Access Control ────────────────────────────────────────────
INSTRUCTOR_PIN = "1234"

# ── App Encryption Key ────────────────────────────────────────
APP_SECRET = b"ExamGuard-v2-SecretKey-2024-Stable"

# ── Monitoring Intervals (seconds) ───────────────────────────
WINDOW_CHECK_INTERVAL    = 0.5
CLIPBOARD_CHECK_INTERVAL = 1.0
SCREENSHOT_INTERVAL      = 120
KEYSTROKE_SAVE_INTERVAL  = 30
USB_CHECK_INTERVAL       = 1.5    # USB drive poll frequency

# ── Screenshot Vault ──────────────────────────────────────────────────────
# Always stored in %APPDATA%\ExamGuard\.vault  (never in Program Files)
VAULT_DIR = get_vault_dir()

# ── Database ──────────────────────────────────────────────────────────────────
# Full path to SQLite file in %APPDATA%\ExamGuard\  (writable without admin)
DB_FILE = get_db_path()

# ── Screenshots directory ─────────────────────────────────────────────────────
SCREENSHOTS_DIR = get_screenshots_dir()

# ── Risk Score Weights (per event) ───────────────────────────
RISK_W_WINDOW        = 3    # window switch
RISK_W_CLIPBOARD     = 8    # clipboard text copy
RISK_W_FILE_COPY     = 15   # file path in clipboard
RISK_W_USB_INSERT    = 25   # USB/pendrive inserted
RISK_W_IDE_PREEXIST  = 20   # code in clipboard before exam
RISK_W_FILE_ACCESS   = 10   # external file opened in IDE

# ── Risk Thresholds ───────────────────────────────────────────
RISK_GREEN_MAX     = 20    # 0-20   → Low Risk  (green)
RISK_YELLOW_MAX    = 50    # 21-50  → Suspicious (yellow)
RISK_LOCK_THRESHOLD = 150  # 150+   → Screen locked until PIN
                            # 51+    → High Risk  (red)

# ── Idle Penalty ──────────────────────────────────────────────
RISK_W_IDLE        = 10    # penalty: total keystrokes < 50

# ── IDE Process Names (for pre-exam content check) ────────────
IDE_PROCESSES = {
    "code.exe",          # VS Code
    "codeblocks.exe",    # Code::Blocks
    "devenv.exe",        # Visual Studio
    "pycharm64.exe",     # PyCharm
    "idea64.exe",        # IntelliJ IDEA
    "eclipse.exe",       # Eclipse
    "atom.exe",          # Atom
    "sublime_text.exe",  # Sublime Text
    "notepad++.exe",     # Notepad++
}

# ── Code file extensions (for file-access monitoring) ─────────
CODE_EXTENSIONS = {
    ".py", ".c", ".cpp", ".h", ".hpp", ".java", ".js",
    ".ts", ".cs", ".go", ".rs", ".php", ".rb", ".swift",
    ".kt", ".r", ".m", ".sql",
}

# ── File-access monitor directories ──────────────────────────
# Relative to user home; these are watched for suspicious file activity
WATCHED_SUBDIRS = ["Desktop", "Downloads", "Documents"]

# ── UI ─────────────────────────────────────────────────────────
CTK_APPEARANCE = "dark"
CTK_COLOR      = "dark-blue"
MIN_EXAM_SECONDS = 10
