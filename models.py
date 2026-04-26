from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class Clinic(Base):
    __tablename__ = "clinics"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)  # url-safe ad
    email = Column(String(200), nullable=True)
    phone = Column(String(50), nullable=True)
    address = Column(String(300), nullable=True)
    plan = Column(String(20), default='free')  # free / basic / pro
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="clinic", cascade="all, delete-orphan")
    patients = relationship("Patient", back_populates="clinic", cascade="all, delete-orphan")
    services = relationship("Service", back_populates="clinic", cascade="all, delete-orphan")
    expenses = relationship("Expense", back_populates="clinic", cascade="all, delete-orphan")

    def to_dict(self):
        return {"id": self.id, "name": self.name, "slug": self.slug,
                "email": self.email, "phone": self.phone, "address": self.address,
                "plan": self.plan, "is_active": self.is_active,
                "created_at": self.created_at.isoformat() if self.created_at else None}


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=True)  # superadmin üçün null
    name = Column(String(200), nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    phone = Column(String(30), nullable=True)
    password_hash = Column(String(500), nullable=False)
    role = Column(String(20), default='doctor')  # superadmin / admin / doctor
    commission_percent = Column(Float, default=0)  # həkim komissiya %
    must_change_password = Column(Boolean, default=False)
    reset_token = Column(String(200), nullable=True)
    reset_token_expiry = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    clinic = relationship("Clinic", back_populates="users")

    def to_dict(self):
        return {'id': self.id, 'clinic_id': self.clinic_id, 'name': self.name,
                'email': self.email, 'phone': self.phone, 'role': self.role,
                'commission_percent': self.commission_percent or 0,
                'must_change_password': self.must_change_password,
                'is_active': self.is_active,
                'created_at': self.created_at.isoformat() if self.created_at else None}


class Patient(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    name = Column(String(200), nullable=False)
    phone = Column(String(50))
    dob = Column(String(20))
    gender = Column(String(10))
    blood_type = Column(String(10))
    complaints = Column(Text)
    medical_history = Column(Text)
    allergies = Column(Text)
    notes = Column(Text)
    fin_code = Column(String(20))                                # FİN/şəxsiyyət vəsiqəsi
    family_member_id = Column(Integer, ForeignKey("patients.id"), nullable=True)
    family_relation = Column(String(50))                         # "oğlu", "anası" və s.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    clinic = relationship("Clinic", back_populates="patients")
    teeth = relationship("Tooth", back_populates="patient", cascade="all, delete-orphan")
    plans = relationship("TreatmentPlan", back_populates="patient", cascade="all, delete-orphan")
    media = relationship("Media", back_populates="patient", cascade="all, delete-orphan")
    timeline = relationship("TimelineEvent", back_populates="patient", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="patient", cascade="all, delete-orphan")

    def to_dict(self):
        return {c.name: (getattr(self, c.name).isoformat() if isinstance(getattr(self, c.name), datetime) else getattr(self, c.name))
                for c in self.__table__.columns}


class Tooth(Base):
    __tablename__ = "teeth"
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    tooth_number = Column(Integer, nullable=False)
    status = Column(String(30), default="healthy")
    notes = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    patient = relationship("Patient", back_populates="teeth")


class Service(Base):
    __tablename__ = "services"
    id = Column(Integer, primary_key=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String(200), nullable=False)
    icon = Column(String(50))
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    clinic = relationship("Clinic", back_populates="services")
    templates = relationship("ServiceTemplate", back_populates="service", cascade="all, delete-orphan")

    def to_dict(self):
        return {"id": self.id, "clinic_id": self.clinic_id, "user_id": self.user_id,
                "name": self.name, "icon": self.icon, "description": self.description,
                "templates": [t.to_dict() for t in self.templates]}


class ServiceTemplate(Base):
    __tablename__ = "service_templates"
    id = Column(Integer, primary_key=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    service = relationship("Service", back_populates="templates")
    steps = relationship("TemplateStep", back_populates="template", cascade="all, delete-orphan",
                         order_by="TemplateStep.order")

    def to_dict(self):
        return {"id": self.id, "service_id": self.service_id, "name": self.name,
                "description": self.description, "steps": [s.to_dict() for s in self.steps]}


class TemplateStep(Base):
    __tablename__ = "template_steps"
    id = Column(Integer, primary_key=True)
    template_id = Column(Integer, ForeignKey("service_templates.id"), nullable=False)
    order = Column(Integer, default=0)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    default_duration_days = Column(Integer, default=7)
    price = Column(Float, default=0)
    template = relationship("ServiceTemplate", back_populates="steps")

    def to_dict(self):
        return {"id": self.id, "order": self.order, "title": self.title,
                "description": self.description,
                "default_duration_days": self.default_duration_days, "price": self.price or 0}


class TreatmentPlan(Base):
    __tablename__ = "treatment_plans"
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # komissiya üçün
    service_id = Column(Integer, ForeignKey("services.id"), nullable=True)
    template_id = Column(Integer, ForeignKey("service_templates.id"), nullable=True)
    title = Column(String(200), nullable=False)
    cost = Column(Float, default=0)
    status = Column(String(30), default="planned")
    start_date = Column(String(20))
    end_date = Column(String(20))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    patient = relationship("Patient", back_populates="plans")
    steps = relationship("TreatmentStep", back_populates="plan", cascade="all, delete-orphan",
                         order_by="TreatmentStep.order")

    def to_dict(self):
        return {"id": self.id, "patient_id": self.patient_id, "service_id": self.service_id,
                "doctor_id": self.doctor_id,
                "template_id": self.template_id, "title": self.title, "cost": self.cost or 0,
                "status": self.status, "start_date": self.start_date, "end_date": self.end_date,
                "notes": self.notes,
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "steps": [s.to_dict() for s in self.steps]}


class TreatmentStep(Base):
    __tablename__ = "treatment_steps"
    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, ForeignKey("treatment_plans.id"), nullable=False)
    order = Column(Integer, default=0)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    status = Column(String(20), default="pending")
    scheduled_date = Column(String(20))
    completed_date = Column(String(20))
    notes = Column(Text)
    plan = relationship("TreatmentPlan", back_populates="steps")
    media = relationship("Media", back_populates="step")

    def to_dict(self):
        return {"id": self.id, "plan_id": self.plan_id, "order": self.order,
                "title": self.title, "description": self.description, "status": self.status,
                "scheduled_date": self.scheduled_date, "completed_date": self.completed_date,
                "notes": self.notes}


class Media(Base):
    __tablename__ = "media"
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    step_id = Column(Integer, ForeignKey("treatment_steps.id"), nullable=True)
    tooth_number = Column(Integer, nullable=True)
    type = Column(String(20), default="other")
    filename = Column(String(300))
    filepath = Column(String(500))
    caption = Column(Text)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    patient = relationship("Patient", back_populates="media")
    step = relationship("TreatmentStep", back_populates="media")

    def to_dict(self):
        return {"id": self.id, "patient_id": self.patient_id, "step_id": self.step_id,
                "tooth_number": self.tooth_number, "type": self.type,
                "filename": self.filename, "caption": self.caption,
                "url": f"/uploads/{self.filename}",
                "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None}


class TimelineEvent(Base):
    __tablename__ = "timeline_events"
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    event_type = Column(String(50))
    description = Column(Text)
    ref_id = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    patient = relationship("Patient", back_populates="timeline")

    def to_dict(self):
        return {"id": self.id, "event_type": self.event_type, "description": self.description,
                "ref_id": self.ref_id,
                "created_at": self.created_at.isoformat() if self.created_at else None}


class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    product = Column(String(200), nullable=False)
    company = Column(String(200))
    purchase_date = Column(String(20))
    quantity = Column(Integer, default=1)
    price = Column(Float, default=0)
    category = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

    clinic = relationship("Clinic", back_populates="expenses")

    def to_dict(self):
        return {"id": self.id, "clinic_id": self.clinic_id, "user_id": self.user_id,
                "product": self.product, "company": self.company,
                "purchase_date": self.purchase_date, "quantity": self.quantity,
                "price": self.price or 0, "total": (self.quantity or 1) * (self.price or 0),
                "category": self.category,
                "created_at": self.created_at.isoformat() if self.created_at else None}


class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id = Column(Integer, primary_key=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(50))   # login, logout, error, password_reset
    detail = Column(Text)
    ip = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "clinic_id": self.clinic_id, "user_id": self.user_id,
                "action": self.action, "detail": self.detail, "ip": self.ip,
                "created_at": self.created_at.isoformat() if self.created_at else None}


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    sender_role = Column(String(20))   # superadmin / admin
    sender_name = Column(String(200))
    text = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "clinic_id": self.clinic_id, "sender_role": self.sender_role,
                "sender_name": self.sender_name, "text": self.text, "is_read": self.is_read,
                "created_at": self.created_at.isoformat() if self.created_at else None}


class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False, unique=True)
    plan = Column(String(20), default='free')           # free / basic / pro
    monthly_fee = Column(Float, default=0)              # AZN
    last_paid_date = Column(String(20))                 # ISO date
    next_payment_date = Column(String(20))              # ISO date — borc yoxlanışı bunun əsasında
    status = Column(String(20), default='active')       # active / grace / suspended
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "clinic_id": self.clinic_id, "plan": self.plan,
                "monthly_fee": self.monthly_fee or 0,
                "last_paid_date": self.last_paid_date,
                "next_payment_date": self.next_payment_date,
                "status": self.status}


class SubscriptionPayment(Base):
    __tablename__ = "subscription_payments"
    id = Column(Integer, primary_key=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    amount = Column(Float, default=0)
    paid_date = Column(String(20))
    period_start = Column(String(20))
    period_end = Column(String(20))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "clinic_id": self.clinic_id, "amount": self.amount or 0,
                "paid_date": self.paid_date, "period_start": self.period_start,
                "period_end": self.period_end, "notes": self.notes,
                "created_at": self.created_at.isoformat() if self.created_at else None}


class SupportTicket(Base):
    __tablename__ = "support_tickets"
    id = Column(Integer, primary_key=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    subject = Column(String(300), nullable=False)
    body = Column(Text)
    priority = Column(String(20), default='normal')     # low / normal / high
    status = Column(String(20), default='open')         # open / in_progress / closed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "clinic_id": self.clinic_id, "user_id": self.user_id,
                "subject": self.subject, "body": self.body,
                "priority": self.priority, "status": self.status,
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "updated_at": self.updated_at.isoformat() if self.updated_at else None}


class PlanConfig(Base):
    __tablename__ = "plan_configs"
    id = Column(Integer, primary_key=True)
    plan_name = Column(String(20), unique=True, nullable=False)  # free / basic / pro
    monthly_fee = Column(Float, default=0)
    max_doctors = Column(Integer, default=1)
    max_admins = Column(Integer, default=1)
    max_patients_per_day = Column(Integer, default=10)
    max_total_patients = Column(Integer, default=10)  # ümumi pasiyent limiti
    description = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "plan_name": self.plan_name,
                "monthly_fee": self.monthly_fee or 0,
                "max_doctors": self.max_doctors, "max_admins": self.max_admins,
                "max_patients_per_day": self.max_patients_per_day,
                "max_total_patients": self.max_total_patients,
                "description": self.description}


class Prescription(Base):
    __tablename__ = "prescriptions"
    id = Column(Integer, primary_key=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    diagnosis = Column(String(300))
    medications = Column(Text)        # JSON: [{name, dose, frequency, duration}]
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "clinic_id": self.clinic_id,
                "patient_id": self.patient_id, "doctor_id": self.doctor_id,
                "diagnosis": self.diagnosis, "medications": self.medications,
                "notes": self.notes,
                "created_at": self.created_at.isoformat() if self.created_at else None}


class Appointment(Base):
    __tablename__ = "appointments"
    id = Column(Integer, primary_key=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    patient_name = Column(String(200))   # qeyd olmamış pasiyent üçün manual ad
    patient_phone = Column(String(50))
    appointment_date = Column(String(20))   # ISO date
    appointment_time = Column(String(10))   # HH:MM
    duration_minutes = Column(Integer, default=30)
    notes = Column(Text)
    status = Column(String(20), default='scheduled')  # scheduled/confirmed/done/no_show/cancelled
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "clinic_id": self.clinic_id,
                "patient_id": self.patient_id, "doctor_id": self.doctor_id,
                "patient_name": self.patient_name, "patient_phone": self.patient_phone,
                "appointment_date": self.appointment_date,
                "appointment_time": self.appointment_time,
                "duration_minutes": self.duration_minutes or 30,
                "notes": self.notes, "status": self.status,
                "created_at": self.created_at.isoformat() if self.created_at else None}


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id = Column(Integer, primary_key=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False)
    name = Column(String(200), nullable=False)
    category = Column(String(100))
    unit = Column(String(30), default="ədəd")        # ədəd/qutu/ml/kg
    quantity = Column(Float, default=0)              # mövcud qalıq
    min_quantity = Column(Float, default=0)          # az qaldı xəbərdarlıq həddi
    unit_price = Column(Float, default=0)
    notes = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "clinic_id": self.clinic_id, "name": self.name,
                "category": self.category, "unit": self.unit,
                "quantity": self.quantity or 0, "min_quantity": self.min_quantity or 0,
                "unit_price": self.unit_price or 0,
                "low_stock": (self.quantity or 0) <= (self.min_quantity or 0),
                "notes": self.notes,
                "updated_at": self.updated_at.isoformat() if self.updated_at else None}


class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    plan_id = Column(Integer, ForeignKey("treatment_plans.id"), nullable=True)
    amount = Column(Float, default=0)
    date = Column(String(20))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    patient = relationship("Patient", back_populates="payments")

    def to_dict(self):
        return {"id": self.id, "patient_id": self.patient_id, "plan_id": self.plan_id,
                "amount": self.amount or 0, "date": self.date, "notes": self.notes,
                "created_at": self.created_at.isoformat() if self.created_at else None}