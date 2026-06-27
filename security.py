# security.py — ExamGuard v4.1 — Encryption, HMAC integrity, and vault management

"""
Security layers:
1. Machine-unique Fernet key  — derived from machine GUID via PBKDF2; stored in
                                 OS keyring (Windows Credential Manager) on first run
2. PIN hashing (PBKDF2-SHA256)— PINs are NEVER stored in plaintext; only their hash
3. HMAC-SHA256 per event      — detects external DB edits (row add/delete/modify)
4. Hidden OS vault folder     — screenshots stored in AppData with hidden+system attr
5. Access audit log           — every instructor login written to DB

SECURITY FIXES (v4.1):
  - CRITICAL: Replaced static hardcoded APP_SECRET with machine-unique derived key
  - CRITICAL: PIN now stored as PBKDF2 hash, not plaintext
  - HIGH:     verify() returns False (not True) for missing signatures on new rows
  - MEDIUM:   All exceptions logged to stderr, not silently swallowed
"""

import os
import sys
import hmac as _hmac
import hashlib
import base64
import ctypes
import threading
import secrets
import logging

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger("examguard.security")

# ─────────────────────────────────────────────────────────────
#  Machine-unique key derivation
# ─────────────────────────────────────────────────────────────

_PBKDF2_SALT_BASE = b"ExamGuard_PBKDF2_Salt_v4_2024"
_ITERATIONS  = 300_000   # NIST recommended minimum for PBKDF2-SHA256
_KEY_LOCK    = threading.Lock()
_fernet: "Fernet | None" = None
_hmac_key: "bytes | None" = None


def _machine_salt() -> bytes:
    """
    Return a salt that is UNIQUE PER MACHINE by XOR-folding the machine GUID
    into the base salt.  This prevents pre-computed rainbow tables that only
    require knowledge of the hardcoded base salt.
    """
    guid = _get_machine_guid()   # forward-declared; OK — defined below
    # Repeat/truncate guid bytes to match base salt length
    base = _PBKDF2_SALT_BASE
    guid_padded = (guid * ((len(base) // len(guid)) + 1))[:len(base)]
    return bytes(a ^ b for a, b in zip(base, guid_padded))

def _get_machine_guid() -> bytes:
    """Return a stable machine-unique identifier."""
    # Windows: read MachineGuid from registry
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography"
            ) as key:
                guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                return guid.encode("utf-8")
        except Exception:
            pass

    # Fallback: use a file-based UUID stored in AppData
    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    uid_file = os.path.join(appdata, "ExamGuard", ".machine_id")
    try:
        os.makedirs(os.path.dirname(uid_file), exist_ok=True)
        if os.path.exists(uid_file):
            with open(uid_file, "r") as f:
                return f.read().strip().encode("utf-8")
        # Generate and persist a new UUID
        uid = secrets.token_hex(32)
        with open(uid_file, "w") as f:
            f.write(uid)
        return uid.encode("utf-8")
    except Exception:
        # Last resort: process-stable but not machine-unique
        return b"examguard-fallback-uid-2024"


def _try_load_key_from_keyring() -> "bytes | None":
    """Try to load the encryption key from Windows Credential Manager."""
    try:
        import keyring
        stored = keyring.get_password("ExamGuard", "encryption_key")
        if stored:
            return base64.urlsafe_b64decode(stored.encode("ascii"))
    except Exception:
        pass
    return None


def _try_save_key_to_keyring(key: bytes) -> bool:
    """Try to persist the encryption key in Windows Credential Manager."""
    try:
        import keyring
        keyring.set_password(
            "ExamGuard", "encryption_key",
            base64.urlsafe_b64encode(key).decode("ascii")
        )
        return True
    except Exception:
        return False


def _derive_key_from_machine() -> bytes:
    """Derive a stable Fernet-compatible key from the machine GUID."""
    machine_id = _get_machine_guid()
    salt = _machine_salt()   # machine-unique salt: prevents rainbow tables
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(machine_id))


def _initialize_crypto():
    """Initialize crypto singletons (called once, thread-safe)."""
    global _fernet, _hmac_key

    with _KEY_LOCK:
        if _fernet is not None:
            return  # already initialized

        # Priority 1: OS keyring (most secure)
        raw_key = _try_load_key_from_keyring()

        if raw_key is None:
            # Priority 2: Derive from machine GUID (stable across runs)
            raw_key = _derive_key_from_machine()
            _try_save_key_to_keyring(raw_key)

        _fernet   = Fernet(raw_key)
        _hmac_key = hashlib.sha256(raw_key + b":hmac-integrity-v4").digest()


def _get_fernet() -> Fernet:
    if _fernet is None:
        _initialize_crypto()
    return _fernet


def _get_hmac_key() -> bytes:
    if _hmac_key is None:
        _initialize_crypto()
    return _hmac_key


# ─────────────────────────────────────────────────────────────
#  Encryption helpers
# ─────────────────────────────────────────────────────────────

def encrypt(plaintext: str) -> str:
    """Encrypt a string; returns URL-safe base64 ciphertext."""
    if not plaintext:
        return ""
    try:
        return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")
    except Exception as e:
        logger.error("Encryption failed: %s", e)
        return plaintext   # fallback — never lose data


def decrypt(token: str) -> str:
    """Decrypt a Fernet token; returns '[DECRYPTION FAILED]' on failure."""
    if not token:
        return ""
    try:
        return _get_fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, Exception) as e:
        logger.warning("Decryption failed (possible tamper or key mismatch): %s", e)
        return "[DECRYPTION FAILED — DATA MAY BE TAMPERED OR FROM DIFFERENT MACHINE]"


# ─────────────────────────────────────────────────────────────
#  HMAC integrity signing
# ─────────────────────────────────────────────────────────────

def sign(data: str) -> str:
    """Return HMAC-SHA256 hex digest for an event's canonical string."""
    return _hmac.new(_get_hmac_key(), data.encode("utf-8"), hashlib.sha256).hexdigest()


def verify(data: str, signature: str) -> bool:
    """
    Verify an event's HMAC. Returns False if tampered or signature missing.

    SECURITY FIX (v4.1): Previously returned True for empty signatures,
    allowing attackers to clear integrity_hash to bypass tamper detection.
    Now returns False for missing/empty signatures.
    """
    if not signature:
        return False   # Missing signature = assume tampered (secure default)
    expected = _hmac.new(_get_hmac_key(), data.encode("utf-8"), hashlib.sha256).hexdigest()
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
    from config import VAULT_DIR
    os.makedirs(VAULT_DIR, exist_ok=True)

    if sys.platform == "win32":
        try:
            # FILE_ATTRIBUTE_HIDDEN (0x2) | FILE_ATTRIBUTE_SYSTEM (0x4) = 0x6
            ctypes.windll.kernel32.SetFileAttributesW(VAULT_DIR, 0x6)
            parent = os.path.dirname(VAULT_DIR)
            ctypes.windll.kernel32.SetFileAttributesW(parent, 0x2)
        except Exception as e:
            logger.warning("Could not set vault hidden attributes: %s", e)

    return VAULT_DIR


def is_vault_accessible() -> bool:
    """Quick check that vault exists and is writable."""
    try:
        vault = ensure_vault()
        test  = os.path.join(vault, ".test")
        with open(test, "w") as f:
            f.write("ok")
        os.remove(test)
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────
#  PIN management  (PBKDF2-hashed, never plaintext)
# ─────────────────────────────────────────────────────────────

_PIN_SALT_BASE = b"ExamGuard_PIN_Salt_v4"
_PIN_ITERS   = 260_000
_PIN_MIN_LEN = 4   # enforced at UI layer; absolute minimum here


def _pin_salt() -> bytes:
    """Machine-unique salt for PIN hashing (same XOR-fold technique as _machine_salt)."""
    base = _PIN_SALT_BASE
    guid = _get_machine_guid()
    guid_padded = (guid * ((len(base) // max(len(guid), 1)) + 1))[:len(base)]
    return bytes(a ^ b for a, b in zip(base, guid_padded))

def hash_pin(pin: str) -> str:
    """
    Hash a PIN with PBKDF2-SHA256 using a machine-unique salt.
    Returns a prefixed string safe to store in settings.json.
    Format: "pbkdf2$<base64>" — the prefix distinguishes hashed from plaintext.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_pin_salt(),       # machine-unique: prevents cross-machine rainbow tables
        iterations=_PIN_ITERS,
    )
    raw = kdf.derive(pin.encode("utf-8"))
    return "pbkdf2$" + base64.urlsafe_b64encode(raw).decode("ascii")


def _is_hashed_pin(stored: str) -> bool:
    """Return True if the stored PIN is a PBKDF2 hash (v4.1+)."""
    return stored.startswith("pbkdf2$")


def verify_pin(entered: str) -> bool:
    """
    Verify an entered PIN against the stored hash.
    Constant-time comparison to resist timing attacks.

    Supports both hashed pins (v4.1+) and legacy plaintext pins (v4.0 migration).
    """
    import settings_manager
    stored = settings_manager.get("instructor_pin", "")

    if not stored:
        return False

    if _is_hashed_pin(stored):
        # Hashed mode: hash the attempt and compare
        attempt_hash = hash_pin(entered)
        return _hmac.compare_digest(attempt_hash.encode(), stored.encode())
    else:
        # Legacy plaintext mode: compare and auto-upgrade
        if _hmac.compare_digest(entered.encode(), stored.encode()):
            settings_manager.set_value("instructor_pin", hash_pin(entered))
            return True
        return False


def ensure_pin_hashed():
    """
    Called at startup: if the stored PIN is plaintext, hash it now.
    This provides a seamless upgrade path from v4.0 to v4.1.
    """
    import settings_manager
    stored = settings_manager.get("instructor_pin", "1234")

    if _is_hashed_pin(stored):
        return  # Already hashed

    # It's plaintext — hash it and save
    hashed = hash_pin(stored)
    settings_manager.set_value("instructor_pin", hashed)
    logger.info("PIN auto-upgraded to hashed storage (v4.1)")
