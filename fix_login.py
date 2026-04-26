"""
Login problemi diaqnozu + tam düzəliş.

İstifadə:
    python fix_login.py                              # diaqnoz
    python fix_login.py <email> <yeni_parol>         # tam düzəliş
"""
import sqlite3, sys, os
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = "dentalapp.db"
if not os.path.exists(DB_PATH):
    print(f"❌ {DB_PATH} tapılmadı"); sys.exit(1)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

if len(sys.argv) < 3:
    print("=" * 90)
    print(f"{'ID':<4} {'User email':<32} {'Rol':<11} {'Klinika':<14} {'CL.email':<28} {'Aktiv'}")
    print("=" * 90)
    cur.execute("""
        SELECT u.id, u.email, u.role, u.is_active, c.id, c.name, c.email, c.is_active
        FROM users u LEFT JOIN clinics c ON c.id=u.clinic_id
        ORDER BY u.role, u.id
    """)
    for r in cur.fetchall():
        uid, ue, role, ua, cid, cn, ce, ca = r
        cl = f"{cn or '—'}" + (" ✗" if cid and not ca else "")
        a = "✓" if ua else "✗"
        sync = ""
        if role == "admin" and ce and ue and ce.lower() != ue.lower():
            sync = " ⚠FƏRQLİ"
        print(f"{uid:<4} {ue or '—':<32} {role:<11} {cl:<14} {ce or '—':<28} {a}{sync}")
    print("=" * 90)
    print("\nDüzəliş üçün: python fix_login.py <email> <yeni_parol>")
    print("Nümunə:       python fix_login.py medistom@gmail.com 123456")
    sys.exit(0)

email = sys.argv[1].strip().lower()
new_pass = sys.argv[2]

# 1. user'i tap (case-insensitive)
cur.execute("SELECT id, email, clinic_id, role, is_active FROM users WHERE LOWER(email)=?", (email,))
user = cur.fetchone()
if not user:
    print(f"❌ '{email}' tapılmadı.")
    cur.execute("SELECT email FROM users")
    print("Mövcud emaillər:", [r[0] for r in cur.fetchall()])
    sys.exit(1)

uid, current_email, cid, role, active = user
print(f"\n→ User #{uid}: {current_email} ({role}), klinika={cid}, aktiv={active}")

# 2. emaili lowercase'ə standartlaşdır
if current_email != email:
    cur.execute("UPDATE users SET email=? WHERE id=?", (email, uid))
    print(f"✅ Email lowercase'ə dəyişdirildi: {current_email} → {email}")

# 3. user aktivləşdir
if not active:
    cur.execute("UPDATE users SET is_active=1 WHERE id=?", (uid,))
    print("✅ User aktivləşdirildi")

# 4. klinikanı aktivləşdir (admin/doctor üçün)
if cid:
    cur.execute("SELECT is_active, email FROM clinics WHERE id=?", (cid,))
    crow = cur.fetchone()
    if crow:
        cactive, cemail = crow
        if not cactive:
            cur.execute("UPDATE clinics SET is_active=1 WHERE id=?", (cid,))
            print("✅ Klinika aktivləşdirildi")
        if role == "admin" and cemail and cemail.lower() != email:
            cur.execute("UPDATE clinics SET email=? WHERE id=?", (email, cid))
            print(f"✅ Klinika emaili sinxronlaşdırıldı: {cemail} → {email}")

# 5. parol və must_change_password sıfırla
hash_ = generate_password_hash(new_pass)
cur.execute("""UPDATE users SET password_hash=?, must_change_password=0,
               reset_token=NULL, reset_token_expiry=NULL WHERE id=?""", (hash_, uid))

# 6. doğrulama
cur.execute("SELECT password_hash FROM users WHERE id=?", (uid,))
ok = check_password_hash(cur.fetchone()[0], new_pass)
print(f"✅ Parol yeniləndi və sınaqdan keçdi: {ok}")

conn.commit()
conn.close()

print(f"\n✓ HAZIR. Login: {email} / {new_pass}")
print("\n⚠  Browser'i Incognito modda açın və ya Ctrl+Shift+R ilə cache təmizləyin.")
print("   Rate-limit səbəbiylə bloklamadısa, 15 dəqiqə gözləyin.")
