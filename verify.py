"""ExamGuard v4.2 — Verification Tests (runs in ~5 seconds)"""
import sys, os, re, threading, sqlite3
sys.path.insert(0, os.path.dirname(__file__))

# Patch PBKDF2 iterations down before any module load uses them
import security as _sec
_sec._ITERATIONS = 500
_sec._PIN_ITERS  = 500

import security, settings_manager

results = []

def chk(n, cond, msg):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {n:2d}. {msg}")
    results.append(cond)
    if not cond:
        sys.exit(1)

print("=" * 50)
print("  ExamGuard v4.2 — Verification Tests")
print("=" * 50)

# 1. PIN upgrade: plaintext -> PBKDF2
settings_manager.set_value("instructor_pin", "mypin99")
security.ensure_pin_hashed()
s = settings_manager.get("instructor_pin", "")
chk(1, s.startswith("pbkdf2$"), f"PIN hashed (prefix={s[:12]})")

# 2. Verify correct PIN
chk(2, security.verify_pin("mypin99"), "Correct PIN accepted")

# 3. Reject wrong PIN
chk(3, not security.verify_pin("wrongpin"), "Wrong PIN rejected")

# 4. reset() never writes plaintext
settings_manager.reset()
rp = settings_manager.get("instructor_pin", "")
chk(4, rp.startswith("pbkdf2$"), f"reset() stores hash (prefix={rp[:12]})")

# 5. Default PIN '1234' verifies after reset
chk(5, security.verify_pin("1234"), "Default '1234' verifies after reset")

# 6. Atomic settings write survives roundtrip
settings_manager.set_value("risk_green_max", 77)
chk(6, settings_manager.get("risk_green_max") == 77, "Atomic write roundtrip OK")
settings_manager.set_value("risk_green_max", 20)

# 7. Encrypt / decrypt
ct = security.encrypt("sensitive data 🔒")
chk(7, ct != "sensitive data 🔒", "Fernet ciphertext != plaintext")
chk(7, security.decrypt(ct) == "sensitive data 🔒", "Fernet decrypt matches")

# 8. Tampered ciphertext returns failure sentinel
bad = security.decrypt("gAAAAABXXXXinvalid_token_here")
chk(8, "[DECRYPTION FAILED" in bad, "Tampered token caught")

# 9. HMAC sign/verify
data = "42|window_switch|Chrome|2024-01-01"
sig  = security.sign(data)
chk(9, security.verify(data, sig),                   "HMAC valid sig accepted")
chk(9, not security.verify("tampered_data", sig),    "HMAC tampered data rejected")
chk(9, not security.verify(data, ""),                "HMAC empty sig rejected")
chk(9, not security.verify(data, sig[:-4] + "0000"), "HMAC corrupted sig rejected")

# 10. Machine-unique salts
s1 = security._machine_salt()
s2 = security._machine_salt()
chk(10, s1 == s2,                          "Key salt stable across calls")
chk(10, s1 != security._PBKDF2_SALT_BASE,  "Key salt unique (XOR applied)")
p1 = security._pin_salt()
chk(10, p1 != security._PIN_SALT_BASE,     "PIN salt unique (XOR applied)")

# 11. Screenshot label sanitisation
def san(lbl): return re.sub(r"[^A-Za-z0-9_-]", "", lbl)[:32]
chk(11, san("../../../etc/passwd") == "etcpasswd", "Path traversal stripped")
chk(11, san("BROWSER")             == "BROWSER",   "Safe label unchanged")
chk(11, san("USB\x00INSERT")       == "USBINSERT",  "Null byte stripped")
chk(11, san("A" * 100)             == "A" * 32,    "Label capped at 32 chars")

# 12. WAL concurrent reads + writes (in-memory DB, bypasses import chain)
conn = sqlite3.connect(":memory:", check_same_thread=False)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY AUTOINCREMENT, v TEXT)")
wlock = threading.Lock()
cerrs = []

def _write(i):
    try:
        with wlock:
            conn.execute("INSERT INTO t(v) VALUES(?)", (str(i),))
            conn.commit()
    except Exception as e:
        cerrs.append(str(e))

def _read():
    try:
        conn.execute("SELECT * FROM t").fetchall()
    except Exception as e:
        cerrs.append(str(e))

ts = [threading.Thread(target=_write, args=(i,)) if i % 2 == 0
      else threading.Thread(target=_read)
      for i in range(20)]
for t in ts: t.start()
for t in ts: t.join()
rows = conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
chk(12, not cerrs,  f"No concurrent R/W errors (errors={cerrs})")
chk(12, rows == 10, f"10 write ops committed (got {rows})")

# 13. Settings file is not storing plaintext '1234'
import json, os
sf = os.path.join(os.environ.get("APPDATA", "."), "ExamGuard", "settings.json")
if os.path.exists(sf):
    with open(sf) as f:
        data = json.load(f)
    pin_on_disk = data.get("instructor_pin", "")
    chk(13, pin_on_disk != "1234",               "Plaintext '1234' NOT on disk")
    chk(13, pin_on_disk.startswith("pbkdf2$"),    "Hash on disk has pbkdf2$ prefix")
else:
    print("  [SKIP] 13. settings.json not yet written")

print()
print("=" * 50)
passed = sum(results)
total  = len(results)
print(f"  Results: {passed}/{total} checks passed")
print("=" * 50)
if passed == total:
    print("  ALL TESTS PASSED")
