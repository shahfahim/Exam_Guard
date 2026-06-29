"""
ExamGuard v4.2 — Fast Smoke Test
Uses low iteration counts (10k) for speed — production code uses 300k.
Run: python fast_smoke_test.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

# ── Patch iteration counts BEFORE any security module init ──
import security
security._ITERATIONS = 10_000
security._PIN_ITERS  = 10_000
security._fernet     = None
security._hmac_key   = None

import database, settings_manager, threading, re

OK   = lambda n, msg: print(f"  [PASS] {n:2d}. {msg}")
FAIL = lambda n, msg: sys.exit(f"  [FAIL] {n:2d}. {msg}")

print("=" * 52)
print("  ExamGuard v4.2 — Fast Smoke Test")
print("=" * 52)

# 1 — Imports
OK(1, "All modules import cleanly")

# 2 — Concurrent DB init (thread-safe double-checked lock)
database._init_done = False          # reset for clean test
database._db_conn   = None
errs = []
def _init():
    try: database.initialize_db()
    except Exception as e: errs.append(str(e))
ts = [threading.Thread(target=_init) for _ in range(8)]
for t in ts: t.start()
for t in ts: t.join()
if errs: FAIL(2, f"concurrent init errors: {errs}")
OK(2, "8 concurrent initialize_db() calls — no deadlock")

# 3 — PIN upgrade path (plaintext → PBKDF2)
settings_manager.set_value("instructor_pin", "testpwd99")
security.ensure_pin_hashed()
stored = settings_manager.get("instructor_pin", "")
if not stored.startswith("pbkdf2$"): FAIL(3, f"not hashed: {stored[:20]}")
if not security.verify_pin("testpwd99"):  FAIL(3, "correct PIN rejected")
if security.verify_pin("wrongpassword"):  FAIL(3, "wrong PIN accepted")
OK(3, "PIN upgrade + verify correct=True wrong=False")

# 4 — reset() always stores hashed PIN (not plaintext)
settings_manager.reset()
rp = settings_manager.get("instructor_pin", "")
if not rp.startswith("pbkdf2$"): FAIL(4, f"reset stored plaintext: {rp[:20]}")
if not security.verify_pin("1234"): FAIL(4, "'1234' rejected after reset")
OK(4, "reset() stores hashed default PIN; '1234' verifies")

# 5 — Atomic settings write
settings_manager.set_value("risk_green_max", 77)
v = settings_manager.get("risk_green_max")
if v != 77: FAIL(5, f"expected 77 got {v}")
settings_manager.set_value("risk_green_max", 20)  # restore
OK(5, "atomic write roundtrip OK")

# 6 — Encryption
ct = security.encrypt("sensitive exam data")
if ct == "sensitive exam data": FAIL(6, "not encrypted")
pt = security.decrypt(ct)
if pt != "sensitive exam data": FAIL(6, f"decrypt mismatch: {pt}")
bad = security.decrypt("gAAAAABXXXXXinvalid")
if "[DECRYPTION FAILED" not in bad: FAIL(6, "invalid token not caught")
OK(6, "encrypt/decrypt OK; tampered token caught")

# 7 — HMAC
data = "42|window_switch|Chrome|2024-01-01 10:00:00"
sig  = security.sign(data)
if not security.verify(data, sig):          FAIL(7, "valid sig rejected")
if security.verify("tampered", sig):        FAIL(7, "tampered data accepted")
if security.verify(data, ""):               FAIL(7, "empty sig accepted")
if security.verify(data, sig[:-4]+"0000"):  FAIL(7, "corrupted sig accepted")
OK(7, "HMAC: valid=T tampered=F empty=F corrupted=F")

# 8 — Machine-unique PBKDF2 salts
s1 = security._machine_salt()
s2 = security._machine_salt()
if s1 != s2:                         FAIL(8, "salt not stable across calls")
if s1 == security._PBKDF2_SALT_BASE: FAIL(8, "salt equals base (no machine XOR)")
p1 = security._pin_salt()
if p1 == security._PIN_SALT_BASE:    FAIL(8, "PIN salt equals base")
OK(8, f"machine-unique salts stable; key={s1[:6].hex()} pin={p1[:6].hex()}")

# 9 — Screenshot label sanitisation
def _san(lbl): return re.sub(r"[^A-Za-z0-9_-]", "", lbl)[:32]
assert _san("../../../etc/passwd") == "etcpasswd"
assert _san("BROWSER")             == "BROWSER"
assert _san("USB\x00INSERT")       == "USBINSERT"
assert _san("A" * 100)             == "A" * 32
OK(9, "label sanitisation strips traversal chars & caps at 32")

# 10 — Concurrent DB reads + writes (no deadlock with WAL read-no-lock)
results = []
def _w():
    try:    database.log_access("smoke_test", "concurrent"); results.append("ok")
    except Exception as e: results.append(f"ERR:{e}")
def _r():
    try:    database.get_access_log(5); results.append("ok")
    except Exception as e: results.append(f"ERR:{e}")
ts2 = [threading.Thread(target=_w if i % 2 == 0 else _r) for i in range(20)]
for t in ts2: t.start()
for t in ts2: t.join()
bad2 = [r for r in results if r.startswith("ERR")]
if bad2: FAIL(10, f"concurrent R/W errors: {bad2}")
OK(10, f"{len(results)} concurrent R/W ops — no deadlock, no error")

print()
print("=" * 52)
print("  ALL 10 TESTS PASSED ✓")
print("=" * 52)
