"""
Klinika emailini admin istifadəçi emaili ilə sinxronlaşdırır.

İstifadə:
    python sync_emails.py                    # mövcud vəziyyəti göstər
    python sync_emails.py --apply            # admin emailini klinika emaili ilə əvəzlə
    python sync_emails.py --reverse          # klinika emailini admin emaili ilə əvəzlə

Hansı yanaşmanı seçməlisiniz?
- Əgər superadmin'də klinika emailini DƏYİŞDİNİZ və indi həmin yeni emaillə login etmək istəyirsinizsə → --apply
- Əgər köhnə email ilə daxil olub klinika emailini geri qaytarmaq istəyirsinizsə → --reverse
"""
import sqlite3, sys, os

DB_PATH = "dentalapp.db"
if not os.path.exists(DB_PATH):
    print(f"❌ {DB_PATH} tapılmadı")
    sys.exit(1)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Hər klinikanın admin user'i ilə müqayisə
cur.execute("""
    SELECT c.id, c.name, c.email AS clinic_email, u.id AS user_id,
           u.email AS user_email, u.is_active
    FROM clinics c
    LEFT JOIN users u ON u.clinic_id = c.id AND u.role = 'admin'
""")
rows = cur.fetchall()

print("=" * 80)
print(f"{'Klinika':<20} {'Clinic email':<28} {'Admin login email':<28} {'Active'}")
print("=" * 80)
mismatched = []
for r in rows:
    cid, cname, cemail, uid, uemail, uactive = r
    sync = "✓" if cemail == uemail else "✗ FƏRQLİ"
    active = "✓" if uactive else "✗ DEAKTIV"
    print(f"{cname:<20} {cemail or '—':<28} {uemail or '—':<28} {active} {sync}")
    if cemail != uemail and uid:
        mismatched.append((cid, cname, cemail, uid, uemail))
print("=" * 80)

if not mismatched:
    print("\n✓ Bütün email'lər sinxrondur, dəyişiklik tələb olunmur.")
    sys.exit(0)

print(f"\n⚠  {len(mismatched)} klinikada email fərqlidir.\n")

mode = sys.argv[1] if len(sys.argv) > 1 else None

if mode == "--apply":
    # admin user.email = clinic.email
    for cid, cname, cemail, uid, uemail in mismatched:
        if not cemail:
            print(f"⏭  {cname} — klinika emaili boşdur, keçilir")
            continue
        # bu emailə görə başqa user var mı?
        cur.execute("SELECT id FROM users WHERE email=? AND id<>?", (cemail.lower(), uid))
        if cur.fetchone():
            print(f"❌ {cname} — '{cemail}' başqa user'da var, keçilir")
            continue
        cur.execute("UPDATE users SET email=? WHERE id=?", (cemail.lower(), uid))
        print(f"✅ {cname}: admin user emaili '{uemail}' → '{cemail}'")
    conn.commit()
    print("\n✓ Tamamlandı. İndi yeni email ilə login edə bilərsiniz.")
elif mode == "--reverse":
    # clinic.email = user.email
    for cid, cname, cemail, uid, uemail in mismatched:
        if not uemail: continue
        cur.execute("UPDATE clinics SET email=? WHERE id=?", (uemail, cid))
        print(f"✅ {cname}: klinika emaili '{cemail}' → '{uemail}'")
    conn.commit()
    print("\n✓ Tamamlandı.")
else:
    print("Necə davam etmək istəyirsiniz?")
    print("  python sync_emails.py --apply    (admin login emailini klinika emailinə bərabər et)")
    print("  python sync_emails.py --reverse  (klinika emailini admin emailinə bərabər et)")

conn.close()
