"""
DentalApp təhlükəsizlik modulu.

İstifadə (main.py içində):
    from security import init_security
    init_security(app)
"""
from flask import request, session, jsonify, redirect
from datetime import datetime, timedelta
from collections import defaultdict, deque
import time

# ── RATE LIMITING (in-memory, login-bruteforce qarşı) ────────────────────────
_login_attempts = defaultdict(lambda: deque(maxlen=20))   # ip → dəfə zamanları
_blocked_ips = {}                                          # ip → block_until_ts

LOGIN_MAX_ATTEMPTS = 5      # 5 uğursuz cəhd
LOGIN_WINDOW_SEC = 300      # 5 dəqiqə içində
LOGIN_BLOCK_SEC = 900       # 15 dəqiqə blok

def _client_ip():
    return (request.headers.get('X-Forwarded-For') or
            request.remote_addr or 'unknown').split(',')[0].strip()

def check_login_rate_limit():
    """Login attempt'i yoxla. Bloklu isə True qaytarır."""
    ip = _client_ip()
    now = time.time()
    if ip in _blocked_ips:
        if now < _blocked_ips[ip]:
            return True, int(_blocked_ips[ip] - now)
        del _blocked_ips[ip]
    return False, 0

def record_login_attempt(success):
    """Login cəhdini qeyd et. Uğursuz cəhd çox olarsa, IP blokla."""
    ip = _client_ip()
    now = time.time()
    if success:
        _login_attempts[ip].clear()
        return
    # köhnə cəhdləri təmizlə
    attempts = _login_attempts[ip]
    while attempts and now - attempts[0] > LOGIN_WINDOW_SEC:
        attempts.popleft()
    attempts.append(now)
    if len(attempts) >= LOGIN_MAX_ATTEMPTS:
        _blocked_ips[ip] = now + LOGIN_BLOCK_SEC
        attempts.clear()


# ── SESSION TIMEOUT ──────────────────────────────────────────────────────────
SESSION_TIMEOUT_MIN = 60   # 60 dəqiqə inaktivlik

def check_session_timeout():
    """Session timeout yoxla. Vaxtı keçibsə, sessionu təmizlə."""
    if 'user_id' not in session:
        return False
    last = session.get('_last_activity')
    now = time.time()
    if last and (now - last) > SESSION_TIMEOUT_MIN * 60:
        session.clear()
        return True
    session['_last_activity'] = now
    return False


# ── INIT ─────────────────────────────────────────────────────────────────────
def init_security(app):
    """Flask app'a təhlükəsizlik middleware'ləri əlavə et."""

    # session config
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=SESSION_TIMEOUT_MIN)
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    # HTTPS-də işləyəndə Secure cookie aktivləşməlidir:
    # app.config['SESSION_COOKIE_SECURE'] = True

    @app.before_request
    def _security_before():
        # session timeout yoxla
        if check_session_timeout():
            if request.path.startswith('/api/'):
                return jsonify({"error": "Sessiya vaxtı keçib", "session_expired": True}), 401
            return redirect('/login?expired=1')
        # login endpoint'ində rate limit
        if request.path == '/login' and request.method == 'POST':
            blocked, remaining = check_login_rate_limit()
            if blocked:
                mins = remaining // 60 + 1
                if request.is_json:
                    return jsonify({"error": f"Çox cəhd. {mins} dəqiqə sonra yenidən yoxlayın."}), 429
                return f"Çox cəhd. {mins} dəqiqə gözləyin.", 429

    @app.after_request
    def _security_headers(resp):
        # Təhlükəsizlik header'ləri
        resp.headers['X-Content-Type-Options'] = 'nosniff'
        resp.headers['X-Frame-Options'] = 'SAMEORIGIN'
        resp.headers['Referrer-Policy'] = 'same-origin'
        return resp
