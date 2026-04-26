"""
Test üçün: bütün ödənişli klinikaların next_payment_date'ini
keçmiş tarixə qoyur ki, "Borclu Klinikalar" widget'ında görsənsinlər.

İstifadə:
    python make_overdue.py 60     # 60 gün gecikmiş etmək
    python make_overdue.py 0      # bugünə qaytar (borc yoxdur)
    python make_overdue.py 30     # 30 gün gələcəyə (normal)
"""
import sqlite3, sys, os
from datetime import datetime, timedelta

DB_PATH = "dentalapp.db"
if not os.path.exists(DB_PATH):
    print(f"❌ {DB_PATH} tapılmadı"); sys.exit(1)

days = int(sys.argv[1]) if len(sys.argv) > 1 else -60   # mənfi = keçmiş, müsbət = gələcək
target_date = (datetime.utcnow().date() + timedelta(days=-days if days > 0 else abs(days)*-1)).isoformat()
# Düzəliş: müsbət ədəd verirsə "X gün GECİKMİŞ" mənasında olsun
if days > 0:
    target_date = (datetime.utcnow().date() - timedelta(days=days)).isoformat()
elif days < 0:
    target_date = (datetime.utcnow().date() + timedelta(days=-days)).isoformat()
else:
    target_date = datetime.utcnow().date().isoformat()

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

cur.execute("UPDATE subscriptions SET next_payment_date=? WHERE plan != 'free'", (target_date,))
print(f"✅ {cur.rowcount} subscription yeniləndi: next_payment_date = {target_date}")
if days > 0:
    print(f"   → {days} gün GECİKMİŞ (borc widget'ında görsənməlidir)")
elif days < 0:
    print(f"   → {-days} gün gələcəkdə (normal)")
else:
    print(f"   → Bu gün")

conn.commit()
conn.close()
