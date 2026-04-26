"""
Birbaşa DB-yə yazaraq istifadəçi parolunu sıfırlayır.
Endpoint'lərdən, sessionlardan, müvəqqəti parol mexanizmindən asılı deyil.

İstifadə:
    python reset_pass.py                          # bütün user'ləri göstər
    python reset_pass.py user@email.com           # parol sıfırla (interaktiv)
    python reset_pass.py user@email.com 123456    # parol sıfırla (parol arqument kimi)
"""
import sqlite3, sys, os
from werkzeug.security import generate_password_hash

DB_PATH = "dentalapp.db"
if not os.path.exists(DB_PATH):
    print(f"❌ {DB_PATH} tapılmadı")
    sys.exit(1)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

if len(sys.argv) < 2:
    print("=" * 80)
    print(f"{'ID':<4} {'Email':<32} {'Rol':<12} {'Klinika':<8} {'Active':<7} {'Must change'}")
    print("=" * 80)
    cur.execute("""
        SELECT u.id, u.email, u.role, u.clinic_id, u.is_active, u.must_change_password
        FROM users u ORDER BY u.role, u.id
    """)
    for r in cur.fetchall():
        uid, email, role, cid, active, must = r
        print(f"{uid:<4} {email or '—':<32} {role:<12} {cid or '—':<8} "
              f"{'✓' if active else '✗':<7} {'Bəli' if must else 'Xeyr'}")
    print("=" * 80)
    print("\nİstifadə:")
    print("  python reset_pass.py <email> [yeni_parol]")
    print("\nNümunə:")
    print("  python reset_pass.py medistom@gmail.com 123456")
    sys.exit(0)

email = sys.argv[1].strip().lower()
new_pass = sys.argv[2] if len(sys.argv) > 2 else None

cur.execute("SELECT id, email, role, is_active FROM users WHERE LOWER(email)=?", (email,))
user = cur.fetchone()
if not user:
    print(f"❌ '{email}' emaili ilə user tapılmadı")
    print("\nMövcud emaillər:")
    cur.execute("SELECT email FROM users")
    for r in cur.fetchall():
        print(f"  • {r[0]}")
    sys.exit(1)

uid, uemail, role, active = user
print(f"\n✓ Tapıldı: id={uid}, email={uemail}, rol={role}, aktiv={'Bəli' if active else 'Xeyr'}")

if not active:
    print("⚠  Bu istifadəçi DEAKTIVdir, login edə bilməyəcək!")
    answer = input("Aktivləşdirək? (b/x): ").strip().lower()
    if answer in ("b", "bəli", "y", "yes"):
        cur.execute("UPDATE users SET is_active=1 WHERE id=?", (uid,))
        print("✅ Aktivləşdirildi")

if not new_pass:
    new_pass = input("\nYeni parol daxil edin: ").strip()

if not new_pass or len(new_pass) < 4:
    print("❌ Parol minimum 4 simvol olmalıdır")
    sys.exit(1)

# parolu hashla və must_change_password sıfırla
hash_ = generate_password_hash(new_pass)
cur.execute("""
    UPDATE users
    SET password_hash=?, must_change_password=0,
        reset_token=NULL, reset_token_expiry=NULL
    WHERE id=?
""", (hash_, uid))
conn.commit()
conn.close()

print(f"\n✅ Uğurla yeniləndi!")
print(f"   Email: {uemail}")
print(f"   Yeni parol: {new_pass}")
print(f"\nİndi login səhifəsinə gedin və bu məlumatlarla daxil olun.")
