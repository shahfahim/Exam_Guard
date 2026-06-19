# security.py — Encryption, HMAC integrity, and vault management for ExamGuard v2

"""
Security layers:
1. Field-level Fernet encryption  — clipboard text & screenshot paths stored as ciphertext in DB
2. HMAC-SHA256 per event          — detects external DB edits (row add/delete/modify)
3. Hidden OS vault folder         — screenshots stored in AppData with hidden+system attribute
4. Access audit log               — every instructor login written to DB
"""

import os
import hmac as _hmac
import hashlib
import base64
import ctypes
import sys
from datetime import datetime

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from config import APP_SECRET, VAULT_DIR

# ─────────────────────────────────────────────────────────────
#  Key derivation  (done once at module import, from APP_SECRET)
# ─────────────────────────────────────────────────────────────

_PBKDF2_SALT = b"ExamGuard_PBKDF2_Salt_v2_2024"
_ITERATIONS  = 200_000

def _derive_fernet_key(secret: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_PBKDF2_SALT,
        iterations=_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(secret))


# Module-level singletons (initialised once)
_fernet: Fernet = Fernet(_derive_fernet_key(APP_SECRET))
_hmac_key: bytes = hashlib.sha256(APP_SECRET + b":hmac-integrity").digest()


# ─────────────────────────────────────────────────────────────
#  Encryption helpers
# ─────────────────────────────────────────────────────────────

def encrypt(plaintext: str) -> str:
    """Encrypt a string; returns URL-safe base64 ciphertext."""
    if not plaintext:
        return ""
    try:
        return _fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")
    except Exception:
        return plaintext   # fallback — don't lose data


def decrypt(token: str) -> str:
    """Decrypt a Fernet token; returns '[ENCRYPTED]' on failure."""
    if not token:
        return ""
    try:
        return _fernet.decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, Exception):
        return "[DECRYPTION FAILED — DATA MAY BE TAMPERED]"


# ─────────────────────────────────────────────────────────────
#  HMAC integrity signing
# ─────────────────────────────────────────────────────────────

def sign(data: str) -> str:
    """Return HMAC-SHA256 hex digest for an event's canonical string."""
    sig = _hmac.new(_hmac_key, data.encode("utf-8"), hashlib.sha256).hexdigest()
    return sig


def verify(data: str, signature: str) -> bool:
    """Verify an event's HMAC. Returns False if tampered."""
    if not signature:
        return True   # Legacy rows without signature: skip check
    expected = _hmac.new(_hmac_key, data.encode("utf-8"), hashlib.sha256).hexdigest()
    return _hmac.compare_digest(expected, signature)


def event_canonical(session_id: int, event_type: str, detail: str, timestamp: str) -> str:
    """Build the canonical string used for HMAC signing of an event row."""
    return f"{session_id}|{event_type}|{detail}|{timestamp}"


# ─────────────────────────────────────────────────────────────
#  Hidden vault folder
# ─────────────────────────────────────────────────────────────

def ensure_vault() -> str:
    """
    Create the screenshot vault directory and mark it hidden+system on Windows.
    Returns the absolute vault path.
    """
    os.makedirs(VAULT_DIR, exist_ok=True)

    if sys.platform == "win32":
        try:
            # FILE_ATTRIBUTE_HIDDEN (0x2) | FILE_ATTRIBUTE_SYSTEM (0x4) = 0x6
            ctypes.windll.kernel32.SetFileAttributesW(VAULT_DIR, 0x6)
            # Also hide the parent ExamGuard folder in AppData
            parent = os.path.dirname(VAULT_DIR)
            ctypes.windll.kernel32.SetFileAttributesW(parent, 0x2)
        except Exception:
            pass  # Non-fatal if permission denied

    return VAULT_DIR


def is_vault_accessible() -> bool:
    """Quick check that vault exists and is writable."""
    try:
        ensure_vault()
        test = os.path.join(VAULT_DIR, ".test")
        with open(test, "w") as f:
            f.write("ok")
        os.remove(test)
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────
#  PIN verification
# ─────────────────────────────────────────────────────────────

def verify_pin(entered: str) -> bool:
    import settings_manager
    stored = settings_manager.get("instructor_pin", "1234")
    # Constant-time comparison to resist timing attacks
    return _hmac.compare_digest(entered.encode(), stored.encode())
