from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List
from database import get_db
import models
from schemas import PatientCreate, PatientUpdate
from datetime import datetime

router = APIRouter()


def patient_to_dict(p):
    return {
        "id": p.id, "name": p.name, "phone": p.phone, "dob": p.dob,
        "gender": p.gender, "blood_type": p.blood_type,
        "complaints": p.complaints, "medical_history": p.medical_history,
        "allergies": p.allergies, "notes": p.notes,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.get("/patients")
def list_patients(q: str = "", db: Session = Depends(get_db)):
    query = db.query(models.Patient)
    if q:
        query = query.filter(models.Patient.name.ilike(f"%{q}%"))
    patients = query.order_by(desc(models.Patient.created_at)).all()
    return [patient_to_dict(p) for p in patients]


@router.post("/patients", status_code=201)
def create_patient(data: PatientCreate, db: Session = Depends(get_db)):
    p = models.Patient(**data.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    ev = models.TimelineEvent(patient_id=p.id, event_type="created",
                               description="Xəstə profili yaradıldı", ref_id=p.id)
    db.add(ev)
    db.commit()
    return patient_to_dict(p)


@router.get("/patients/{patient_id}")
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    p = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    if not p:
        raise HTTPException(404, "Xəstə tapılmadı")
    return patient_to_dict(p)


@router.put("/patients/{patient_id}")
def update_patient(patient_id: int, data: PatientUpdate, db: Session = Depends(get_db)):
    p = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    if not p:
        raise HTTPException(404, "Xəstə tapılmadı")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    p.updated_at = datetime.utcnow()
    db.commit()
    return patient_to_dict(p)


@router.delete("/patients/{patient_id}")
def delete_patient(patient_id: int, db: Session = Depends(get_db)):
    p = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    if not p:
        raise HTTPException(404, "Xəstə tapılmadı")
    db.delete(p)
    db.commit()
    return {"ok": True}


@router.get("/patients/{patient_id}/timeline")
def get_timeline(patient_id: int, db: Session = Depends(get_db)):
    events = db.query(models.TimelineEvent).filter(
        models.TimelineEvent.patient_id == patient_id
    ).order_by(desc(models.TimelineEvent.created_at)).all()
    return [{
        "id": e.id, "event_type": e.event_type, "description": e.description,
        "ref_id": e.ref_id, "created_at": e.created_at.isoformat() if e.created_at else None
    } for e in events]


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    from sqlalchemy import func
    total = db.query(func.count(models.Patient.id)).scalar()
    today = datetime.utcnow().date()
    today_count = db.query(func.count(models.Patient.id)).filter(
        func.date(models.Patient.created_at) == today
    ).scalar()
    active_plans = db.query(func.count(models.TreatmentPlan.id)).filter(
        models.TreatmentPlan.status == "in_progress"
    ).scalar()
    return {"total_patients": total, "today_patients": today_count, "active_plans": active_plans}
