from flask import Flask, render_template, request, jsonify, send_from_directory, abort, session, redirect
from database import engine, SessionLocal
import models
import os, uuid, shutil, json
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

models.Base.metadata.create_all(bind=engine)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get('SECRET_KEY', 'dental-secret-xK9mP-2024')

from routers.auth import auth as auth_bp
app.register_blueprint(auth_bp)

@app.before_request
def require_login():
    free = ('/login', '/logout', '/forgot-password', '/reset-password', '/static')
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

def _init_admin():
    s = SessionLocal()
    try:
        if not s.query(models.User).first():
            s.add(models.User(
                name='Admin', email='admin@dental.app',
                password_hash=generate_password_hash('Admin1234'),
                role='admin', must_change_password=True, is_active=True
            ))
            s.commit()
            print('\n✓ Default admin yaradıldı: admin@dental.app / Admin1234\n')
    finally:
        s.close()

_init_admin()
UPLOAD_DIR = "static/uploads"
SETTINGS_FILE = "settings.json"


def db():
    return SessionLocal()


def err(msg, code=400):
    return jsonify({"error": msg}), code


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


@app.route("/admin/doctors/<int:uid>")
def doctor_profile_page(uid):
    if session.get("role") != "admin":
        return redirect("/")
    return render_template("doctor_profile_edit.html", doctor_id=uid)


@app.route("/uploads/<path:fname>")
def serve_upload(fname):
    return send_from_directory(UPLOAD_DIR, fname)


# ─── PATIENTS ─────────────────────────────────────────────────────────────────

@app.route("/api/patients", methods=["GET"])
def list_patients():
    q = request.args.get("q", "")
    s = db()
    try:
        query = s.query(models.Patient)
        if q:
            query = query.filter(models.Patient.name.ilike(f"%{q}%"))
        patients = query.order_by(models.Patient.created_at.desc()).all()
        return jsonify([p.to_dict() for p in patients])
    finally:
        s.close()


@app.route("/api/patients", methods=["POST"])
def create_patient():
    d = request.json or {}
    if not d.get("name"):
        return err("Ad tələb olunur")
    s = db()
    try:
        p = models.Patient(
            name=d.get("name"), phone=d.get("phone"), dob=d.get("dob"),
            gender=d.get("gender"), blood_type=d.get("blood_type"),
            complaints=d.get("complaints"), medical_history=d.get("medical_history"),
            allergies=d.get("allergies"), notes=d.get("notes")
        )
        s.add(p)
        s.commit()
        s.refresh(p)
        ev = models.TimelineEvent(patient_id=p.id, event_type="created",
                                   description="Xəstə profili yaradıldı", ref_id=p.id)
        s.add(ev)
        s.commit()
        return jsonify(p.to_dict()), 201
    finally:
        s.close()


@app.route("/api/patients/<int:pid>", methods=["GET"])
def get_patient(pid):
    s = db()
    try:
        p = s.query(models.Patient).get(pid)
        if not p:
            return err("Xəstə tapılmadı", 404)
        return jsonify(p.to_dict())
    finally:
        s.close()


@app.route("/api/patients/<int:pid>", methods=["PUT"])
def update_patient(pid):
    d = request.json or {}
    s = db()
    try:
        p = s.query(models.Patient).get(pid)
        if not p:
            return err("Xəstə tapılmadı", 404)
        for k in ["name","phone","dob","gender","blood_type","complaints","medical_history","allergies","notes"]:
            if k in d:
                setattr(p, k, d[k])
        p.updated_at = datetime.utcnow()
        s.commit()
        return jsonify(p.to_dict())
    finally:
        s.close()


@app.route("/api/patients/<int:pid>", methods=["DELETE"])
def delete_patient(pid):
    s = db()
    try:
        p = s.query(models.Patient).get(pid)
        if not p:
            return err("Xəstə tapılmadı", 404)
        s.delete(p)
        s.commit()
        return jsonify({"ok": True})
    finally:
        s.close()


@app.route("/api/patients/<int:pid>/timeline")
def get_timeline(pid):
    s = db()
    try:
        events = s.query(models.TimelineEvent).filter_by(patient_id=pid)\
            .order_by(models.TimelineEvent.created_at.desc()).all()
        return jsonify([e.to_dict() for e in events])
    finally:
        s.close()


@app.route("/api/stats")
def stats():
    from sqlalchemy import func
    s = db()
    try:
        total = s.query(func.count(models.Patient.id)).scalar()
        today = datetime.utcnow().date().isoformat()
        today_count = s.query(func.count(models.Patient.id))\
            .filter(func.date(models.Patient.created_at) == today).scalar()
        active = s.query(func.count(models.TreatmentPlan.id))\
            .filter(models.TreatmentPlan.status == "in_progress").scalar()
        return jsonify({"total_patients": total, "today_patients": today_count, "active_plans": active})
    finally:
        s.close()


# ─── TEETH ────────────────────────────────────────────────────────────────────

@app.route("/api/patients/<int:pid>/teeth")
def get_teeth(pid):
    s = db()
    try:
        teeth = s.query(models.Tooth).filter_by(patient_id=pid).all()
        return jsonify({t.tooth_number: {"status": t.status, "notes": t.notes} for t in teeth})
    finally:
        s.close()


@app.route("/api/patients/<int:pid>/teeth/<int:tnum>", methods=["PUT"])
def update_tooth(pid, tnum):
    d = request.json or {}
    s = db()
    try:
        tooth = s.query(models.Tooth).filter_by(patient_id=pid, tooth_number=tnum).first()
        if tooth:
            tooth.status = d.get("status", tooth.status)
            tooth.notes = d.get("notes", tooth.notes)
        else:
            tooth = models.Tooth(patient_id=pid, tooth_number=tnum,
                                  status=d.get("status","healthy"), notes=d.get("notes"))
            s.add(tooth)
        s.commit()
        ev = models.TimelineEvent(patient_id=pid, event_type="tooth_updated",
                                   description=f"Diş {tnum} statusu: {d.get('status')}", ref_id=tnum)
        s.add(ev)
        s.commit()
        return jsonify({"tooth_number": tnum, "status": tooth.status, "notes": tooth.notes})
    finally:
        s.close()


# ─── TREATMENT PLANS ──────────────────────────────────────────────────────────

@app.route("/api/patients/<int:pid>/plans")
def list_plans(pid):
    s = db()
    try:
        plans = s.query(models.TreatmentPlan).filter_by(patient_id=pid)\
            .order_by(models.TreatmentPlan.created_at.desc()).all()
        return jsonify([p.to_dict() for p in plans])
    finally:
        s.close()


@app.route("/api/patients/<int:pid>/plans", methods=["POST"])
def create_plan(pid):
    d = request.json or {}
    if not d.get("title"):
        return err("Başlıq tələb olunur")
    s = db()
    try:
        plan = models.TreatmentPlan(
            patient_id=pid, title=d.get("title"),
            service_id=d.get("service_id"), template_id=d.get("template_id"),
            cost=float(d.get("cost",0)),
            status=d.get("status","planned"), start_date=d.get("start_date"),
            end_date=d.get("end_date"), notes=d.get("notes")
        )
        s.add(plan)
        s.commit()
        s.refresh(plan)
        # Auto-fill steps from template (selected or all)
        if d.get("template_id"):
            selected_ids = d.get("selected_step_ids")
            q = s.query(models.TemplateStep).filter_by(template_id=d["template_id"])
            if selected_ids:
                q = q.filter(models.TemplateStep.id.in_(selected_ids))
            tmpl_steps = q.order_by(models.TemplateStep.order).all()
            start = datetime.utcnow()
            for i, ts in enumerate(tmpl_steps):
                sched = (start + timedelta(days=ts.default_duration_days * (i+1))).strftime("%Y-%m-%d")
                step = models.TreatmentStep(plan_id=plan.id, order=i,
                                             title=ts.title, description=ts.description, scheduled_date=sched)
                s.add(step)
            s.commit()
        ev = models.TimelineEvent(patient_id=pid, event_type="plan_created",
                                   description=f"Müalicə planı yaradıldı: {plan.title}", ref_id=plan.id)
        s.add(ev)
        s.commit()
        s.refresh(plan)
        return jsonify(plan.to_dict()), 201
    finally:
        s.close()


@app.route("/api/plans/<int:plan_id>")
def get_plan(plan_id):
    s = db()
    try:
        plan = s.query(models.TreatmentPlan).get(plan_id)
        if not plan:
            return err("Plan tapılmadı", 404)
        return jsonify(plan.to_dict())
    finally:
        s.close()




@app.route("/api/plans/<int:plan_id>", methods=["DELETE"])
def delete_plan(plan_id):
    s = db()
    try:
        plan = s.query(models.TreatmentPlan).get(plan_id)
        if not plan:
            return err("Plan tapılmadı", 404)
        s.delete(plan)
        s.commit()
        return jsonify({"ok": True})
    finally:
        s.close()


@app.route("/api/plans/<int:plan_id>/steps", methods=["POST"])
def add_step(plan_id):
    d = request.json or {}
    if not d.get("title"):
        return err("Başlıq tələb olunur")
    s = db()
    try:
        step = models.TreatmentStep(
            plan_id=plan_id, order=d.get("order",0), title=d.get("title"),
            description=d.get("description"), status=d.get("status","pending"),
            scheduled_date=d.get("scheduled_date"), notes=d.get("notes")
        )
        s.add(step)
        s.commit()
        s.refresh(step)
        return jsonify(step.to_dict()), 201
    finally:
        s.close()


@app.route("/api/steps/<int:step_id>", methods=["PUT"])
def update_step(step_id):
    d = request.json or {}
    s = db()
    try:
        step = s.query(models.TreatmentStep).get(step_id)
        if not step:
            return err("Addım tapılmadı", 404)
        for k in ["title","description","status","scheduled_date","completed_date","notes"]:
            if k in d:
                setattr(step, k, d[k])
        if d.get("status") == "done" and not step.completed_date:
            step.completed_date = datetime.utcnow().strftime("%Y-%m-%d")
        s.commit()
        plan = s.query(models.TreatmentPlan).get(step.plan_id)
        if plan and all(st.status in ("done","skipped") for st in plan.steps) and plan.steps:
            plan.status = "completed"
            s.commit()
        return jsonify(step.to_dict())
    finally:
        s.close()


@app.route("/api/steps/<int:step_id>", methods=["DELETE"])
def delete_step(step_id):
    s = db()
    try:
        step = s.query(models.TreatmentStep).get(step_id)
        if not step:
            return err("Addım tapılmadı", 404)
        s.delete(step)
        s.commit()
        return jsonify({"ok": True})
    finally:
        s.close()


# ─── SERVICES & TEMPLATES ─────────────────────────────────────────────────────

@app.route("/api/services")
def list_services():
    s = db()
    try:
        q = s.query(models.Service)
        if session.get("role") != "admin":
            q = q.filter_by(user_id=session["user_id"])
        return jsonify([svc.to_dict() for svc in q.all()])
    finally:
        s.close()


@app.route("/api/services", methods=["POST"])
def create_service():
    d = request.json or {}
    s = db()
    try:
        svc = models.Service(
            user_id=session["user_id"],
            name=d.get("name",""), icon=d.get("icon"), description=d.get("description")
        )
        s.add(svc)
        s.commit()
        s.refresh(svc)
        return jsonify(svc.to_dict()), 201
    finally:
        s.close()


@app.route("/api/services/<int:svc_id>", methods=["PUT"])
def update_service(svc_id):
    d = request.json or {}
    s = db()
    try:
        svc = s.query(models.Service).get(svc_id)
        if not svc:
            return err("Xidmət tapılmadı", 404)
        if session.get("role") != "admin" and svc.user_id != session["user_id"]:
            return err("İcazə yoxdur", 403)
        for k in ["name","icon","description"]:
            if k in d:
                setattr(svc, k, d[k])
        s.commit()
        return jsonify(svc.to_dict())
    finally:
        s.close()


@app.route("/api/services/<int:svc_id>", methods=["DELETE"])
def delete_service(svc_id):
    s = db()
    try:
        svc = s.query(models.Service).get(svc_id)
        if not svc:
            return err("Xidmət tapılmadı", 404)
        if session.get("role") != "admin" and svc.user_id != session["user_id"]:
            return err("İcazə yoxdur", 403)
        s.delete(svc)
        s.commit()
        return jsonify({"ok": True})
    finally:
        s.close()


@app.route("/api/services/<int:svc_id>/templates", methods=["POST"])
def create_template(svc_id):
    d = request.json or {}
    s = db()
    try:
        svc = s.query(models.Service).get(svc_id)
        if not svc:
            return err("Xidmət tapılmadı", 404)
        if session.get("role") != "admin" and svc.user_id != session["user_id"]:
            return err("İcazə yoxdur", 403)
        t = models.ServiceTemplate(service_id=svc_id, name=d.get("name",""), description=d.get("description"))
        s.add(t)
        s.commit()
        s.refresh(t)
        return jsonify(t.to_dict()), 201
    finally:
        s.close()


@app.route("/api/templates/<int:tmpl_id>", methods=["DELETE"])
def delete_template(tmpl_id):
    s = db()
    try:
        t = s.query(models.ServiceTemplate).get(tmpl_id)
        if not t:
            return err("Şablon tapılmadı", 404)
        svc = s.query(models.Service).get(t.service_id)
        if svc and session.get("role") != "admin" and svc.user_id != session["user_id"]:
            return err("İcazə yoxdur", 403)
        s.delete(t)
        s.commit()
        return jsonify({"ok": True})
    finally:
        s.close()


@app.route("/api/templates/<int:tmpl_id>/steps", methods=["POST"])
def add_template_step(tmpl_id):
    d = request.json or {}
    s = db()
    try:
        step = models.TemplateStep(template_id=tmpl_id, order=d.get("order",0),
                                    title=d.get("title",""), description=d.get("description"),
                                    default_duration_days=d.get("default_duration_days",7),
                                    price=float(d.get("price",0)))
        s.add(step)
        s.commit()
        s.refresh(step)
        return jsonify(step.to_dict()), 201
    finally:
        s.close()


@app.route("/api/template-steps/<int:step_id>", methods=["DELETE"])
def delete_template_step(step_id):
    s = db()
    try:
        step = s.query(models.TemplateStep).get(step_id)
        if not step:
            return err("Addım tapılmadı", 404)
        s.delete(step)
        s.commit()
        return jsonify({"ok": True})
    finally:
        s.close()


# ─── MEDIA ────────────────────────────────────────────────────────────────────

@app.route("/api/media/upload", methods=["POST"])
def upload_media():
    f = request.files.get("file")
    if not f:
        return err("Fayl tələb olunur")
    pid = request.form.get("patient_id")
    if not pid:
        return err("patient_id tələb olunur")
    ext = os.path.splitext(f.filename)[1]
    fname = uuid.uuid4().hex + ext
    fpath = os.path.join(UPLOAD_DIR, fname)
    f.save(fpath)
    s = db()
    try:
        m = models.Media(patient_id=int(pid), step_id=request.form.get("step_id") or None,
                          tooth_number=request.form.get("tooth_number") or None,
                          type=request.form.get("type","other"),
                          filename=fname, filepath=fpath, caption=request.form.get("caption"))
        s.add(m)
        s.commit()
        s.refresh(m)
        return jsonify(m.to_dict()), 201
    finally:
        s.close()


@app.route("/api/patients/<int:pid>/media")
def get_media(pid):
    mtype = request.args.get("type")
    s = db()
    try:
        q = s.query(models.Media).filter_by(patient_id=pid)
        if mtype:
            q = q.filter_by(type=mtype)
        return jsonify([m.to_dict() for m in q.order_by(models.Media.uploaded_at.desc()).all()])
    finally:
        s.close()


@app.route("/api/media/<int:mid>", methods=["DELETE"])
def delete_media(mid):
    s = db()
    try:
        m = s.query(models.Media).get(mid)
        if not m:
            return err("Media tapılmadı", 404)
        if m.filepath and os.path.exists(m.filepath):
            os.remove(m.filepath)
        s.delete(m)
        s.commit()
        return jsonify({"ok": True})
    finally:
        s.close()


# ─── EXPENSES ─────────────────────────────────────────────────────────────────

@app.route("/expenses")
def expenses_page():
    return render_template("expenses.html")


@app.route("/api/expenses")
def list_expenses():
    s = db()
    try:
        q = s.query(models.Expense)
        if session.get("role") != "admin":
            q = q.filter_by(user_id=session["user_id"])
        return jsonify([e.to_dict() for e in q.order_by(models.Expense.purchase_date.desc()).all()])
    finally:
        s.close()


@app.route("/api/expenses", methods=["POST"])
def create_expense():
    d = request.json or {}
    s = db()
    try:
        e = models.Expense(
            user_id=session["user_id"],
            product=d.get("product",""), company=d.get("company"),
            purchase_date=d.get("purchase_date"), quantity=int(d.get("quantity",1)),
            price=float(d.get("price",0)), category=d.get("category")
        )
        s.add(e); s.commit(); s.refresh(e)
        return jsonify(e.to_dict()), 201
    finally:
        s.close()


@app.route("/api/expenses/<int:eid>", methods=["PUT"])
def update_expense(eid):
    d = request.json or {}
    s = db()
    try:
        e = s.query(models.Expense).get(eid)
        if not e: return err("Tapılmadı", 404)
        if session.get("role") != "admin" and e.user_id != session["user_id"]:
            return err("İcazə yoxdur", 403)
        for k in ["product","company","purchase_date","category"]:
            if k in d: setattr(e, k, d[k])
        if "quantity" in d: e.quantity = int(d["quantity"])
        if "price"    in d: e.price    = float(d["price"])
        s.commit()
        return jsonify(e.to_dict())
    finally:
        s.close()


@app.route("/api/expenses/<int:eid>", methods=["DELETE"])
def delete_expense(eid):
    s = db()
    try:
        e = s.query(models.Expense).get(eid)
        if not e: return err("Tapılmadı", 404)
        if session.get("role") != "admin" and e.user_id != session["user_id"]:
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
        q = s.query(models.Expense)
        if session.get("role") != "admin":
            q = q.filter_by(user_id=session["user_id"])
        rows = q.order_by(models.Expense.purchase_date.desc()).all()
    finally:
        s.close()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Xərclər"
    headers = ["#","Məhsul","Firma","Kateqoriya","Tarix","Say","Qiymət (₼)","Cəm (₼)"]
    ws.append(headers)
    for i, e in enumerate(rows, 1):
        ws.append([i, e.product, e.company or "", e.category or "",
                   e.purchase_date or "", e.quantity, e.price,
                   (e.quantity or 1) * (e.price or 0)])
    buf = BytesIO()
    wb.save(buf); buf.seek(0)
    return send_file(buf, as_attachment=True,
                     download_name="xercler.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ─── PAYMENTS ─────────────────────────────────────────────────────────────────

@app.route("/api/patients/<int:pid>/payments")
def list_payments(pid):
    s = db()
    try:
        pays = s.query(models.Payment).filter_by(patient_id=pid)\
               .order_by(models.Payment.date.desc()).all()
        plans = s.query(models.TreatmentPlan).filter_by(patient_id=pid).all()
        total_cost = sum(p.cost or 0 for p in plans)
        total_paid = sum(p.amount or 0 for p in pays)
        return jsonify({"payments": [p.to_dict() for p in pays],
                        "total_cost": total_cost, "total_paid": total_paid,
                        "debt": max(0, total_cost - total_paid)})
    finally:
        s.close()


@app.route("/api/patients/<int:pid>/payments", methods=["POST"])
def add_payment(pid):
    d = request.json or {}
    s = db()
    try:
        p = models.Payment(patient_id=pid, plan_id=d.get("plan_id"),
                           amount=float(d.get("amount",0)),
                           date=d.get("date"), notes=d.get("notes"))
        s.add(p); s.commit(); s.refresh(p)
        return jsonify(p.to_dict()), 201
    finally:
        s.close()


@app.route("/api/payments/<int:pid>", methods=["DELETE"])
def delete_payment(pid):
    s = db()
    try:
        p = s.query(models.Payment).get(pid)
        if not p: return err("Tapılmadı", 404)
        s.delete(p); s.commit()
        return jsonify({"ok": True})
    finally:
        s.close()


@app.route("/api/plans/<int:plan_id>", methods=["PUT"])
def update_plan(plan_id):
    d = request.json or {}
    s = db()
    try:
        plan = s.query(models.TreatmentPlan).get(plan_id)
        if not plan: return err("Plan tapılmadı", 404)
        for k in ["title","status","start_date","end_date","notes"]:
            if k in d: setattr(plan, k, d[k])
        if "cost" in d: plan.cost = float(d["cost"])
        s.commit()
        return jsonify(plan.to_dict())
    finally:
        s.close()


# ─── DASHBOARD ACTIVE TIMELINE ────────────────────────────────────────────────

@app.route("/api/dashboard/active-timeline")
def active_timeline():
    from sqlalchemy import func
    s = db()
    try:
        active_pids = [r[0] for r in s.query(models.TreatmentPlan.patient_id)
                       .filter_by(status="in_progress").distinct().all()]
        result = []
        for pid in active_pids[:10]:
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
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE) as f:
            return jsonify(json.load(f))
    return jsonify({"clinic_name": "DentalApp", "doctor_name": "", "phone": "", "address": ""})


@app.route("/api/admin/settings", methods=["PUT"])
def update_settings():
    current = {}
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE) as f:
            current = json.load(f)
    current.update(request.json or {})
    with open(SETTINGS_FILE, "w") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    return jsonify(current)


if __name__ == "__main__":
    app.run(debug=True, port=8000)
