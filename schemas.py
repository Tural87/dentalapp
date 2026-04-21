from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class PatientCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    dob: Optional[str] = None
    gender: Optional[str] = None
    blood_type: Optional[str] = None
    complaints: Optional[str] = None
    medical_history: Optional[str] = None
    allergies: Optional[str] = None
    notes: Optional[str] = None


class PatientUpdate(PatientCreate):
    name: Optional[str] = None


class ToothUpdate(BaseModel):
    status: str
    notes: Optional[str] = None


class ServiceCreate(BaseModel):
    name: str
    icon: Optional[str] = None
    description: Optional[str] = None
    default_simulation_type: Optional[str] = None


class TemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None


class TemplateStepCreate(BaseModel):
    order: int = 0
    title: str
    description: Optional[str] = None
    default_duration_days: int = 7


class PlanCreate(BaseModel):
    title: str
    service_id: Optional[int] = None
    template_id: Optional[int] = None
    status: str = "planned"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    notes: Optional[str] = None


class PlanUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    notes: Optional[str] = None


class StepCreate(BaseModel):
    order: int = 0
    title: str
    description: Optional[str] = None
    status: str = "pending"
    scheduled_date: Optional[str] = None
    notes: Optional[str] = None


class StepUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    scheduled_date: Optional[str] = None
    completed_date: Optional[str] = None
    notes: Optional[str] = None
