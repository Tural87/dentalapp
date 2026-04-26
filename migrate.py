"""
DB migration: bütün admin/superadmin/həkim funksiyaları üçün
Mövcud cədvəllərə çatışmayan sütunları əlavə edir.

İstifadə:
    python migrate.py

Bunu bir dəfədən artıq işə salmaq təhlükəsizdir.
"""
import sqlite3, os, sys

DB_PATH = "dentalapp.db"

if not os.path.exists(DB_PATH):
    print(f"❌ {DB_PATH} tapılmadı. Əvvəlcə tətbiqi bir dəfə açın ki, DB yaransın.")
    sys.exit(1)

MIGRATIONS = [
    # Admin/Superadmin extension
    ("users", "commission_percent", "REAL DEFAULT 0"),
    ("treatment_plans", "doctor_id", "INTEGER"),
    # Doctor/Patient extension
    ("patients", "fin_code", "VARCHAR(20)"),
    ("patients", "family_member_id", "INTEGER"),
    ("patients", "family_relation", "VARCHAR(50)"),
]

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

added, skipped = 0, 0
for table, col, coltype in MIGRATIONS:
    try:
        cur.execute(f"PRAGMA table_info({table})")
        existing = [r[1] for r in cur.fetchall()]
        if not existing:
            print(f"⚠  {table} cədvəli yoxdur — keçilir")
            continue
        if col in existing:
            print(f"⏭  {table}.{col} artıq var")
            skipped += 1
            continue
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")
        print(f"✅ {table}.{col} əlavə edildi")
        added += 1
    except sqlite3.OperationalError as e:
        print(f"❌ {table}.{col} — xəta: {e}")

conn.commit()
conn.close()
print(f"\n📊 Nəticə: {added} əlavə edildi, {skipped} keçildi")
print("Tətbiqi indi yenidən başladın: python main.py")
print("(Yeni cədvəllər — prescriptions, appointments, inventory_items və s. — main.py açılanda avtomatik yaranır)")
