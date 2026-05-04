from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect
from database import engine, SessionLocal
import models
import os, uuid, json, re, unicodedata
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

models.Base.metadata.create_all(bind=engine)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get('SECRET_KEY', 'dental-secret-xK9mP-2024')

from security import init_security, record_login_attempt, client_ip
init_security(app)

from routers.auth import auth as auth_bp
app.register_blueprint(auth_bp)

UPLOAD_DIR = "static/uploads"
SETTINGS_FILE = "settings.json"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def db():
    return SessionLocal()

def err(msg, code=400):
    return jsonify({"error": msg}), code

def clinic_id():
    """Cari sessiyadan clinic_id qaytarır"""
    return session.get('clinic_id')

def is_superadmin():
    return session.get('role') == 'superadmin'

def is_admin():
    return session.get('role') in ('admin', 'superadmin')

@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    return jsonify({"error": str(e), "detail": traceback.format_exc()}), 500

SUPERADMIN_EXPENSES_CLINIC_ID = None

ONLINE_WINDOW_MINUTES = 15


def _safe_path_part(value, fallback):
    text = unicodedata.normalize("NFKD", (value or "").strip())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("ı", "i").replace("İ", "I")
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    text = re.sub(r"[-\s]+", "_", text, flags=re.UNICODE).strip("._ ")
    return text[:80] or fallback


def _clinic_online_info(s, cid):
    cutoff = datetime.utcnow() - timedelta(minutes=ONLINE_WINDOW_MINUTES)
    logs = s.query(models.ActivityLog).filter(
        models.ActivityLog.clinic_id == cid,
        models.ActivityLog.user_id != None,
        models.ActivityLog.action.in_(["login", "logout"])
    ).order_by(models.ActivityLog.created_at.desc()).all()
    latest_by_user = {}
    for log in logs:
        if log.user_id and log.user_id not in latest_by_user:
            latest_by_user[log.user_id] = log
    online_logs = [
        log for log in latest_by_user.values()
        if log.action == "login" and log.created_at and log.created_at >= cutoff
    ]
    latest_seen = max((log.created_at for log in latest_by_user.values() if log.created_at), default=None)
    return {
        "is_online": bool(online_logs),
        "online_users": len(online_logs),
        "last_seen_at": latest_seen.isoformat() if latest_seen else None,
        "status_label": "Online" if online_logs else "Offline",
    }


# ─── AUTH MIDDLEWARE ───────────────────────────────────────────────────────────

@app.before_request
def require_login():
    free = ('/login', '/logout', '/forgot-password', '/reset-password',
            '/static', '/register', '/superadmin/login')
    if any(request.path.startswith(p) for p in free):
        return
    if 'user_id' not in session:
        if request.path.startswith('/api'):
            return jsonify({'error': 'Giriş tələb olunur'}), 401
        return redirect('/login')
    if session.get('must_change_password') and request.path != '/change-password':
        if request.path.startswith('/api'):
            return jsonify({'error': 'Parolu dəyişin'}), 403
        return redirect('/change-password')


# ─── INIT ─────────────────────────────────────────────────────────────────────

def _init_superadmin():
    s = SessionLocal()
    try:
        if not s.query(models.User).filter_by(role='superadmin').first():
            s.add(models.User(
                name='Superadmin', email='super@dental.app',
                password_hash=generate_password_hash('Super1234'),
                role='superadmin', must_change_password=False, is_active=True
            ))
            s.commit()
            print('\n✓ Superadmin yaradıldı: super@dental.app / Super1234\n')
    finally:
        s.close()

_init_superadmin()


# ─── PAGES ────────────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@app.route("/patients")
def patient_list():
    return render_template("patient_list.html")

@app.route("/patients/<int:pid>")
def patient_detail(pid):
    return render_template("patient_detail.html", patient_id=pid)

@app.route("/plans/<int:plan_id>")
def treatment_page(plan_id):
    return render_template("treatment.html", plan_id=plan_id)

@app.route("/admin")
def admin_page():
    return render_template("admin.html")

@app.route("/profile")
def profile_page():
    if 'user_id' not in session: return redirect("/login")
    return render_template("admin.html")

@app.route("/services")
def services_page():
    if 'user_id' not in session: return redirect("/login")
    return render_template("admin.html")

@app.route("/admin/doctors/<int:uid>")
def doctor_profile_page(uid):
    if session.get("role") not in ('admin', 'superadmin'):
        return redirect("/")
    return render_template("doctor_profile_edit.html", doctor_id=uid)

@app.route("/expenses")
def expenses_page():
    return render_template("expenses.html")

@app.route("/uploads/<path:fname>")
def serve_upload(fname):
    return send_from_directory(UPLOAD_DIR, fname)


# ─── SUPERADMIN ───────────────────────────────────────────────────────────────

@app.route("/superadmin")
def superadmin_page():
    if not is_superadmin():
        return redirect("/")
    return render_template("superadmin.html")

@app.route("/api/superadmin/clinics")
def sa_list_clinics():
    if not is_superadmin():
        return err("İcazə yoxdur", 403)
    s = db()
    try:
        clinics = s.query(models.Clinic).order_by(models.Clinic.created_at.desc()).all()
        result = []
        for c in clinics:
            d = c.to_dict()
            d['admin_count'] = s.query(models.User).filter_by(clinic_id=c.id, role='admin').count()
            d['doctor_count'] = s.query(models.User).filter_by(clinic_id=c.id, role='doctor').count()
            d['user_count'] = d['admin_count'] + d['doctor_count']
            d['patient_count'] = s.query(models.Patient).filter_by(clinic_id=c.id).count()
            d.update(_clinic_online_info(s, c.id))
            result.append(d)
        return jsonify(result)
    finally:
        s.close()

@app.route("/api/superadmin/clinics", methods=["POST"])
def sa_create_clinic():
    if not is_superadmin():
        return err("İcazə yoxdur", 403)
    d = request.json or {}
    if not d.get("name") or not d.get("admin_email"):
        return err("Ad və admin email tələb olunur")
    s = db()
    try:
        slug = d.get("slug") or d["name"].lower().replace(" ", "-")
        if s.query(models.Clinic).filter_by(slug=slug).first():
            return err("Bu slug artıq mövcuddur")
        clinic = models.Clinic(
            name=d["name"], slug=slug,
            email=d.get("email"), phone=d.get("phone"),
            address=d.get("address"), plan=d.get("plan", "free")
        )
        s.add(clinic)
        s.commit()
        s.refresh(clinic)
        # Admin user yarat
        from werkzeug.security import generate_password_hash
        import secrets, string
        temp = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))
        admin = models.User(
            clinic_id=clinic.id,
            name=d.get("admin_name", "Admin"),
            email=d["admin_email"].strip().lower(),
            password_hash=generate_password_hash(temp),
            role='admin', must_change_password=True, is_active=True
        )
        s.add(admin)
        s.commit()
        res = clinic.to_dict()
        res['admin_temp_pass'] = temp
        return jsonify(res), 201
    finally:
        s.close()

@app.route("/api/superadmin/clinics/<int:cid>", methods=["PATCH"])
def sa_update_clinic(cid):
    if not is_superadmin():
        return err("İcazə yoxdur", 403)
    d = request.json or {}
    s = db()
    try:
        clinic = s.query(models.Clinic).get(cid)
        if not clinic:
            return err("Tapılmadı", 404)
        if "slug" in d and d["slug"] and d["slug"] != clinic.slug:
            if s.query(models.Clinic).filter(models.Clinic.slug == d["slug"], models.Clinic.id != cid).first():
                return err("Bu slug artıq mövcuddur")
            clinic.slug = d["slug"]
        # Email dəyişəndə klinika admin'inin login emailini də sinxronlaşdır
        if "email" in d and d["email"] and d["email"] != clinic.email:
            new_email = d["email"].strip().lower()
            # bu email başqa istifadəçidə var mı?
            exists = s.query(models.User).filter(models.User.email == new_email).first()
            if exists and exists.clinic_id != cid:
                return err(f"Bu email başqa istifadəçidə istifadə olunur ({new_email})")
            admin = s.query(models.User).filter_by(clinic_id=cid, role='admin').first()
            if admin:
                admin.email = new_email
        for k in ["name", "plan", "is_active", "phone", "address", "email"]:
            if k in d:
                if k == "email" and d[k]:
                    setattr(clinic, k, d[k].strip().lower())
                else:
                    setattr(clinic, k, d[k])
        # Klinika planı dəyişdisə subscription da sinxronlaşsın
        if "plan" in d:
            _ensure_subscription(s, cid)
        s.commit()
        return jsonify(clinic.to_dict())
    finally:
        s.close()

@app.route("/api/superadmin/clinics/<int:cid>", methods=["DELETE"])
def sa_delete_clinic(cid):
    if not is_superadmin():
        return err("İcazə yoxdur", 403)
    s = db()
    try:
        clinic = s.query(models.Clinic).get(cid)
        if not clinic:
            return err("Tapılmadı", 404)
        s.execute(text("PRAGMA foreign_keys=OFF"))
          s.delete(clinic)
          s.commit()
          return jsonify({"ok": True})
    finally:
        s.close()


# ─── PATIENTS ─────────────────────────────────────────────────────────────────

@app.route("/api/superadmin/clinics/<int:cid>/reset-admin-password", methods=["POST"])
def sa_reset_admin_password(cid):
    if not is_superadmin(): return err("İcazə yoxdur", 403)
    import secrets, string
    from werkzeug.security import generate_password_hash
    s = db()
    try:
        admin = s.query(models.User).filter_by(clinic_id=cid, role='admin').first()
        if not admin: return err("Admin tapılmadı", 404)
        temp = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))
        admin.password_hash = generate_password_hash(temp)
        admin.must_change_password = True
        s.commit()
        # email göndər
        _send_reset_email(admin.email, admin.name, temp)
        return jsonify({"ok": True, "temp_pass": temp, "email": admin.email})
    finally:
        s.close()

def _send_reset_email(to_email, name, temp_pass):
    import smtplib, json, os
    from email.mime.text import MIMEText
    cfg = {}
    if os.path.exists("settings.json"):
        with open("settings.json") as f: cfg = json.load(f)
    host = cfg.get("smtp_host",""); user = cfg.get("smtp_user","")
    pwd = cfg.get("smtp_pass",""); port = int(cfg.get("smtp_port",587))
    if not host or not user: return
    body = f"<p>Salam {name},</p><p>Parolunuz sıfırlandı. Müvəqqəti parol: <b>{temp_pass}</b></p><p>Giriş etdikdən sonra dəyişdirin.</p>"
    msg = MIMEText(body, "html", "utf-8")
    msg["Subject"] = "DentalApp - Parol Sıfırlandı"
    msg["From"] = cfg.get("smtp_from", user)
    msg["To"] = to_email
    try:
        with smtplib.SMTP(host, port) as sv:
            sv.ehlo(); sv.starttls(); sv.login(user, pwd); sv.send_message(msg)
    except Exception as e:
        print(f"Email error: {e}")

@app.route("/api/superadmin/smtp", methods=["GET"])
def sa_get_smtp():
    if not is_superadmin(): return err("İcazə yoxdur", 403)
    cfg = {}
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE) as f: cfg = json.load(f)
    return jsonify(cfg)

@app.route("/api/superadmin/smtp", methods=["PUT"])
def sa_update_smtp():
    if not is_superadmin(): return err("İcazə yoxdur", 403)
    d = request.json or {}
    cfg = {}
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE) as f: cfg = json.load(f)
    for k in ["smtp_host","smtp_port","smtp_user","smtp_pass","smtp_from"]:
        if k in d: cfg[k] = d[k]
    with open(SETTINGS_FILE, "w") as f: json.dump(cfg, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True})

# ── Chat ──────────────────────────────────────────────────────────────────────

@app.route("/api/chat/<int:cid>/messages")
def get_messages(cid):
    if not (is_superadmin() or session.get("clinic_id") == cid):
        return err("İcazə yoxdur", 403)
    s = db()
    try:
        msgs = s.query(models.Message).filter_by(clinic_id=cid)\
               .order_by(models.Message.created_at.asc()).limit(100).all()
        # oxunmamışları oxunmuş et
        if session.get("clinic_id") == cid:
            for m in msgs:
                if m.sender_role == "superadmin" and not m.is_read:
                    m.is_read = True
            s.commit()
        elif is_superadmin():
            for m in msgs:
                if m.sender_role == "admin" and not m.is_read:
                    m.is_read = True
            s.commit()
        return jsonify([m.to_dict() for m in msgs])
    finally:
        s.close()

@app.route("/api/chat/<int:cid>/messages", methods=["POST"])
def send_message(cid):
    if not (is_superadmin() or session.get("clinic_id") == cid):
        return err("İcazə yoxdur", 403)
    d = request.json or {}
    if not d.get("text"): return err("Mətn tələb olunur")
    s = db()
    try:
        m = models.Message(clinic_id=cid, text=d["text"],
                           sender_role=session.get("role"),
                           sender_name=session.get("user_name",""))
        s.add(m); s.commit(); s.refresh(m)
        return jsonify(m.to_dict()), 201
    finally:
        s.close()

@app.route("/api/chat/unread")
def chat_unread():
    s = db()
    try:
        if is_superadmin():
            rows = s.query(models.Message.clinic_id,
                           models.Message.clinic_id)\
                    .filter_by(sender_role="admin", is_read=False).all()
            return jsonify({"clinic_ids": list(set(r[0] for r in rows))})
        else:
            cid = session.get("clinic_id")
            count = s.query(models.Message).filter_by(
                clinic_id=cid, sender_role="superadmin", is_read=False).count()
            return jsonify({"count": count})
    finally:
        s.close()

@app.route("/api/chat/upload", methods=["POST"])
def chat_upload():
    f = request.files.get("file")
    if not f: return err("Fayl tələb olunur")
    cid = request.form.get("clinic_id") or session.get("clinic_id")
    if not cid: return err("clinic_id tələb olunur")
    cid = int(cid)
    if not (is_superadmin() or session.get("clinic_id") == cid):
        return err("İcazə yoxdur", 403)
    import tempfile, base64
    # Faylı müvəqqəti oxu, mesaja base64 embed et, disk-də saxlama
    ext = os.path.splitext(f.filename)[1].lower()
    allowed = {'.jpg','.jpeg','.png','.gif','.webp','.pdf','.txt','.xlsx','.docx'}
    if ext not in allowed: return err("Bu fayl formatı dəstəklənmir")
    data = f.read()
    if len(data) > 5*1024*1024: return err("Fayl 5MB-dan böyük ola bilməz")
    is_img = ext in {'.jpg','.jpeg','.png','.gif','.webp'}
    b64 = base64.b64encode(data).decode()
    mime = f.content_type or 'application/octet-stream'
    text = f"[FILE:{f.filename}|{mime}|{b64}]" if not is_img else f"[IMG:{f.filename}|{mime}|{b64}]"
    s = db()
    try:
        m = models.Message(clinic_id=cid, text=text,
                           sender_role=session.get("role"),
                           sender_name=session.get("user_name",""))
        s.add(m); s.commit(); s.refresh(m)
        return jsonify(m.to_dict()), 201
    finally:
        s.close()

# ── Activity Log ──────────────────────────────────────────────────────────────

def log_activity(action, detail="", clinic_id=None, user_id=None):
    try:
        s = db()
        s.add(models.ActivityLog(
            clinic_id=clinic_id or session.get("clinic_id"),
            user_id=user_id or session.get("user_id"),
            action=action, detail=detail,
            ip=client_ip()))
        s.commit()
        s.close()
    except: pass

@app.route("/api/superadmin/logs")
def sa_get_logs():
    if not is_superadmin(): return err("İcazə yoxdur", 403)
    cid = request.args.get("clinic_id")
    s = db()
    try:
        q = s.query(models.ActivityLog).order_by(models.ActivityLog.created_at.desc())
        if cid: q = q.filter_by(clinic_id=int(cid))
        return jsonify([l.to_dict() for l in q.limit(200).all()])
    finally:
        s.close()

@app.route("/api/patients")
def list_patients():
    q = request.args.get("q", "")
    s = db()
    try:
        query = s.query(models.Patient).filter_by(clinic_id=clinic_id())
        if q:
            query = query.filter(models.Patient.name.ilike(f"%{q}%"))
        return jsonify([p.to_dict() for p in query.order_by(models.Patient.created_at.desc()).all()])
    finally:
        s.close()

PLAN_LIMITS = {"free": 10, "basic": 50, "pro": None}  # None = limitsiz

@app.route("/api/patients", methods=["POST"])
def create_patient():
    d = request.json or {}
    if not d.get("name"):
        return err("Ad tələb olunur")
    s = db()
    try:
        cid = clinic_id()
        clinic = s.query(models.Clinic).get(cid)
        if clinic:
            limit = PLAN_LIMITS.get(clinic.plan, None)
            if limit is not None:
                count = s.query(models.Patient).filter_by(clinic_id=cid).count()
                if count >= limit:
                    return err(f"'{clinic.plan}' planında pasiyent limiti ({limit}) doludur. Planı yüksəldin.", 403)
        # boş stringləri None-a çevir (integer/FK sahələri üçün)
        clean = {k: d.get(k) for k in
            ["name","phone","dob","gender","blood_type","complaints","medical_history","allergies","notes","fin_code","family_member_id","family_relation"]}
        if clean.get("family_member_id") in ("", 0, "0"):
            clean["family_member_id"] = None
        elif clean.get("family_member_id") is not None:
            try: clean["family_member_id"] = int(clean["family_member_id"])
            except (ValueError, TypeError): clean["family_member_id"] = None
        p = models.Patient(clinic_id=cid, **clean)
        s.add(p); s.commit(); s.refresh(p)
        s.add(models.TimelineEvent(patient_id=p.id, event_type="created",
                                    description="Xəstə profili yaradıldı", ref_id=p.id))
        s.commit()
        return jsonify(p.to_dict()), 201
    finally:
        s.close()

@app.route("/api/patients/<int:pid>", methods=["GET"])
def get_patient(pid):
    s = db()
    try:
        p = s.query(models.Patient).filter_by(id=pid, clinic_id=clinic_id()).first()
        if not p: return err("Xəstə tapılmadı", 404)
        return jsonify(p.to_dict())
    finally:
        s.close()

@app.route("/api/patients/<int:pid>", methods=["PUT"])
def update_patient(pid):
    d = request.json or {}
    s = db()
    try:
        p = s.query(models.Patient).filter_by(id=pid, clinic_id=clinic_id()).first()
        if not p: return err("Xəstə tapılmadı", 404)
        for k in ["name","phone","dob","gender","blood_type","complaints","medical_history","allergies","notes","fin_code","family_member_id","family_relation"]:
            if k in d:
                v = d[k]
                if k == "family_member_id":
                    if v in ("", 0, "0", None): v = None
                    else:
                        try: v = int(v)
                        except (ValueError, TypeError): v = None
                setattr(p, k, v)
        p.updated_at = datetime.utcnow()
        s.commit()
        return jsonify(p.to_dict())
    finally:
        s.close()

@app.route("/api/patients/<int:pid>", methods=["DELETE"])
def delete_patient(pid):
    s = db()
    try:
        p = s.query(models.Patient).filter_by(id=pid, clinic_id=clinic_id()).first()
        if not p: return err("Xəstə tapılmadı", 404)
        s.delete(p); s.commit()
        return jsonify({"ok": True})
    finally:
        s.close()

@app.route("/api/patients/<int:pid>/timeline")
def get_timeline(pid):
    s = db()
    try:
        p = s.query(models.Patient).filter_by(id=pid, clinic_id=clinic_id()).first()
        if not p: return err("İcazə yoxdur", 403)
        events = s.query(models.TimelineEvent).filter_by(patient_id=pid)\
            .order_by(models.TimelineEvent.created_at.desc()).all()
        return jsonify([e.to_dict() for e in events])
    finally:
        s.close()

@app.route("/api/stats")
def stats():
    from sqlalchemy import func
    cid = clinic_id()
    s = db()
    try:
        total = s.query(func.count(models.Patient.id)).filter_by(clinic_id=cid).scalar()
        today = datetime.utcnow().date().isoformat()
        today_count = s.query(func.count(models.Patient.id)).filter(
            models.Patient.clinic_id == cid,
            func.date(models.Patient.created_at) == today
        ).scalar()
        active = s.query(func.count(models.TreatmentPlan.id)).join(models.Patient).filter(
            models.Patient.clinic_id == cid,
            models.TreatmentPlan.status == "in_progress"
        ).scalar()
        return jsonify({"total_patients": total, "today_patients": today_count, "active_plans": active})
    finally:
        s.close()


# ─── TEETH ────────────────────────────────────────────────────────────────────

@app.route("/api/patients/<int:pid>/teeth")
def get_teeth(pid):
    s = db()
    try:
        if not s.query(models.Patient).filter_by(id=pid, clinic_id=clinic_id()).first():
            return err("İcazə yoxdur", 403)
        teeth = s.query(models.Tooth).filter_by(patient_id=pid).all()
        return jsonify({t.tooth_number: {"status": t.status, "notes": t.notes} for t in teeth})
    finally:
        s.close()

@app.route("/api/patients/<int:pid>/teeth/<int:tnum>", methods=["PUT"])
def update_tooth(pid, tnum):
    d = request.json or {}
    s = db()
    try:
        if not s.query(models.Patient).filter_by(id=pid, clinic_id=clinic_id()).first():
            return err("İcazə yoxdur", 403)
        tooth = s.query(models.Tooth).filter_by(patient_id=pid, tooth_number=tnum).first()
        if tooth:
            tooth.status = d.get("status", tooth.status)
            tooth.notes = d.get("notes", tooth.notes)
        else:
            tooth = models.Tooth(patient_id=pid, tooth_number=tnum,
                                  status=d.get("status", "healthy"), notes=d.get("notes"))
            s.add(tooth)
        s.commit()
        s.add(models.TimelineEvent(patient_id=pid, event_type="tooth_updated",
                                    description=f"Diş {tnum} statusu: {d.get('status')}", ref_id=tnum))
        s.commit()
        return jsonify({"tooth_number": tnum, "status": tooth.status, "notes": tooth.notes})
    finally:
        s.close()


# ─── TREATMENT PLANS ──────────────────────────────────────────────────────────

@app.route("/api/patients/<int:pid>/plans")
def list_plans(pid):
    s = db()
    try:
        if not s.query(models.Patient).filter_by(id=pid, clinic_id=clinic_id()).first():
            return err("İcazə yoxdur", 403)
        plans = s.query(models.TreatmentPlan).filter_by(patient_id=pid)\
            .order_by(models.TreatmentPlan.created_at.desc()).all()
        return jsonify([p.to_dict() for p in plans])
    finally:
        s.close()

@app.route("/api/patients/<int:pid>/plans", methods=["POST"])
def create_plan(pid):
    d = request.json or {}
    if not d.get("title"): return err("Başlıq tələb olunur")
    s = db()
    try:
        if not s.query(models.Patient).filter_by(id=pid, clinic_id=clinic_id()).first():
            return err("İcazə yoxdur", 403)
        plan = models.TreatmentPlan(
            patient_id=pid, title=d.get("title"),
            service_id=d.get("service_id"), template_id=d.get("template_id"),
            cost=float(d.get("cost", 0)), status=d.get("status", "planned"),
            start_date=d.get("start_date"), end_date=d.get("end_date"), notes=d.get("notes")
        )
        s.add(plan); s.commit(); s.refresh(plan)
        if d.get("template_id"):
            selected_ids = d.get("selected_step_ids")
            q = s.query(models.TemplateStep).filter_by(template_id=d["template_id"])
            if selected_ids:
                q = q.filter(models.TemplateStep.id.in_(selected_ids))
            start = datetime.utcnow()
            for i, ts in enumerate(q.order_by(models.TemplateStep.order).all()):
                sched = (start + timedelta(days=ts.default_duration_days * (i+1))).strftime("%Y-%m-%d")
                s.add(models.TreatmentStep(plan_id=plan.id, order=i, title=ts.title,
                                            description=ts.description, scheduled_date=sched))
            s.commit()
        s.add(models.TimelineEvent(patient_id=pid, event_type="plan_created",
                                    description=f"Müalicə planı yaradıldı: {plan.title}", ref_id=plan.id))
        s.commit(); s.refresh(plan)
        return jsonify(plan.to_dict()), 201
    finally:
        s.close()

@app.route("/api/plans/<int:plan_id>")
def get_plan(plan_id):
    s = db()
    try:
        plan = s.query(models.TreatmentPlan).get(plan_id)
        if not plan: return err("Plan tapılmadı", 404)
        p = s.query(models.Patient).filter_by(id=plan.patient_id, clinic_id=clinic_id()).first()
        if not p: return err("İcazə yoxdur", 403)
        return jsonify(plan.to_dict())
    finally:
        s.close()

@app.route("/api/plans/<int:plan_id>", methods=["PUT"])
def update_plan(plan_id):
    d = request.json or {}
    s = db()
    try:
        plan = s.query(models.TreatmentPlan).get(plan_id)
        if not plan: return err("Plan tapılmadı", 404)
        if not s.query(models.Patient).filter_by(id=plan.patient_id, clinic_id=clinic_id()).first():
            return err("İcazə yoxdur", 403)
        for k in ["title","status","start_date","end_date","notes"]:
            if k in d: setattr(plan, k, d[k])
        if "cost" in d: plan.cost = float(d["cost"])
        s.commit()
        return jsonify(plan.to_dict())
    finally:
        s.close()

@app.route("/api/plans/<int:plan_id>", methods=["DELETE"])
def delete_plan(plan_id):
    s = db()
    try:
        plan = s.query(models.TreatmentPlan).get(plan_id)
        if not plan: return err("Plan tapılmadı", 404)
        if not s.query(models.Patient).filter_by(id=plan.patient_id, clinic_id=clinic_id()).first():
            return err("İcazə yoxdur", 403)
        s.delete(plan); s.commit()
        return jsonify({"ok": True})
    finally:
        s.close()

@app.route("/api/plans/<int:plan_id>/steps", methods=["POST"])
def add_step(plan_id):
    d = request.json or {}
    if not d.get("title"): return err("Başlıq tələb olunur")
    s = db()
    try:
        # Plan'ın bu klinikaya aid olduğunu yoxla
        plan = s.query(models.TreatmentPlan).join(models.Patient).filter(
            models.TreatmentPlan.id == plan_id,
            models.Patient.clinic_id == clinic_id()
        ).first()
        if not plan: return err("Plan tapılmadı", 404)
        step = models.TreatmentStep(
            plan_id=plan_id, order=d.get("order", 0), title=d.get("title"),
            description=d.get("description"), status=d.get("status", "pending"),
            scheduled_date=d.get("scheduled_date"), notes=d.get("notes")
        )
        s.add(step); s.commit(); s.refresh(step)
        return jsonify(step.to_dict()), 201
    finally:
        s.close()

@app.route("/api/steps/<int:step_id>", methods=["PUT"])
def update_step(step_id):
    d = request.json or {}
    s = db()
    try:
        step = s.query(models.TreatmentStep).join(models.TreatmentPlan).join(models.Patient).filter(
            models.TreatmentStep.id == step_id,
            models.Patient.clinic_id == clinic_id()
        ).first()
        if not step: return err("Addım tapılmadı", 404)
        for k in ["title","description","status","scheduled_date","completed_date","notes"]:
            if k in d: setattr(step, k, d[k])
        if d.get("status") == "done" and not step.completed_date:
            step.completed_date = datetime.utcnow().strftime("%Y-%m-%d")
        s.commit()
        plan = s.query(models.TreatmentPlan).get(step.plan_id)
        if plan and plan.steps and all(st.status in ("done","skipped") for st in plan.steps):
            plan.status = "completed"; s.commit()
        return jsonify(step.to_dict())
    finally:
        s.close()

@app.route("/api/steps/<int:step_id>", methods=["DELETE"])
def delete_step(step_id):
    s = db()
    try:
        step = s.query(models.TreatmentStep).join(models.TreatmentPlan).join(models.Patient).filter(
            models.TreatmentStep.id == step_id,
            models.Patient.clinic_id == clinic_id()
        ).first()
        if not step: return err("Addım tapılmadı", 404)
        s.delete(step); s.commit()
        return jsonify({"ok": True})
    finally:
        s.close()


# ─── SERVICES ─────────────────────────────────────────────────────────────────

@app.route("/api/services")
def list_services():
    s = db()
    try:
        return jsonify([svc.to_dict() for svc in
                        s.query(models.Service).filter_by(clinic_id=clinic_id()).all()])
    finally:
        s.close()

@app.route("/api/services", methods=["POST"])
def create_service():
    d = request.json or {}
    s = db()
    try:
        svc = models.Service(clinic_id=clinic_id(), user_id=session["user_id"],
                              name=d.get("name",""), icon=d.get("icon"), description=d.get("description"))
        s.add(svc); s.commit(); s.refresh(svc)
        return jsonify(svc.to_dict()), 201
    finally:
        s.close()

@app.route("/api/services/<int:svc_id>", methods=["PUT"])
def update_service(svc_id):
    d = request.json or {}
    s = db()
    try:
        svc = s.query(models.Service).filter_by(id=svc_id, clinic_id=clinic_id()).first()
        if not svc: return err("Xidmət tapılmadı", 404)
        for k in ["name","icon","description"]:
            if k in d: setattr(svc, k, d[k])
        s.commit()
        return jsonify(svc.to_dict())
    finally:
        s.close()

@app.route("/api/services/<int:svc_id>", methods=["DELETE"])
def delete_service(svc_id):
    s = db()
    try:
        svc = s.query(models.Service).filter_by(id=svc_id, clinic_id=clinic_id()).first()
        if not svc: return err("Xidmət tapılmadı", 404)
        s.delete(svc); s.commit()
        return jsonify({"ok": True})
    finally:
        s.close()

@app.route("/api/services/<int:svc_id>/templates", methods=["POST"])
def create_template(svc_id):
    d = request.json or {}
    s = db()
    try:
        svc = s.query(models.Service).filter_by(id=svc_id, clinic_id=clinic_id()).first()
        if not svc: return err("Xidmət tapılmadı", 404)
        t = models.ServiceTemplate(service_id=svc_id, name=d.get("name",""), description=d.get("description"))
        s.add(t); s.commit(); s.refresh(t)
        return jsonify(t.to_dict()), 201
    finally:
        s.close()

@app.route("/api/templates/<int:tmpl_id>", methods=["DELETE"])
def delete_template(tmpl_id):
    s = db()
    try:
        t = s.query(models.ServiceTemplate).join(models.Service).filter(
            models.ServiceTemplate.id == tmpl_id,
            models.Service.clinic_id == clinic_id()
        ).first()
        if not t: return err("Şablon tapılmadı", 404)
        s.delete(t); s.commit()
        return jsonify({"ok": True})
    finally:
        s.close()

@app.route("/api/templates/<int:tmpl_id>/steps", methods=["POST"])
def add_template_step(tmpl_id):
    d = request.json or {}
    s = db()
    try:
        # Şablonun bu klinikaya aid olduğunu yoxla
        t = s.query(models.ServiceTemplate).join(models.Service).filter(
            models.ServiceTemplate.id == tmpl_id,
            models.Service.clinic_id == clinic_id()
        ).first()
        if not t: return err("Şablon tapılmadı", 404)
        step = models.TemplateStep(template_id=tmpl_id, order=d.get("order",0),
                                    title=d.get("title",""), description=d.get("description"),
                                    default_duration_days=d.get("default_duration_days",7),
                                    price=float(d.get("price",0)))
        s.add(step); s.commit(); s.refresh(step)
        return jsonify(step.to_dict()), 201
    finally:
        s.close()

@app.route("/api/template-steps/<int:step_id>", methods=["DELETE"])
def delete_template_step(step_id):
    s = db()
    try:
        step = s.query(models.TemplateStep).join(models.ServiceTemplate).join(models.Service).filter(
            models.TemplateStep.id == step_id,
            models.Service.clinic_id == clinic_id()
        ).first()
        if not step: return err("Addım tapılmadı", 404)
        s.delete(step); s.commit()
        return jsonify({"ok": True})
    finally:
        s.close()


# ─── MEDIA ────────────────────────────────────────────────────────────────────

@app.route("/api/media/upload", methods=["POST"])
def upload_media():
    f = request.files.get("file")
    if not f: return err("Fayl tələb olunur")
    pid = request.form.get("patient_id")
    if not pid: return err("patient_id tələb olunur")
    s = db()
    try:
        cid = clinic_id()
        patient = s.query(models.Patient).filter_by(id=int(pid), clinic_id=cid).first()
        if not patient:
            return err("İcazə yoxdur", 403)
        clinic = s.query(models.Clinic).get(cid)
        ext = os.path.splitext(f.filename)[1]
        media_type = _safe_path_part(request.form.get("type", "other"), "other").lower()
        clinic_folder = _safe_path_part(getattr(clinic, "name", ""), f"clinic_{cid}")
        patient_folder = _safe_path_part(getattr(patient, "name", ""), f"patient_{pid}")
        fname = f"{media_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
        folder = os.path.join(UPLOAD_DIR, clinic_folder, f"{patient_folder}_{pid}", media_type)
        os.makedirs(folder, exist_ok=True)
        fpath = os.path.join(folder, fname)
        rel_path = "/".join([clinic_folder, f"{patient_folder}_{pid}", media_type, fname])
        f.save(fpath)
        m = models.Media(patient_id=int(pid), step_id=request.form.get("step_id") or None,
                          tooth_number=request.form.get("tooth_number") or None,
                          type=request.form.get("type","other"),
                          filename=rel_path, filepath=fpath, caption=request.form.get("caption"))
        s.add(m); s.commit(); s.refresh(m)
        return jsonify(m.to_dict()), 201
    finally:
        s.close()

@app.route("/api/patients/<int:pid>/media")
def get_media(pid):
    s = db()
    try:
        if not s.query(models.Patient).filter_by(id=pid, clinic_id=clinic_id()).first():
            return err("İcazə yoxdur", 403)
        q = s.query(models.Media).filter_by(patient_id=pid)
        if request.args.get("type"):
            q = q.filter_by(type=request.args.get("type"))
        return jsonify([m.to_dict() for m in q.order_by(models.Media.uploaded_at.desc()).all()])
    finally:
        s.close()

@app.route("/api/media/<int:mid>", methods=["DELETE"])
def delete_media(mid):
    s = db()
    try:
        m = s.query(models.Media).join(models.Patient).filter(
            models.Media.id == mid,
            models.Patient.clinic_id == clinic_id()
        ).first()
        if not m: return err("Media tapılmadı", 404)
        if m.filepath and os.path.exists(m.filepath):
            os.remove(m.filepath)
        s.delete(m); s.commit()
        return jsonify({"ok": True})
    finally:
        s.close()


# ─── EXPENSES ─────────────────────────────────────────────────────────────────

@app.route("/api/expenses")
def list_expenses():
    s = db()
    try:
        if is_superadmin():
            q = s.query(models.Expense).filter(models.Expense.clinic_id == None)
        else:
            q = s.query(models.Expense).filter_by(clinic_id=clinic_id())
            if session.get("role") == "doctor":
                q = q.filter_by(user_id=session["user_id"])
        return jsonify([e.to_dict() for e in q.order_by(models.Expense.purchase_date.desc()).all()])
    finally:
        s.close()

@app.route("/api/superadmin/monitor")
def sa_monitor():
    if not is_superadmin(): return err("İcazə yoxdur", 403)
    try:
        import psutil, platform
        cpu = psutil.cpu_percent(interval=0.5)
        cpu_freq = psutil.cpu_freq()
        ram = psutil.virtual_memory()
        # disk partitions
        disks = []
        for p in psutil.disk_partitions(all=False):
            try:
                u = psutil.disk_usage(p.mountpoint)
                disks.append({
                    "device": p.device, "mount": p.mountpoint,
                    "total": round(u.total/1024**3, 1),
                    "used": round(u.used/1024**3, 1),
                    "free": round(u.free/1024**3, 1),
                    "percent": round(u.percent, 1)
                })
            except: pass
        return jsonify({
            "cpu": round(cpu, 1),
            "cpu_cores": psutil.cpu_count(logical=False),
            "cpu_threads": psutil.cpu_count(logical=True),
            "cpu_freq": round(cpu_freq.current/1000, 2) if cpu_freq else None,
            "ram": round(ram.percent, 1),
            "ram_used": round(ram.used/1024**3, 1),
            "ram_total": round(ram.total/1024**3, 1),
            "ram_available": round(ram.available/1024**3, 1),
            "disks": disks,
            "platform": platform.system()
        })
    except ImportError:
        return err("psutil quraşdırılmayıb", 500)


@app.route("/api/expenses", methods=["POST"])
def create_expense():
    d = request.json or {}
    s = db()
    try:
        e = models.Expense(clinic_id=SUPERADMIN_EXPENSES_CLINIC_ID if is_superadmin() else clinic_id(),
                            user_id=session["user_id"],
                            product=d.get("product",""), company=d.get("company"),
                            purchase_date=d.get("purchase_date"), quantity=int(d.get("quantity",1)),
                            price=float(d.get("price",0)), category=d.get("category"))
        s.add(e); s.commit(); s.refresh(e)
        return jsonify(e.to_dict()), 201
    finally:
        s.close()

@app.route("/api/expenses/<int:eid>", methods=["PUT"])
def update_expense(eid):
    d = request.json or {}
    s = db()
    try:
        e = s.query(models.Expense).filter_by(id=eid, clinic_id=clinic_id()).first()
        if not e: return err("Tapılmadı", 404)
        if session.get("role") == "doctor" and e.user_id != session["user_id"]:
            return err("İcazə yoxdur", 403)
        for k in ["product","company","purchase_date","category"]:
            if k in d: setattr(e, k, d[k])
        if "quantity" in d: e.quantity = int(d["quantity"])
        if "price" in d: e.price = float(d["price"])
        s.commit()
        return jsonify(e.to_dict())
    finally:
        s.close()

@app.route("/api/expenses/<int:eid>", methods=["DELETE"])
def delete_expense(eid):
    s = db()
    try:
        e = s.query(models.Expense).filter_by(id=eid, clinic_id=clinic_id()).first()
        if not e: return err("Tapılmadı", 404)
        if session.get("role") == "doctor" and e.user_id != session["user_id"]:
            return err("İcazə yoxdur", 403)
        s.delete(e); s.commit()
        return jsonify({"ok": True})
    finally:
        s.close()

@app.route("/api/expenses/export")
def export_expenses():
    import openpyxl
    from io import BytesIO
    from flask import send_file
    s = db()
    try:
        q = s.query(models.Expense).filter_by(clinic_id=clinic_id())
        if session.get("role") == "doctor":
            q = q.filter_by(user_id=session["user_id"])
        rows = q.order_by(models.Expense.purchase_date.desc()).all()
    finally:
        s.close()
    wb = openpyxl.Workbook()
    ws = wb.active; ws.title = "Xərclər"
    ws.append(["#","Məhsul","Firma","Kateqoriya","Tarix","Say","Qiymət (₼)","Cəm (₼)"])
    for i, e in enumerate(rows, 1):
        ws.append([i, e.product, e.company or "", e.category or "",
                   e.purchase_date or "", e.quantity, e.price, (e.quantity or 1)*(e.price or 0)])
    buf = BytesIO(); wb.save(buf); buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="xercler.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ─── PAYMENTS ─────────────────────────────────────────────────────────────────

@app.route("/api/patients/<int:pid>/payments")
def list_payments(pid):
    s = db()
    try:
        if not s.query(models.Patient).filter_by(id=pid, clinic_id=clinic_id()).first():
            return err("İcazə yoxdur", 403)
        pays = s.query(models.Payment).filter_by(patient_id=pid).order_by(models.Payment.date.desc()).all()
        plans = s.query(models.TreatmentPlan).filter_by(patient_id=pid).all()
        total_cost = sum(p.cost or 0 for p in plans)
        total_paid = sum(p.amount or 0 for p in pays)
        return jsonify({"payments": [p.to_dict() for p in pays], "total_cost": total_cost,
                        "total_paid": total_paid, "debt": max(0, total_cost - total_paid)})
    finally:
        s.close()

@app.route("/api/patients/<int:pid>/payments", methods=["POST"])
def add_payment(pid):
    d = request.json or {}
    s = db()
    try:
        if not s.query(models.Patient).filter_by(id=pid, clinic_id=clinic_id()).first():
            return err("İcazə yoxdur", 403)
        p = models.Payment(patient_id=pid, plan_id=d.get("plan_id"),
                            amount=float(d.get("amount",0)), date=d.get("date"), notes=d.get("notes"))
        s.add(p); s.commit(); s.refresh(p)
        return jsonify(p.to_dict()), 201
    finally:
        s.close()

@app.route("/api/payments/<int:pid>", methods=["DELETE"])
def delete_payment(pid):
    s = db()
    try:
        p = s.query(models.Payment).join(models.Patient).filter(
            models.Payment.id == pid,
            models.Patient.clinic_id == clinic_id()
        ).first()
        if not p: return err("Tapılmadı", 404)
        s.delete(p); s.commit()
        return jsonify({"ok": True})
    finally:
        s.close()


# ─── DASHBOARD TIMELINE ───────────────────────────────────────────────────────

@app.route("/api/dashboard/active-timeline")
def active_timeline():
    cid = clinic_id()
    s = db()
    try:
        active_pids = [r[0] for r in
                       s.query(models.TreatmentPlan.patient_id).join(models.Patient)
                        .filter(models.Patient.clinic_id == cid,
                                models.TreatmentPlan.status == "in_progress").distinct().limit(10).all()]
        result = []
        for pid in active_pids:
            pt = s.query(models.Patient).get(pid)
            if not pt: continue
            events = s.query(models.TimelineEvent).filter_by(patient_id=pid)\
                     .order_by(models.TimelineEvent.created_at.desc()).limit(3).all()
            result.append({"patient": {"id": pt.id, "name": pt.name},
                           "events": [e.to_dict() for e in events]})
        return jsonify(result)
    finally:
        s.close()


# ─── ADMIN SETTINGS ───────────────────────────────────────────────────────────

@app.route("/api/admin/settings")
def get_settings():
    s = db()
    try:
        clinic = s.query(models.Clinic).get(clinic_id())
        if clinic:
            return jsonify({"clinic_name": clinic.name, "phone": clinic.phone or "",
                            "address": clinic.address or "", "email": clinic.email or ""})
        return jsonify({"clinic_name": "DentalApp", "phone": "", "address": "", "email": ""})
    finally:
        s.close()

@app.route("/api/admin/settings", methods=["PUT"])
def update_settings():
    if not is_admin(): return err("İcazə yoxdur", 403)
    d = request.json or {}
    s = db()
    try:
        clinic = s.query(models.Clinic).get(clinic_id())
        if clinic:
            if "clinic_name" in d: clinic.name = d["clinic_name"]
            if "phone" in d: clinic.phone = d["phone"]
            if "address" in d: clinic.address = d["address"]
            if "email" in d: clinic.email = d["email"]
            s.commit()
            return jsonify({"clinic_name": clinic.name, "phone": clinic.phone,
                            "address": clinic.address, "email": clinic.email})
        return err("Klinika tapılmadı", 404)
    finally:
        s.close()


# ─── SUPERADMIN: ABUNƏ / BORC / DƏSTƏK / QLOBAL AXTARIŞ ───────────────────────

PLAN_DEFAULT_FEE = {"free": 0, "basic": 30, "pro": 80}  # AZN/ay

PLAN_DEFAULTS = {
    "free":  {"monthly_fee": 0,  "max_doctors": 1,  "max_admins": 1, "max_patients_per_day": 10, "max_total_patients": 50,   "description": "Pulsuz plan"},
    "basic": {"monthly_fee": 30, "max_doctors": 3,  "max_admins": 2, "max_patients_per_day": 30, "max_total_patients": 300,  "description": "Əsas plan"},
    "pro":   {"monthly_fee": 80, "max_doctors": 10, "max_admins": 5, "max_patients_per_day": 100,"max_total_patients": 9999, "description": "Pro plan"},
}

def _ensure_plan_configs(s):
    for pname, defaults in PLAN_DEFAULTS.items():
        if not s.query(models.PlanConfig).filter_by(plan_name=pname).first():
            s.add(models.PlanConfig(plan_name=pname, **defaults))
    s.commit()

@app.route("/api/superadmin/plans")
def sa_list_plans():
    if not is_superadmin(): return err("İcazə yoxdur", 403)
    s = db()
    try:
        _ensure_plan_configs(s)
        configs = s.query(models.PlanConfig).all()
        clinic_counts = {}
        for c in s.query(models.Clinic).all():
            clinic_counts[c.plan or 'free'] = clinic_counts.get(c.plan or 'free', 0) + 1
        out = []
        for pc in configs:
            d = pc.to_dict()
            d['clinic_count'] = clinic_counts.get(pc.plan_name, 0)
            out.append(d)
        out.sort(key=lambda x: list(PLAN_DEFAULTS.keys()).index(x['plan_name']) if x['plan_name'] in PLAN_DEFAULTS else 99)
        return jsonify(out)
    finally:
        s.close()

@app.route("/api/superadmin/plans/<string:plan_name>", methods=["PUT"])
def sa_update_plan(plan_name):
    if not is_superadmin(): return err("İcazə yoxdur", 403)
    if plan_name not in PLAN_DEFAULTS: return err("Yanlış plan adı", 400)
    d = request.json or {}
    s = db()
    try:
        _ensure_plan_configs(s)
        pc = s.query(models.PlanConfig).filter_by(plan_name=plan_name).first()
        for k in ("monthly_fee", "max_doctors", "max_admins", "max_patients_per_day", "max_total_patients", "description"):
            if k in d:
                setattr(pc, k, float(d[k]) if k == "monthly_fee" else (int(d[k]) if k != "description" else d[k]))
        s.commit()
        return jsonify(pc.to_dict())
    finally:
        s.close()

def _ensure_subscription(s, cid, plan=None):
    """Subscription yarat və klinika planı ilə sinxronlaşdır."""
    sub = s.query(models.Subscription).filter_by(clinic_id=cid).first()
    clinic = s.query(models.Clinic).get(cid)
    target_plan = plan or (clinic.plan if clinic else 'free') or 'free'
    if not sub:
        sub = models.Subscription(clinic_id=cid, plan=target_plan,
                                  monthly_fee=PLAN_DEFAULT_FEE.get(target_plan, 0),
                                  status='active')
        s.add(sub); s.commit(); s.refresh(sub)
    # Sinxronlaşdırma: klinika planı dəyişibsə subscription da dəyişsin
    if clinic and clinic.plan and sub.plan != clinic.plan:
        sub.plan = clinic.plan
        sub.monthly_fee = PLAN_DEFAULT_FEE.get(clinic.plan, sub.monthly_fee or 0)
        s.commit()
    # next_payment_date boşdursa və plan ödənişlidirsə, 30 gün sonraya qoy
    if not sub.next_payment_date and sub.plan and sub.plan != 'free':
        sub.next_payment_date = (datetime.utcnow().date() + timedelta(days=30)).isoformat()
        s.commit()
    return sub

def _days_overdue(next_payment_date):
    if not next_payment_date: return 0
    try:
        nd = datetime.fromisoformat(next_payment_date).date()
        delta = (datetime.utcnow().date() - nd).days
        return delta if delta > 0 else 0
    except Exception:
        return 0

@app.route("/api/superadmin/subscriptions")
def sa_list_subscriptions():
    if not is_superadmin(): return err("İcazə yoxdur", 403)
    s = db()
    try:
        clinics = s.query(models.Clinic).all()
        out = []
        for c in clinics:
            sub = _ensure_subscription(s, c.id, c.plan or 'free')
            overdue = _days_overdue(sub.next_payment_date)
            debt = (sub.monthly_fee or 0) * (overdue // 30 + 1) if overdue > 0 else 0
            out.append({
                "clinic_id": c.id, "clinic_name": c.name, "slug": c.slug,
                "is_active": c.is_active,
                "plan": sub.plan, "monthly_fee": sub.monthly_fee or 0,
                "last_paid_date": sub.last_paid_date,
                "next_payment_date": sub.next_payment_date,
                "status": sub.status,
                "days_overdue": overdue,
                "debt_amount": debt,
            })
        return jsonify(out)
    finally:
        s.close()

@app.route("/api/superadmin/subscriptions/<int:cid>", methods=["PUT"])
def sa_update_subscription(cid):
    if not is_superadmin(): return err("İcazə yoxdur", 403)
    d = request.json or {}
    s = db()
    try:
        sub = _ensure_subscription(s, cid)
        for k in ("plan", "monthly_fee", "next_payment_date", "status"):
            if k in d: setattr(sub, k, d[k])
        # plan dəyişəndə klinikanın plan'ını da yenilə
        if "plan" in d:
            clinic = s.query(models.Clinic).get(cid)
            if clinic: clinic.plan = d["plan"]
        s.commit()
        return jsonify(sub.to_dict())
    finally:
        s.close()

@app.route("/api/superadmin/subscriptions/<int:cid>/pay", methods=["POST"])
def sa_record_payment(cid):
    """Ödəniş qeyd et — last_paid + next_payment_date 30 gün irəli"""
    if not is_superadmin(): return err("İcazə yoxdur", 403)
    d = request.json or {}
    s = db()
    try:
        sub = _ensure_subscription(s, cid)
        amount = float(d.get("amount") or sub.monthly_fee or 0)
        today = datetime.utcnow().date()
        # period_start = mövcud next_payment_date (varsa) və ya bugün
        try:
            base = datetime.fromisoformat(sub.next_payment_date).date() if sub.next_payment_date else today
        except Exception:
            base = today
        if base < today: base = today
        period_end = base + timedelta(days=30)
        pay = models.SubscriptionPayment(
            clinic_id=cid, amount=amount,
            paid_date=today.isoformat(),
            period_start=base.isoformat(),
            period_end=period_end.isoformat(),
            notes=d.get("notes")
        )
        s.add(pay)
        sub.last_paid_date = today.isoformat()
        sub.next_payment_date = period_end.isoformat()
        sub.status = 'active'
        # bloklanmışdısa aç
        clinic = s.query(models.Clinic).get(cid)
        if clinic and not clinic.is_active:
            clinic.is_active = True
        s.commit()
        return jsonify({"ok": True, "payment": pay.to_dict(), "subscription": sub.to_dict()})
    finally:
        s.close()

@app.route("/api/superadmin/subscriptions/<int:cid>/payments")
def sa_subscription_payments(cid):
    if not is_superadmin(): return err("İcazə yoxdur", 403)
    s = db()
    try:
        items = s.query(models.SubscriptionPayment).filter_by(clinic_id=cid)\
                  .order_by(models.SubscriptionPayment.id.desc()).all()
        return jsonify([p.to_dict() for p in items])
    finally:
        s.close()

@app.route("/api/superadmin/subscriptions/<int:cid>/suspend", methods=["POST"])
def sa_suspend_clinic(cid):
    if not is_superadmin(): return err("İcazə yoxdur", 403)
    s = db()
    try:
        clinic = s.query(models.Clinic).get(cid)
        if not clinic: return err("Klinika tapılmadı", 404)
        clinic.is_active = False
        sub = _ensure_subscription(s, cid)
        sub.status = 'suspended'
        s.commit()
        return jsonify({"ok": True})
    finally:
        s.close()

@app.route("/api/superadmin/subscriptions/<int:cid>/activate", methods=["POST"])
def sa_activate_clinic(cid):
    if not is_superadmin(): return err("İcazə yoxdur", 403)
    s = db()
    try:
        clinic = s.query(models.Clinic).get(cid)
        if not clinic: return err("Klinika tapılmadı", 404)
        clinic.is_active = True
        sub = _ensure_subscription(s, cid)
        sub.status = 'active'
        s.commit()
        return jsonify({"ok": True})
    finally:
        s.close()

@app.route("/api/superadmin/subscriptions/<int:cid>/remind", methods=["POST"])
def sa_send_reminder(cid):
    """Klinika admin emailinə xatırlatma. SMTP konfiqurasiyası mövcuddursa göndərir."""
    if not is_superadmin(): return err("İcazə yoxdur", 403)
    s = db()
    try:
        clinic = s.query(models.Clinic).get(cid)
        if not clinic: return err("Klinika tapılmadı", 404)
        admin = s.query(models.User).filter_by(clinic_id=cid, role='admin').first()
        to_email = (admin.email if admin else None) or clinic.email
        if not to_email:
            return err("Email tapılmadı", 400)
        sub = _ensure_subscription(s, cid)
        overdue = _days_overdue(sub.next_payment_date)
        body = (f"Hörmətli {clinic.name},\n\n"
                f"DentalApp abunəlik haqqı ödənişiniz "
                f"{'gecikib (' + str(overdue) + ' gün)' if overdue > 0 else 'yaxınlaşır'}.\n"
                f"Plan: {sub.plan.upper()} — {sub.monthly_fee} AZN/ay\n"
                f"Növbəti ödəniş tarixi: {sub.next_payment_date or '—'}\n\n"
                f"Xahiş edirik vaxtında ödəyəsiniz.\n\nDentalApp")
        try:
            _send_smtp(to_email, "Abunəlik xatırlatması — DentalApp", body)
            ok = True; msg = "Email göndərildi"
        except Exception as e:
            ok = False; msg = f"SMTP xətası: {e}"
        s.add(models.ActivityLog(clinic_id=cid, action="payment_reminder",
                                 detail=f"to={to_email} ok={ok}"))
        s.commit()
        return jsonify({"ok": ok, "message": msg, "to": to_email})
    finally:
        s.close()

def _send_smtp(to_email, subject, body):
    """Sadə SMTP göndərici - settings.json'dan oxuyur"""
    import smtplib
    from email.mime.text import MIMEText
    if not os.path.exists(SETTINGS_FILE):
        raise RuntimeError("SMTP konfiqurasiyası yoxdur")
    cfg = json.load(open(SETTINGS_FILE))
    host = cfg.get("smtp_host"); port = int(cfg.get("smtp_port") or 587)
    user = cfg.get("smtp_user"); pw = cfg.get("smtp_pass")
    sender = cfg.get("smtp_from") or user
    if not (host and user and pw):
        raise RuntimeError("SMTP tam doldurulmayıb")
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject; msg["From"] = sender; msg["To"] = to_email
    with smtplib.SMTP(host, port, timeout=10) as srv:
        srv.starttls(); srv.login(user, pw)
        srv.sendmail(sender, [to_email], msg.as_string())


# ─── BILLING DASHBOARD (MRR, gəlir) ───────────────────────────────────────────

@app.route("/api/superadmin/billing/summary")
def sa_billing_summary():
    if not is_superadmin(): return err("İcazə yoxdur", 403)
    s = db()
    try:
        clinics = s.query(models.Clinic).all()
        total_clinics = len(clinics)
        active_clinics = sum(1 for c in clinics if c.is_active)
        mrr = 0
        overdue_count = 0; overdue_amount = 0
        plan_breakdown = {"free": 0, "basic": 0, "pro": 0}
        for c in clinics:
            sub = _ensure_subscription(s, c.id, c.plan or 'free')
            plan_breakdown[sub.plan] = plan_breakdown.get(sub.plan, 0) + 1
            if c.is_active and (sub.monthly_fee or 0) > 0:
                mrr += sub.monthly_fee or 0
            od = _days_overdue(sub.next_payment_date)
            if od > 0 and sub.plan != 'free':
                overdue_count += 1
                overdue_amount += (sub.monthly_fee or 0) * (od // 30 + 1)
        # son 12 ay ödənişləri
        from collections import OrderedDict
        monthly = OrderedDict()
        now = datetime.utcnow().date()
        for i in range(11, -1, -1):
            y = now.year; m = now.month - i
            while m <= 0: m += 12; y -= 1
            monthly[f"{y:04d}-{m:02d}"] = 0
        pays = s.query(models.SubscriptionPayment).all()
        for p in pays:
            if p.paid_date and p.paid_date[:7] in monthly:
                monthly[p.paid_date[:7]] += p.amount or 0
        return jsonify({
            "total_clinics": total_clinics,
            "active_clinics": active_clinics,
            "mrr": round(mrr, 2),
            "overdue_count": overdue_count,
            "overdue_amount": round(overdue_amount, 2),
            "plan_breakdown": plan_breakdown,
            "monthly_revenue": [{"month": k, "amount": round(v, 2)} for k, v in monthly.items()],
        })
    finally:
        s.close()


# ─── KLİNİKA AKTİVLİK SƏVİYYƏSİ ───────────────────────────────────────────────

@app.route("/api/superadmin/clinics/activity")
def sa_clinics_activity():
    if not is_superadmin(): return err("İcazə yoxdur", 403)
    s = db()
    try:
        from sqlalchemy import func
        clinics = s.query(models.Clinic).all()
        cutoff = datetime.utcnow() - timedelta(days=30)
        out = []
        for c in clinics:
            new_patients = s.query(models.Patient).filter(
                models.Patient.clinic_id == c.id,
                models.Patient.created_at >= cutoff
            ).count()
            total_patients = s.query(models.Patient).filter_by(clinic_id=c.id).count()
            last_login = s.query(models.ActivityLog).filter(
                models.ActivityLog.clinic_id == c.id,
                models.ActivityLog.action == 'login'
            ).order_by(models.ActivityLog.created_at.desc()).first()
            last_login_date = last_login.created_at.isoformat() if last_login else None
            # kateqoriya: 0 yeni → ölü, 1-5 → aşağı, 6-20 → orta, 20+ → aktiv
            if new_patients == 0:
                level = "dead"
            elif new_patients < 6:
                level = "low"
            elif new_patients < 21:
                level = "medium"
            else:
                level = "high"
            out.append({
                "clinic_id": c.id, "clinic_name": c.name,
                "plan": c.plan, "is_active": c.is_active,
                "total_patients": total_patients,
                "new_patients_30d": new_patients,
                "last_login": last_login_date,
                "level": level,
            })
        out.sort(key=lambda x: x["new_patients_30d"], reverse=True)
        return jsonify(out)
    finally:
        s.close()


# ─── DƏSTƏK BİLETLƏRİ ─────────────────────────────────────────────────────────

@app.route("/api/superadmin/tickets")
def sa_list_tickets():
    if not is_superadmin(): return err("İcazə yoxdur", 403)
    s = db()
    try:
        items = s.query(models.SupportTicket).order_by(models.SupportTicket.id.desc()).all()
        clinic_map = {c.id: c.name for c in s.query(models.Clinic).all()}
        return jsonify([{**t.to_dict(), "clinic_name": clinic_map.get(t.clinic_id, "—")}
                        for t in items])
    finally:
        s.close()

@app.route("/api/superadmin/tickets/<int:tid>", methods=["PUT"])
def sa_update_ticket(tid):
    if not is_superadmin(): return err("İcazə yoxdur", 403)
    d = request.json or {}
    s = db()
    try:
        t = s.query(models.SupportTicket).get(tid)
        if not t: return err("Bilet tapılmadı", 404)
        for k in ("status", "priority"):
            if k in d: setattr(t, k, d[k])
        s.commit()
        return jsonify(t.to_dict())
    finally:
        s.close()

# Klinika tərəfindən bilet yarat (admin və ya doctor)
@app.route("/api/tickets", methods=["POST"])
def create_ticket():
    if 'user_id' not in session: return err("Giriş yoxdur", 401)
    d = request.json or {}
    if not d.get("subject"): return err("Mövzu tələb olunur")
    s = db()
    try:
        t = models.SupportTicket(
            clinic_id=clinic_id(), user_id=session.get("user_id"),
            subject=d["subject"], body=d.get("body"),
            priority=d.get("priority", "normal"),
        )
        s.add(t); s.commit(); s.refresh(t)
        return jsonify(t.to_dict()), 201
    finally:
        s.close()

@app.route("/api/tickets")
def list_my_tickets():
    if 'user_id' not in session: return err("Giriş yoxdur", 401)
    s = db()
    try:
        items = s.query(models.SupportTicket).filter_by(clinic_id=clinic_id())\
                  .order_by(models.SupportTicket.id.desc()).all()
        return jsonify([t.to_dict() for t in items])
    finally:
        s.close()


# ─── QLOBAL (CROSS-CLINIC) AXTARIŞ ────────────────────────────────────────────

@app.route("/api/superadmin/global-search")
def sa_global_search():
    if not is_superadmin(): return err("İcazə yoxdur", 403)
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"clinics": [], "patients": [], "users": []})
    s = db()
    try:
        like = f"%{q}%"
        clinics = s.query(models.Clinic).filter(
            (models.Clinic.name.ilike(like)) | (models.Clinic.slug.ilike(like)) |
            (models.Clinic.phone.ilike(like)) | (models.Clinic.email.ilike(like))
        ).limit(20).all()
        clinic_map = {c.id: c.name for c in s.query(models.Clinic).all()}
        patients = s.query(models.Patient).filter(
            (models.Patient.name.ilike(like)) | (models.Patient.phone.ilike(like))
        ).limit(30).all()
        users = s.query(models.User).filter(
            (models.User.name.ilike(like)) | (models.User.email.ilike(like)) |
            (models.User.phone.ilike(like))
        ).limit(20).all()
        return jsonify({
            "clinics": [{"id": c.id, "name": c.name, "slug": c.slug,
                         "phone": c.phone, "email": c.email} for c in clinics],
            "patients": [{"id": p.id, "name": p.name, "phone": p.phone,
                          "clinic_id": p.clinic_id,
                          "clinic_name": clinic_map.get(p.clinic_id, "—")} for p in patients],
            "users": [{"id": u.id, "name": u.name, "email": u.email,
                       "phone": u.phone, "role": u.role,
                       "clinic_id": u.clinic_id,
                       "clinic_name": clinic_map.get(u.clinic_id, "—") if u.clinic_id else "—"}
                      for u in users],
        })
    finally:
        s.close()


# ─── ADMIN: DASHBOARD / GƏLİR / KOMİSSİYA / RANDEVU / ANBAR / BORC / EXPORT ───

EXPENSE_CATEGORIES = ["Material","Avadanlıq","İcarə","Maaş","Reklam","Kommunal","Digər"]

@app.route("/api/admin/expense-categories")
def admin_expense_categories():
    if not is_admin(): return err("İcazə yoxdur", 403)
    return jsonify(EXPENSE_CATEGORIES)

@app.route("/api/admin/dashboard")
def admin_dashboard():
    """Klinika üzrə gəlir, xərc, mənfəət, ay statistikası"""
    if session.get("role") != "admin": return err("İcazə yoxdur", 403)
    s = db()
    try:
        cid = clinic_id()
        today = datetime.utcnow().date()
        month_start = today.replace(day=1)
        # gəlir = bütün ödənişlər (Payment) bu klinikada
        from sqlalchemy import func
        total_revenue = s.query(func.coalesce(func.sum(models.Payment.amount), 0))\
            .join(models.Patient, models.Patient.id == models.Payment.patient_id)\
            .filter(models.Patient.clinic_id == cid).scalar() or 0
        month_revenue = s.query(func.coalesce(func.sum(models.Payment.amount), 0))\
            .join(models.Patient, models.Patient.id == models.Payment.patient_id)\
            .filter(models.Patient.clinic_id == cid,
                    models.Payment.date >= month_start.isoformat()).scalar() or 0
        total_expense = s.query(func.coalesce(func.sum(
            models.Expense.price * models.Expense.quantity), 0))\
            .filter(models.Expense.clinic_id == cid).scalar() or 0
        month_expense = s.query(func.coalesce(func.sum(
            models.Expense.price * models.Expense.quantity), 0))\
            .filter(models.Expense.clinic_id == cid,
                    models.Expense.purchase_date >= month_start.isoformat()).scalar() or 0
        # ümumi plan dəyəri vs ödənilən = qalıq borc
        plans_total = s.query(func.coalesce(func.sum(models.TreatmentPlan.cost), 0))\
            .join(models.Patient, models.Patient.id == models.TreatmentPlan.patient_id)\
            .filter(models.Patient.clinic_id == cid).scalar() or 0
        outstanding = max(0, plans_total - total_revenue)
        # gözlənilən randevular bu gün
        today_appointments = s.query(models.Appointment).filter(
            models.Appointment.clinic_id == cid,
            models.Appointment.appointment_date == today.isoformat(),
            models.Appointment.status.in_(['scheduled', 'confirmed'])
        ).count()
        # son 6 ay gəlir trendi
        from collections import OrderedDict
        monthly = OrderedDict()
        for i in range(5, -1, -1):
            y = today.year; m = today.month - i
            while m <= 0: m += 12; y -= 1
            monthly[f"{y:04d}-{m:02d}"] = {"revenue": 0, "expense": 0}
        # gəlir per ay
        pays = s.query(models.Payment).join(models.Patient).filter(
            models.Patient.clinic_id == cid).all()
        for p in pays:
            if p.date and p.date[:7] in monthly:
                monthly[p.date[:7]]["revenue"] += p.amount or 0
        exps = s.query(models.Expense).filter_by(clinic_id=cid).all()
        for e in exps:
            if e.purchase_date and e.purchase_date[:7] in monthly:
                monthly[e.purchase_date[:7]]["expense"] += (e.price or 0) * (e.quantity or 1)
        # az qalan inventar
        low_stock = s.query(models.InventoryItem).filter(
            models.InventoryItem.clinic_id == cid,
            models.InventoryItem.quantity <= models.InventoryItem.min_quantity
        ).count()
        # bildiriş sayı
        unread_count = today_appointments + low_stock
        if outstanding > 0: unread_count += 1
        return jsonify({
            "total_revenue": round(total_revenue, 2),
            "month_revenue": round(month_revenue, 2),
            "total_expense": round(total_expense, 2),
            "month_expense": round(month_expense, 2),
            "month_profit": round(month_revenue - month_expense, 2),
            "outstanding_debt": round(outstanding, 2),
            "today_appointments": today_appointments,
            "low_stock_count": low_stock,
            "unread_count": unread_count,
            "monthly_trend": [{"month": k, **v} for k, v in monthly.items()],
        })
    finally:
        s.close()

@app.route("/api/admin/doctor-performance")
def admin_doctor_performance():
    """Hər həkim üçün: pasiyent sayı, gəlir, komissiya"""
    if session.get("role") != "admin": return err("İcazə yoxdur", 403)
    s = db()
    try:
        from sqlalchemy import func
        cid = clinic_id()
        today = datetime.utcnow().date()
        month_start = today.replace(day=1).isoformat()
        doctors = s.query(models.User).filter_by(clinic_id=cid, role='doctor').all()
        out = []
        for d in doctors:
            # bu həkimə bağlı planlar
            plans = s.query(models.TreatmentPlan).join(models.Patient).filter(
                models.Patient.clinic_id == cid,
                models.TreatmentPlan.doctor_id == d.id
            ).all()
            plan_ids = [p.id for p in plans]
            patient_ids = list({p.patient_id for p in plans})
            # gəlir: bu həkimin planlarına edilən ödənişlər
            rev = 0; rev_month = 0
            if plan_ids:
                pays = s.query(models.Payment).filter(models.Payment.plan_id.in_(plan_ids)).all()
                for p in pays:
                    rev += p.amount or 0
                    if p.date and p.date >= month_start:
                        rev_month += p.amount or 0
            comm_pct = d.commission_percent or 0
            out.append({
                "id": d.id, "name": d.name, "email": d.email,
                "commission_percent": comm_pct,
                "patient_count": len(patient_ids),
                "plan_count": len(plans),
                "total_revenue": round(rev, 2),
                "month_revenue": round(rev_month, 2),
                "total_commission": round(rev * comm_pct / 100, 2),
                "month_commission": round(rev_month * comm_pct / 100, 2),
            })
        out.sort(key=lambda x: x["month_revenue"], reverse=True)
        return jsonify(out)
    finally:
        s.close()

@app.route("/api/admin/users/<int:uid>/commission", methods=["PUT"])
def admin_set_commission(uid):
    if session.get("role") != "admin": return err("İcazə yoxdur", 403)
    d = request.json or {}
    s = db()
    try:
        u = s.query(models.User).filter_by(id=uid, clinic_id=clinic_id()).first()
        if not u: return err("İstifadəçi tapılmadı", 404)
        u.commission_percent = float(d.get("commission_percent") or 0)
        s.commit()
        return jsonify(u.to_dict())
    finally:
        s.close()

# ─── RANDEVULAR ───────────────────────────────────────────────────────────────

@app.route("/api/appointments")
def list_appointments():
    if 'user_id' not in session: return err("Giriş yoxdur", 401)
    s = db()
    try:
        cid = clinic_id()
        date_from = request.args.get("from")
        date_to = request.args.get("to")
        q = s.query(models.Appointment).filter_by(clinic_id=cid)
        if date_from: q = q.filter(models.Appointment.appointment_date >= date_from)
        if date_to:   q = q.filter(models.Appointment.appointment_date <= date_to)
        # həkim isə yalnız özününkü
        if session.get("role") == "doctor":
            q = q.filter(models.Appointment.doctor_id == session["user_id"])
        items = q.order_by(models.Appointment.appointment_date,
                           models.Appointment.appointment_time).all()
        # patient adı join
        pmap = {p.id: p.name for p in s.query(models.Patient).filter_by(clinic_id=cid).all()}
        umap = {u.id: u.name for u in s.query(models.User).filter_by(clinic_id=cid).all()}
        return jsonify([{**a.to_dict(),
                         "patient_name_resolved": pmap.get(a.patient_id) or a.patient_name or "—",
                         "doctor_name": umap.get(a.doctor_id, "—")} for a in items])
    finally:
        s.close()

@app.route("/api/appointments", methods=["POST"])
def create_appointment():
    if 'user_id' not in session: return err("Giriş yoxdur", 401)
    d = request.json or {}
    if not d.get("appointment_date"): return err("Tarix tələb olunur")
    s = db()
    try:
        a = models.Appointment(clinic_id=clinic_id(),
            patient_id=d.get("patient_id") or None,
            doctor_id=d.get("doctor_id") or None,
            patient_name=d.get("patient_name"),
            patient_phone=d.get("patient_phone"),
            appointment_date=d.get("appointment_date"),
            appointment_time=d.get("appointment_time"),
            duration_minutes=int(d.get("duration_minutes") or 30),
            notes=d.get("notes"),
            status=d.get("status") or "scheduled")
        s.add(a); s.commit(); s.refresh(a)
        return jsonify(a.to_dict()), 201
    finally:
        s.close()

@app.route("/api/appointments/<int:aid>", methods=["PUT"])
def update_appointment(aid):
    if 'user_id' not in session: return err("Giriş yoxdur", 401)
    d = request.json or {}
    s = db()
    try:
        a = s.query(models.Appointment).filter_by(id=aid, clinic_id=clinic_id()).first()
        if not a: return err("Tapılmadı", 404)
        for k in ("patient_id","doctor_id","patient_name","patient_phone",
                  "appointment_date","appointment_time","duration_minutes","notes","status"):
            if k in d: setattr(a, k, d[k])
        s.commit()
        return jsonify(a.to_dict())
    finally:
        s.close()

@app.route("/api/appointments/<int:aid>", methods=["DELETE"])
def delete_appointment(aid):
    if 'user_id' not in session: return err("Giriş yoxdur", 401)
    s = db()
    try:
        a = s.query(models.Appointment).filter_by(id=aid, clinic_id=clinic_id()).first()
        if not a: return err("Tapılmadı", 404)
        s.delete(a); s.commit()
        return jsonify({"ok": True})
    finally:
        s.close()

# ─── ANBAR / İNVENTAR ─────────────────────────────────────────────────────────

@app.route("/api/inventory")
def list_inventory():
    if not is_admin(): return err("İcazə yoxdur", 403)
    s = db()
    try:
        items = s.query(models.InventoryItem).filter_by(clinic_id=clinic_id())\
                  .order_by(models.InventoryItem.name).all()
        return jsonify([i.to_dict() for i in items])
    finally:
        s.close()

@app.route("/api/inventory", methods=["POST"])
def create_inventory():
    if not is_admin(): return err("İcazə yoxdur", 403)
    d = request.json or {}
    if not d.get("name"): return err("Ad tələb olunur")
    s = db()
    try:
        item = models.InventoryItem(clinic_id=clinic_id(),
            name=d["name"], category=d.get("category"), unit=d.get("unit") or "ədəd",
            quantity=float(d.get("quantity") or 0),
            min_quantity=float(d.get("min_quantity") or 0),
            unit_price=float(d.get("unit_price") or 0),
            notes=d.get("notes"))
        s.add(item); s.commit(); s.refresh(item)
        return jsonify(item.to_dict()), 201
    finally:
        s.close()

@app.route("/api/inventory/<int:iid>", methods=["PUT"])
def update_inventory(iid):
    if not is_admin(): return err("İcazə yoxdur", 403)
    d = request.json or {}
    s = db()
    try:
        item = s.query(models.InventoryItem).filter_by(id=iid, clinic_id=clinic_id()).first()
        if not item: return err("Tapılmadı", 404)
        for k in ("name","category","unit","quantity","min_quantity","unit_price","notes"):
            if k in d: setattr(item, k, d[k])
        s.commit()
        return jsonify(item.to_dict())
    finally:
        s.close()

@app.route("/api/inventory/<int:iid>", methods=["DELETE"])
def delete_inventory(iid):
    if not is_admin(): return err("İcazə yoxdur", 403)
    s = db()
    try:
        item = s.query(models.InventoryItem).filter_by(id=iid, clinic_id=clinic_id()).first()
        if not item: return err("Tapılmadı", 404)
        s.delete(item); s.commit()
        return jsonify({"ok": True})
    finally:
        s.close()

# ─── BORCLU PASİYENTLƏR ───────────────────────────────────────────────────────

@app.route("/api/admin/debtors")
def admin_debtors():
    """Pasiyent üzrə plan dəyəri vs ödənilən = borc"""
    if session.get("role") != "admin": return err("İcazə yoxdur", 403)
    s = db()
    try:
        cid = clinic_id()
        patients = s.query(models.Patient).filter_by(clinic_id=cid).all()
        out = []
        for p in patients:
            plans = s.query(models.TreatmentPlan).filter_by(patient_id=p.id).all()
            plan_total = sum(pl.cost or 0 for pl in plans)
            payments = s.query(models.Payment).filter_by(patient_id=p.id).all()
            paid = sum(pay.amount or 0 for pay in payments)
            debt = plan_total - paid
            if debt > 0.01:
                last_payment = max((pay.date for pay in payments if pay.date), default=None)
                days_since = None
                if last_payment:
                    try:
                        days_since = (datetime.utcnow().date() -
                                      datetime.fromisoformat(last_payment).date()).days
                    except Exception: pass
                out.append({
                    "patient_id": p.id, "patient_name": p.name, "phone": p.phone,
                    "plan_total": round(plan_total, 2),
                    "paid": round(paid, 2),
                    "debt": round(debt, 2),
                    "last_payment": last_payment,
                    "days_since_payment": days_since,
                    "plans_count": len(plans),
                })
        out.sort(key=lambda x: x["debt"], reverse=True)
        return jsonify(out)
    finally:
        s.close()

# ─── AUDIT LOG (admin'in öz klinikası üçün) ───────────────────────────────────

@app.route("/api/admin/logs")
def admin_logs():
    if session.get("role") != "admin": return err("İcazə yoxdur", 403)
    s = db()
    try:
        cid = clinic_id()
        logs = s.query(models.ActivityLog).filter_by(clinic_id=cid)\
                 .order_by(models.ActivityLog.created_at.desc()).limit(200).all()
        umap = {u.id: u.name for u in s.query(models.User).filter_by(clinic_id=cid).all()}
        return jsonify([{**l.to_dict(), "user_name": umap.get(l.user_id, "—")} for l in logs])
    finally:
        s.close()

# ─── EXCEL/CSV EXPORT ─────────────────────────────────────────────────────────

def _csv_response(rows, headers, filename):
    import csv, io
    buf = io.StringIO()
    buf.write('\ufeff')  # BOM — Excel azərbaycan hərflərini düzgün açsın
    w = csv.writer(buf)
    w.writerow(headers)
    for r in rows: w.writerow(r)
    from flask import Response
    return Response(buf.getvalue(), mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="{filename}"'})

@app.route("/api/admin/export/<string:kind>")
def admin_export(kind):
    if session.get("role") != "admin": return err("İcazə yoxdur", 403)
    s = db()
    try:
        cid = clinic_id()
        if kind == "patients":
            items = s.query(models.Patient).filter_by(clinic_id=cid).all()
            rows = [[p.id, p.name, p.phone or "", p.dob or "", p.gender or "",
                     p.allergies or "", (p.created_at.isoformat() if p.created_at else "")]
                    for p in items]
            return _csv_response(rows,
                ["ID","Ad","Telefon","D.T.","Cins","Allergiya","Qeydiyyat"],
                f"patients-{cid}.csv")
        elif kind == "payments":
            pays = s.query(models.Payment).join(models.Patient).filter(
                models.Patient.clinic_id == cid).all()
            pmap = {p.id: p.name for p in s.query(models.Patient).filter_by(clinic_id=cid).all()}
            rows = [[p.id, pmap.get(p.patient_id, "—"), p.amount or 0,
                     p.date or "", p.notes or ""] for p in pays]
            return _csv_response(rows, ["ID","Pasiyent","Məbləğ","Tarix","Qeyd"],
                                  f"payments-{cid}.csv")
        elif kind == "expenses":
            items = s.query(models.Expense).filter_by(clinic_id=cid).all()
            rows = [[e.id, e.product, e.company or "", e.category or "",
                     e.purchase_date or "", e.quantity or 0, e.price or 0,
                     (e.quantity or 0) * (e.price or 0)] for e in items]
            return _csv_response(rows,
                ["ID","Məhsul","Firma","Kateqoriya","Tarix","Say","Qiymət","Cəm"],
                f"expenses-{cid}.csv")
        elif kind == "appointments":
            items = s.query(models.Appointment).filter_by(clinic_id=cid).all()
            pmap = {p.id: p.name for p in s.query(models.Patient).filter_by(clinic_id=cid).all()}
            umap = {u.id: u.name for u in s.query(models.User).filter_by(clinic_id=cid).all()}
            rows = [[a.id, a.appointment_date or "", a.appointment_time or "",
                     pmap.get(a.patient_id) or a.patient_name or "—",
                     umap.get(a.doctor_id, "—"), a.status or "",
                     a.notes or ""] for a in items]
            return _csv_response(rows,
                ["ID","Tarix","Saat","Pasiyent","Həkim","Status","Qeyd"],
                f"appointments-{cid}.csv")
        elif kind == "inventory":
            items = s.query(models.InventoryItem).filter_by(clinic_id=cid).all()
            rows = [[i.id, i.name, i.category or "", i.unit, i.quantity or 0,
                     i.min_quantity or 0, i.unit_price or 0,
                     (i.quantity or 0) * (i.unit_price or 0)] for i in items]
            return _csv_response(rows,
                ["ID","Ad","Kateqoriya","Vahid","Qalıq","Min","Vahid qiymət","Dəyər"],
                f"inventory-{cid}.csv")
        else:
            return err("Naməlum export növü", 400)
    finally:
        s.close()

# ─── FATURA / QƏBZ (HTML — browser → Print → PDF) ─────────────────────────────

@app.route("/admin/invoice/<int:patient_id>")
def admin_invoice(patient_id):
    if session.get("role") != "admin": return redirect("/")
    s = db()
    try:
        cid = clinic_id()
        p = s.query(models.Patient).filter_by(id=patient_id, clinic_id=cid).first()
        if not p: return "Tapılmadı", 404
        clinic = s.query(models.Clinic).get(cid)
        plans = s.query(models.TreatmentPlan).filter_by(patient_id=p.id).all()
        payments = s.query(models.Payment).filter_by(patient_id=p.id).all()
        plan_total = sum(pl.cost or 0 for pl in plans)
        paid = sum(pay.amount or 0 for pay in payments)
        debt = plan_total - paid
        return render_template("invoice.html",
            clinic=clinic, patient=p, plans=plans, payments=payments,
            plan_total=plan_total, paid=paid, debt=debt,
            today=datetime.utcnow().strftime("%d.%m.%Y"))
    finally:
        s.close()


# ─── HƏKİM: RESEPT / RAZILIQ FORMASI / DİŞ TARİXİ ────────────────────────────

@app.route("/api/prescriptions", methods=["POST"])
def create_prescription():
    if 'user_id' not in session: return err("Giriş yoxdur", 401)
    d = request.json or {}
    if not d.get("patient_id"): return err("patient_id tələb olunur")
    s = db()
    try:
        rx = models.Prescription(
            clinic_id=clinic_id(),
            patient_id=int(d["patient_id"]),
            doctor_id=session.get("user_id"),
            diagnosis=d.get("diagnosis"),
            medications=d.get("medications"),  # JSON string
            notes=d.get("notes"))
        s.add(rx); s.commit(); s.refresh(rx)
        return jsonify(rx.to_dict()), 201
    finally:
        s.close()

@app.route("/api/patients/<int:pid>/prescriptions")
def list_prescriptions(pid):
    if 'user_id' not in session: return err("Giriş yoxdur", 401)
    s = db()
    try:
        items = s.query(models.Prescription).filter_by(
            clinic_id=clinic_id(), patient_id=pid
        ).order_by(models.Prescription.id.desc()).all()
        umap = {u.id: u.name for u in s.query(models.User).filter_by(clinic_id=clinic_id()).all()}
        return jsonify([{**rx.to_dict(), "doctor_name": umap.get(rx.doctor_id, "—")} for rx in items])
    finally:
        s.close()

@app.route("/prescriptions/<int:rxid>/print")
def print_prescription(rxid):
    """Reseptin çap edilə bilən səhifəsi"""
    if 'user_id' not in session: return redirect("/login")
    s = db()
    try:
        rx = s.query(models.Prescription).filter_by(id=rxid, clinic_id=clinic_id()).first()
        if not rx: return "Tapılmadı", 404
        patient = s.query(models.Patient).get(rx.patient_id)
        clinic = s.query(models.Clinic).get(clinic_id())
        doctor = s.query(models.User).get(rx.doctor_id) if rx.doctor_id else None
        try:
            meds = json.loads(rx.medications) if rx.medications else []
        except Exception:
            meds = []
        return render_template("prescription.html",
            rx=rx, patient=patient, clinic=clinic, doctor=doctor,
            meds=meds, today=datetime.utcnow().strftime("%d.%m.%Y"))
    finally:
        s.close()

@app.route("/consent/<int:pid>")
def consent_form(pid):
    """Pasiyent üçün razılıq forması (boş, çap edilə bilən)"""
    if 'user_id' not in session: return redirect("/login")
    s = db()
    try:
        patient = s.query(models.Patient).filter_by(id=pid, clinic_id=clinic_id()).first()
        if not patient: return "Tapılmadı", 404
        clinic = s.query(models.Clinic).get(clinic_id())
        kind = request.args.get("type", "general")  # general, surgery, implant
        return render_template("consent.html",
            patient=patient, clinic=clinic, kind=kind,
            today=datetime.utcnow().strftime("%d.%m.%Y"))
    finally:
        s.close()


if __name__ == "__main__":
    app.run(debug=True, port=8000)
