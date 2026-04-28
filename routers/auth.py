from flask import Blueprint, render_template, request, session, redirect, jsonify
from database import SessionLocal
import models
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import secrets, string, json, os, smtplib, re
from email.mime.text import MIMEText
from urllib.parse import quote

auth = Blueprint('auth', __name__)
SETTINGS_FILE = 'settings.json'


def _get_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    return {}


def _send_email(to_email, subject, body):
    cfg = _get_settings()
    host = cfg.get('smtp_host', '')
    user = cfg.get('smtp_user', '')
    pwd = cfg.get('smtp_pass', '')
    port = int(cfg.get('smtp_port', 587))
    from_addr = cfg.get('smtp_from', user)
    if not host or not user:
        return False
    msg = MIMEText(body, 'html', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = from_addr
    msg['To'] = to_email
    try:
        with smtplib.SMTP(host, port) as s:
            s.ehlo(); s.starttls(); s.login(user, pwd); s.send_message(msg)
        return True
    except Exception as e:
        print(f'Email error: {e}')
        return False


def _gen_password(n=10):
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(n))


def _wa_link(phone, message):
    phone = re.sub(r'\D', '', phone)
    return f"https://wa.me/{phone}?text={quote(message)}"


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect('/')
    error = None
    reset_sent = False
    reset_ok = request.args.get('reset') == '1'
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        s = SessionLocal()
        try:
            user = s.query(models.User).filter_by(email=email, is_active=True).first()
            if user and check_password_hash(user.password_hash, password):
                try:
                    from security import record_login_attempt
                    record_login_attempt(True)
                except Exception: pass
                session['user_id'] = user.id
                session['user_name'] = user.name
                session['role'] = user.role
                session['clinic_id'] = user.clinic_id
                session['must_change_password'] = user.must_change_password
                # LOG
                log = models.ActivityLog(clinic_id=user.clinic_id, user_id=user.id,
                    action='login', detail=f'{user.name} ({user.role}) daxil oldu',
                    ip=request.remote_addr)
                s.add(log); s.commit()
                if user.role == 'superadmin':
                    return redirect('/superadmin')
                return redirect('/change-password' if user.must_change_password else '/')
            elif user:
                # Email tapildi, parol yanlisdir - reset link gonder
                try:
                    from security import record_login_attempt
                    record_login_attempt(False)
                except Exception: pass
                import secrets as _sec
                token = _sec.token_urlsafe(32)
                user.reset_token = token
                user.reset_token_expiry = datetime.utcnow() + timedelta(hours=2)
                s.commit()
                reset_url = f"{request.host_url}reset-password/{token}"
                body = f"<p>Salam {user.name},</p><p>Hesabiniza yanlis parol daxil edildi. Parolu sifirlamaq ucun bu linke tiklayin (2 saat etibarlidi):</p><p><a href='{reset_url}'>{reset_url}</a></p><p style='color:#6b7fa3;font-size:.85em'>Eger bu siz deyilsinizse, bu emaili nezere almayin.</p>"
                _send_email(email, 'DentalApp - Parol Sifirlanmasi', body)
                reset_sent = True
                s.add(models.ActivityLog(action='error', detail=f'Yanlis parol, reset gonderildi: {email}', ip=request.remote_addr))
                s.commit()
            else:
                # Email tapilmadi
                try:
                    from security import record_login_attempt
                    record_login_attempt(False)
                except Exception: pass
                error = 'Bu email sistemd&#601; tapilmadi'
                s.add(models.ActivityLog(action='error', detail=f'Tapilmayan email: {email}', ip=request.remote_addr))
                s.commit()
        finally:
            s.close()
    return render_template('login.html', error=error, reset_ok=reset_ok, reset_sent=reset_sent)


@auth.route('/logout')
def logout():
    s = SessionLocal()
    try:
        log = models.ActivityLog(clinic_id=session.get('clinic_id'), user_id=session.get('user_id'),
            action='logout', detail=f"{session.get('user_name','')} çıxış etdi",
            ip=request.remote_addr)
        s.add(log); s.commit()
    except: pass
    finally: s.close()
    session.clear()
    return redirect('/login')


@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    msg = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        s = SessionLocal()
        try:
            user = s.query(models.User).filter_by(email=email).first()
            if user:
                token = secrets.token_urlsafe(32)
                user.reset_token = token
                user.reset_token_expiry = datetime.utcnow() + timedelta(hours=2)
                s.commit()
                reset_url = f"{request.host_url}reset-password/{token}"
                body = f"""<p>Salam {user.name},</p>
                <p>Parolu sıfırlamaq üçün bu linkə klikləyin (2 saat etibarlıdır):</p>
                <p><a href="{reset_url}">{reset_url}</a></p>"""
                sent = _send_email(email, 'DentalApp - Parol Sıfırlama', body)
                if sent:
                    msg = ('success', 'Parol sıfırlama linki emailinizə göndərildi.')
                else:
                    msg = ('warn', f'Email konfiqurasiyası yoxdur. Sıfırlama linkiniz: <a href="{reset_url}">{reset_url}</a>')
            else:
                msg = ('success', 'Əgər bu email mövcuddursa, link göndərildi.')
        finally:
            s.close()
    return render_template('forgot_password.html', msg=msg)


@auth.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    s = SessionLocal()
    try:
        user = s.query(models.User).filter_by(reset_token=token).first()
        if not user or (user.reset_token_expiry and user.reset_token_expiry < datetime.utcnow()):
            return render_template('reset_password.html', expired=True, token=token)
        error = None
        if request.method == 'POST':
            p1 = request.form.get('password', '')
            p2 = request.form.get('password2', '')
            if len(p1) < 6:
                error = 'Parol ən azı 6 simvol olmalıdır'
            elif p1 != p2:
                error = 'Parollar uyğun gəlmir'
            else:
                user.password_hash = generate_password_hash(p1)
                user.reset_token = None
                user.reset_token_expiry = None
                user.must_change_password = False
                s.commit()
                return redirect('/login?reset=1')
        return render_template('reset_password.html', token=token, error=error, user_name=user.name)
    finally:
        s.close()


@auth.route('/change-password', methods=['GET', 'POST'])
def change_password():
    if 'user_id' not in session:
        return redirect('/login')
    error = None
    if request.method == 'POST':
        cur = request.form.get('current_password', '') or request.form.get('password_current', '')
        p1 = request.form.get('password', '') or request.form.get('new_password', '')
        p2 = request.form.get('password2', '') or request.form.get('confirm_password', '')
        forced = session.get('must_change_password', False)
        if len(p1) < 6:
            error = 'Parol ən azı 6 simvol olmalıdır'
        elif p1 != p2:
            error = 'Parollar uyğun gəlmir'
        else:
            s = SessionLocal()
            try:
                user = s.query(models.User).get(session['user_id'])
                # Forced (ilk dəfə) deyilsə, cari parolu yoxla
                if not forced and (not cur or not check_password_hash(user.password_hash, cur)):
                    error = 'Cari parol yanlışdır'
                else:
                    user.password_hash = generate_password_hash(p1)
                    user.must_change_password = False
                    s.commit()
                    session['must_change_password'] = False
                    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
                        return jsonify({'ok': True})
                    return redirect('/')
            finally:
                s.close()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'error': error}), 400
    return render_template('change_password.html', error=error,
                           forced=session.get('must_change_password', False))


# ── Profile ───────────────────────────────────────────────────────────────────

@auth.route('/api/profile', methods=['GET'])
def get_profile():
    if 'user_id' not in session:
        return jsonify({'error': 'Giriş tələb olunur'}), 401
    s = SessionLocal()
    try:
        user = s.query(models.User).get(session['user_id'])
        return jsonify(user.to_dict()) if user else (jsonify({'error': 'Tapılmadı'}), 404)
    finally:
        s.close()


@auth.route('/api/profile', methods=['PUT'])
def update_profile():
    if 'user_id' not in session:
        return jsonify({'error': 'Giriş tələb olunur'}), 401
    d = request.json or {}
    s = SessionLocal()
    try:
        user = s.query(models.User).get(session['user_id'])
        if not user: return jsonify({'error': 'Tapılmadı'}), 404
        if d.get('name'): user.name = d['name'].strip()
        if d.get('phone') is not None: user.phone = d['phone'].strip() or None
        if d.get('email'):
            existing = s.query(models.User).filter(
                models.User.email == d['email'].strip().lower(),
                models.User.id != user.id).first()
            if existing: return jsonify({'error': 'Bu email artıq istifadə olunur'}), 400
            user.email = d['email'].strip().lower()
        if d.get('new_password'):
            if len(d['new_password']) < 6:
                return jsonify({'error': 'Parol ən azı 6 simvol olmalıdır'}), 400
            if not check_password_hash(user.password_hash, d.get('current_password', '')):
                return jsonify({'error': 'Cari parol yanlışdır'}), 400
            user.password_hash = generate_password_hash(d['new_password'])
        s.commit()
        session['user_name'] = user.name
        return jsonify(user.to_dict())
    finally:
        s.close()


# ── User Management (admin only) ──────────────────────────────────────────────

def _admin_only():
    if session.get('role') not in ('admin', 'superadmin'):
        return jsonify({'error': 'İcazə yoxdur'}), 403


@auth.route('/api/users')
def list_users():
    e = _admin_only()
    if e: return e
    s = SessionLocal()
    try:
        return jsonify([u.to_dict() for u in
                        s.query(models.User).filter_by(clinic_id=session.get('clinic_id'), role='doctor')
                         .order_by(models.User.created_at).all()])
    finally:
        s.close()


@auth.route('/api/users', methods=['POST'])
def create_user():
    e = _admin_only()
    if e: return e
    d = request.json or {}
    if not d.get('name') or not d.get('email'):
        return jsonify({'error': 'Ad və email tələb olunur'}), 400
    s = SessionLocal()
    try:
        if s.query(models.User).filter_by(email=d['email'].strip().lower()).first():
            return jsonify({'error': 'Bu email artıq mövcuddur'}), 400
        # Plan limitini yoxla
        cid = session.get('clinic_id')
        clinic = s.query(models.Clinic).get(cid) if cid else None
        if clinic:
            cfg = s.query(models.PlanConfig).filter_by(plan_name=clinic.plan or 'kicik').first()
            if cfg:
                role = d.get('role', 'doctor')
                if role == 'doctor' and cfg.max_doctors:
                    cnt = s.query(models.User).filter_by(clinic_id=cid, role='doctor', is_active=True).count()
                    if cnt >= cfg.max_doctors:
                        return jsonify({'error': f"'{clinic.plan}' planında həkim limiti ({cfg.max_doctors}) doludur"}), 403
                if role == 'admin' and cfg.max_admins:
                    cnt = s.query(models.User).filter_by(clinic_id=cid, role='admin', is_active=True).count()
                    if cnt >= cfg.max_admins:
                        return jsonify({'error': f"'{clinic.plan}' planında admin limiti ({cfg.max_admins}) doludur"}), 403
        temp = _gen_password()
        user = models.User(
            clinic_id=session.get('clinic_id'),
            name=d['name'].strip(), email=d['email'].strip().lower(),
            phone=d.get('phone', '').strip() or None,
            password_hash=generate_password_hash(temp),
            role=d.get('role', 'doctor'),
            must_change_password=True, is_active=True
        )
        s.add(user); s.commit(); s.refresh(user)
        res = user.to_dict()
        res['temp_pass'] = temp
        if user.phone:
            msg = f"Salam {user.name}, DentalApp giriş məlumatları:\nEmail: {user.email}\nParol: {temp}\nİlk girişdə parolu dəyişdirməlisiniz."
            res['wa_link'] = _wa_link(user.phone, msg)
        return jsonify(res), 201
    finally:
        s.close()


@auth.route('/api/users/<int:uid>')
def get_user(uid):
    e = _admin_only()
    if e: return e
    s = SessionLocal()
    try:
        user = s.query(models.User).filter_by(id=uid, clinic_id=session.get('clinic_id')).first()
        if not user: return jsonify({'error': 'Tapılmadı'}), 404
        return jsonify(user.to_dict())
    finally:
        s.close()


@auth.route('/api/users/<int:uid>', methods=['PATCH'])
def update_user(uid):
    e = _admin_only()
    if e: return e
    d = request.json or {}
    s = SessionLocal()
    try:
        user = s.query(models.User).filter_by(id=uid, clinic_id=session.get('clinic_id')).first()
        if not user: return jsonify({'error': 'Tapılmadı'}), 404
        if 'name' in d and d['name']: user.name = d['name'].strip()
        if 'phone' in d: user.phone = d['phone'].strip() or None
        if 'role' in d: user.role = d['role']
        if 'is_active' in d: user.is_active = bool(d['is_active'])
        if 'email' in d and d['email']:
            taken = s.query(models.User).filter(
                models.User.email == d['email'].strip().lower(),
                models.User.id != uid).first()
            if taken: return jsonify({'error': 'Bu email artıq istifadə olunur'}), 400
            user.email = d['email'].strip().lower()
        s.commit()
        return jsonify(user.to_dict())
    finally:
        s.close()


@auth.route('/api/users/<int:uid>/reset-password', methods=['POST'])
def reset_user_password(uid):
    e = _admin_only()
    if e: return e
    s = SessionLocal()
    try:
        user = s.query(models.User).filter_by(id=uid, clinic_id=session.get('clinic_id')).first()
        if not user: return jsonify({'error': 'Tapılmadı'}), 404
        temp = _gen_password()
        user.password_hash = generate_password_hash(temp)
        user.must_change_password = True
        s.commit()
        res = {'temp_pass': temp, 'name': user.name, 'email': user.email, 'phone': user.phone}
        if user.phone:
            msg = f"Salam {user.name}, DentalApp yeni müvəqqəti parolunuz:\nEmail: {user.email}\nParol: {temp}\nGirişdən sonra parolu dəyişdirməlisiniz."
            res['wa_link'] = _wa_link(user.phone, msg)
        return jsonify(res)
    finally:
        s.close()


@auth.route('/api/users/<int:uid>', methods=['DELETE'])
def delete_user(uid):
    e = _admin_only()
    if e: return e
    if uid == session.get('user_id'):
        return jsonify({'error': 'Özünüzü silə bilməzsiniz'}), 400
    s = SessionLocal()
    try:
        user = s.query(models.User).filter_by(id=uid, clinic_id=session.get('clinic_id')).first()
        if not user: return jsonify({'error': 'Tapılmadı'}), 404
        s.delete(user); s.commit()
        return jsonify({'ok': True})
    finally:
        s.close()

@auth.route('/api/usage')
def get_usage():
    e = _admin_only()
    if e: return e
    cid = session.get('clinic_id')
    if not cid: return jsonify({})
    s = SessionLocal()
    try:
        clinic = s.query(models.Clinic).get(cid)
        if not clinic: return jsonify({})
        cfg = s.query(models.PlanConfig).filter_by(plan_name=clinic.plan or 'kicik').first()
        if not cfg: return jsonify({})
        doctors = s.query(models.User).filter_by(clinic_id=cid, role='doctor', is_active=True).count()
        admins = s.query(models.User).filter_by(clinic_id=cid, role='admin', is_active=True).count()
        try:
            patients = s.query(models.Patient).filter_by(clinic_id=cid).count()
        except Exception:
            patients = 0
        return jsonify({
            'plan': clinic.plan,
            'plan_display': cfg.description or clinic.plan,
            'doctors': {'used': doctors, 'max': cfg.max_doctors or 0},
            'admins': {'used': admins, 'max': cfg.max_admins or 0},
            'patients': {'used': patients, 'max': cfg.max_patients or 0},
        })
    finally:
        s.close()
