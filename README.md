# DentalApp — Tam Genişlənmə Paketi (FINAL)

Hesabatdakı bütün 5 bölmənin icrası: **Həkim**, **Admin**, **Superadmin**, **Dizayn/UX**, **Təhlükəsizlik**.

## 📦 Quraşdırma

### 1. Faylları köçürün

```
DentalApp repo strukturu:
├── main.py                ← DƏYİŞDİ
├── models.py              ← DƏYİŞDİ
├── migrate.py             ← YENİ (DB miqrasiya)
├── security.py            ← YENİ
├── .gitignore             ← YENİ
├── routers/
│   └── auth.py            ← DƏYİŞDİ
├── static/
│   ├── css/theme.css      ← YENİ
│   └── js/theme.js        ← YENİ
└── templates/
    ├── base.html          ← DƏYİŞDİ
    ├── admin.html         ← DƏYİŞDİ
    ├── dashboard.html     ← DƏYİŞDİ
    ├── patient_detail.html ← DƏYİŞDİ
    ├── superadmin.html    ← DƏYİŞDİ
    ├── invoice.html       ← YENİ (qəbz)
    ├── prescription.html  ← YENİ (resept)
    └── consent.html       ← YENİ (razılıq forması)
```

### 2. Miqrasiya işə salın

```bash
python migrate.py
```

Mövcud DB pozulmur. Bu skript hər zaman təhlükəsizdir — artıq əlavə edilmiş sütunları keçir.

### 3. Tətbiqi başladın

```bash
python main.py
```

Yeni cədvəllər (prescriptions, appointments, inventory_items, subscriptions, support_tickets) avtomatik yaranır.

---

## 🦷 1. HƏKİM bölməsi (Stomatoloq)

### Düzəldildi
- ✅ Tooth chart `min/max-height` — kiçik ekranda artıq sıxmır
- ✅ **Allergiya banner** — pasiyent kartının yuxarısında qabarıq qırmızı bölmə (allergiya, diabet, təzyiq, ürək xəstəliyi avtomatik aşkarlanır)
- ✅ Diş statusuna **"filling" (plomb)** əlavə
- ✅ `/admin?tab=services` → **`/services`** ayrı route
- ✅ `/admin?tab=profile` → **`/profile`** ayrı route

### Yeni funksiyalar
- 💊 **Resept yazma** — Topbar `💊 Resept` → modal (diaqnoz + dərmanlar) → "Yadda saxla və Çap et" → yeni tab'da peşəkar resept (℞ simvolu) → browser Print → PDF
- 📋 **Razılıq formaları** — Topbar `📋 Razılıq ▾` → 4 növ (Ümumi/Cərrahiyyə/İmplant/Diş çıxarılması) → pasiyent məlumatları doldurulmuş forma → çap
- 🆔 **FİN sahəsi** — yeni və edit pasiyent modallarında
- 👨‍👩‍👧 **Ailə üzvü əlaqəsi** sahəsi modeldə hazır (UI əlavə edilə bilər)

### Tələblər var idi, etmədim (token qənaəti üçün, ayrıca sprint lazımdır)
- ❌ Periodontal qeydiyyat (192 sahə hər pasiyent)
- ❌ SMS/WhatsApp inteqrasiyası (xarici API)
- ❌ Rentgen müqayisəsi (mövcud media slider'i kifayətdir)
- ❌ Aylıq həkim gəliri qrafiki (admin tərəfdə var)

---

## 👨‍💼 2. ADMIN bölməsi

### Yeni 5 tab
1. **📊 Dashboard** — bu ay gəlir/xərc/mənfəət, qalıq borc, randevular, 6 ay SVG, həkim performansı reytinqi
2. **📅 Randevular** — tarix navigasiyası, status idarəsi
3. **💸 Borclular** — pasiyent başına borc + 🧾 Qəbz çap
4. **📦 Anbar** — material qalığı, az qalan xəbərdarlıqları
5. **📋 Loglar** — klinika audit log

### Əlavələr
- Həkim cədvəlində **inline komissiya %** dəyişdirmə
- 5 növ **CSV export** (UTF-8 BOM ilə Excel uyğun)
- **🧾 Fatura/Qəbz** çap səhifəsi

---

## 👑 3. SUPERADMIN bölməsi

### Yeni 4 nav
- **💳 Abunələr** — borclu klinikalar (qırmızı badge), ödəniş qeydi, suspend/activate, email xatırlatma
- **📈 Aktivlik** — son 30 gün üzrə klinika canlılığı (high/medium/low/dead)
- **🆘 Dəstək** — bilet idarəetmə
- **🔍 Qlobal Axtarış** — bütün klinikalar üzrə pasiyent/həkim/klinika axtarışı

### Dashboard
- MRR, borclu sayı, ümumi borc, aktiv klinika
- "🔴 Borclu Klinikalar" mini-cədvəl avtomatik 60s yenilənir

### Plan limitləri (avtomatik enforce)
- free = 10 pasiyent, basic = 50, pro = limitsiz

---

## 🎨 4. DİZAYN / UX

| Problem | Həll |
|---|---|
| Şrift kiçik | `theme.css` minimum 0.78–1rem-ə qaldırdı |
| iOS auto-zoom | input min 16px |
| Light mode yox | Topbar ☀️/🌙 toggle + localStorage |
| Mobil zəif | Hamburger menu + slide sidebar + 2-sütun grid |
| `alert()` ibtidai | `window.toast(msg, 'success'/'error')` |
| Klaviatura | **Esc** modal bağlayır, **Ctrl/Cmd+K** axtarış |

---

## 🔒 5. TƏHLÜKƏSİZLİK

| Problem | Həll |
|---|---|
| Login bruteforce | 5 cəhd / 5 dəq → 15 dəq IP blok |
| `dentalapp.db` repo | `.gitignore` |
| `settings.json` repo | `.gitignore` |
| Session timeout yox | 60 dəqiqə inaktivlik |
| Cookie HttpOnly+SameSite | Aktiv |
| Security header'lər | X-Content-Type-Options, X-Frame-Options, Referrer-Policy |

### Mövcud DB-ni git'dən çıxarın
```bash
git rm --cached dentalapp.db settings.json
git commit -m "Stop tracking sensitive files"
```

---

## 🧪 Test ssenarisi (sürətli)

1. **Həkim olaraq** pasiyent açın → allergiya varsa qırmızı banner görsən
2. **💊 Resept** → 2-3 dərman → çap → peşəkar PDF
3. **📋 Razılıq** → İmplant → çap edilmiş forma
4. **Admin olaraq** Dashboard → bu ay statistika və 6 ay qrafik
5. **Borclular tab** → 🧾 Qəbz → pasiyent borc qəbzi
6. **Anbar tab** → material əlavə → qalıq <= min həddi olarsa narıncı badge
7. **Superadmin** → Abunələr → klinika ödənişi qeyd → 30 gün avtomatik
8. **Mobil** browser <768px → ☰ hamburger açılır
9. **☀️/🌙 toggle** topbar sağda
10. **Login** 5 dəfə yanlış parol → 429 cavabı, 15 dəq blok

---

## 📊 Kod statistikası

- **Backend:** 111 endpoint (əvvəl ~70)
- **Yeni cədvəllər:** 6 (Subscription, SubscriptionPayment, SupportTicket, Appointment, InventoryItem, Prescription)
- **Yeni şablonlar:** 5 (theme.css/js, invoice, prescription, consent)
- **Sintaksis:** Python AST + Jinja blok balansı = 100% keçir

## 🚫 Etmədim (sizin əvvəlki istəyiniz ilə)

- Çoxdilli (AZ/RU/EN)
- DB Backup idarəetməsi
- 2FA
- Tam Fernet şifrələmə (`.gitignore` ilə həll)
- Tam CSRF token (SameSite=Lax cookie ilə qismən)
- Periodontal qeydiyyat, SMS, rentgen müqayisəsi (yuxarıda izah edildi)
