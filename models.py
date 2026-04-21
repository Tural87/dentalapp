from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    email = Column(String(200), unique=True, nullable=False)
    phone = Column(String(30), nullable=True)
    password_hash = Column(String(500), nullable=False)
    role = Column(String(20), default='doctor')
    must_change_password = Column(Boolean, default=False)
    reset_token = Column(String(200), nullable=True)
    reset_token_expiry = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'email': self.email,
                'phone': self.phone, 'role': self.role,
                'must_change_password': self.must_change_password,
                'is_active': self.is_active,
                'created_at': self.created_at.isoformat() if self.created_at else None}


class Patient(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    phone = Column(String(50))
    dob = Column(String(20))
    gender = Column(String(10))
    blood_type = Column(String(10))
    complaints = Column(Text)
    medical_history = Column(Text)
    allergies = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    name = Column(String(200), nullable=False)
    icon = Column(String(50))
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    templates = relationship("ServiceTemplate", back_populates="service", cascade="all, delete-orphan")

    def to_dict(self):
        return {"id": self.id, "user_id": self.user_id, "name": self.name,
                "icon": self.icon, "description": self.description,
                "templates": [t.to_dict() for t in self.templates]}


class ServiceTemplate(Base):
    __tablename__ = "service_templates"
    id = Column(Integer, primary_key=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    service = relationship("Service", back_populates="templates")
    steps = relationship("TemplateStep", back_populates="template", cascade="all, delete-orphan", order_by="TemplateStep.order")

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
                "description": self.description, "default_duration_days": self.default_duration_days,
                "price": self.price or 0}


class TreatmentPlan(Base):
    __tablename__ = "treatment_plans"
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
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
    steps = relationship("TreatmentStep", back_populates="plan", cascade="all, delete-orphan", order_by="TreatmentStep.order")

    def to_dict(self):
        return {"id": self.id, "patient_id": self.patient_id, "service_id": self.service_id,
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
        return {"id": self.id, "plan_id": self.plan_id, "order": self.order, "title": self.title,
                "description": self.description, "status": self.status,
                "scheduled_date": self.scheduled_date, "completed_date": self.completed_date, "notes": self.notes}


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
                "ref_id": self.ref_id, "created_at": self.created_at.isoformat() if self.created_at else None}


class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    product = Column(String(200), nullable=False)
    company = Column(String(200))
    purchase_date = Column(String(20))
    quantity = Column(Integer, default=1)
    price = Column(Float, default=0)
    category = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "user_id": self.user_id, "product": self.product,
                "company": self.company, "purchase_date": self.purchase_date,
                "quantity": self.quantity, "price": self.price or 0,
                "total": (self.quantity or 1) * (self.price or 0),
                "category": self.category,
                "created_at": self.created_at.isoformat() if self.created_at else None}


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
