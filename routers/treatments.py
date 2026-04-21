from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from database import get_db
import models
from schemas import PlanCreate, PlanUpdate, StepCreate, StepUpdate
from datetime import datetime, timedelta

router = APIRouter()


def plan_to_dict(p):
    return {
        "id": p.id, "patient_id": p.patient_id, "service_id": p.service_id,
        "template_id": p.template_id, "title": p.title, "status": p.status,
        "start_date": p.start_date, "end_date": p.end_date, "notes": p.notes,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "steps": [step_to_dict(s) for s in sorted(p.steps, key=lambda x: x.order)]
    }


def step_to_dict(s):
    return {
        "id": s.id, "plan_id": s.plan_id, "order": s.order, "title": s.title,
        "description": s.description, "status": s.status,
        "scheduled_date": s.scheduled_date, "completed_date": s.completed_date, "notes": s.notes
    }


@router.get("/patients/{patient_id}/plans")
def list_plans(patient_id: int, db: Session = Depends(get_db)):
    plans = db.query(models.TreatmentPlan).filter(
        models.TreatmentPlan.patient_id == patient_id
    ).order_by(desc(models.TreatmentPlan.created_at)).all()
    return [plan_to_dict(p) for p in plans]


@router.post("/patients/{patient_id}/plans", status_code=201)
def create_plan(patient_id: int, data: PlanCreate, db: Session = Depends(get_db)):
    plan = models.TreatmentPlan(patient_id=patient_id, **data.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    # Auto-fill steps from template
    if data.template_id:
        tmpl_steps = db.query(models.TemplateStep).filter(
            models.TemplateStep.template_id == data.template_id
        ).order_by(models.TemplateStep.order).all()
        start = datetime.utcnow()
        for ts in tmpl_steps:
            sched = (start + timedelta(days=ts.default_duration_days * ts.order)).strftime("%Y-%m-%d")
            step = models.TreatmentStep(
                plan_id=plan.id, order=ts.order, title=ts.title,
                description=ts.description, scheduled_date=sched
            )
            db.add(step)
        db.commit()
        db.refresh(plan)
    ev = models.TimelineEvent(
        patient_id=patient_id, event_type="plan_created",
        description=f"Müalicə planı yaradıldı: {plan.title}", ref_id=plan.id
    )
    db.add(ev)
    db.commit()
    db.refresh(plan)
    return plan_to_dict(plan)


@router.get("/plans/{plan_id}")
def get_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(models.TreatmentPlan).filter(models.TreatmentPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plan tapılmadı")
    return plan_to_dict(plan)


@router.put("/plans/{plan_id}")
def update_plan(plan_id: int, data: PlanUpdate, db: Session = Depends(get_db)):
    plan = db.query(models.TreatmentPlan).filter(models.TreatmentPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plan tapılmadı")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(plan, k, v)
    db.commit()
    db.refresh(plan)
    return plan_to_dict(plan)


@router.delete("/plans/{plan_id}")
def delete_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(models.TreatmentPlan).filter(models.TreatmentPlan.id == plan_id).first()
    if not plan:
        raise HTTPException(404, "Plan tapılmadı")
    db.delete(plan)
    db.commit()
    return {"ok": True}


@router.post("/plans/{plan_id}/steps", status_code=201)
def add_step(plan_id: int, data: StepCreate, db: Session = Depends(get_db)):
    step = models.TreatmentStep(plan_id=plan_id, **data.model_dump())
    db.add(step)
    db.commit()
    db.refresh(step)
    return step_to_dict(step)


@router.put("/steps/{step_id}")
def update_step(step_id: int, data: StepUpdate, db: Session = Depends(get_db)):
    step = db.query(models.TreatmentStep).filter(models.TreatmentStep.id == step_id).first()
    if not step:
        raise HTTPException(404, "Addım tapılmadı")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(step, k, v)
    if data.status == "done" and not step.completed_date:
        step.completed_date = datetime.utcnow().strftime("%Y-%m-%d")
    db.commit()
    plan = db.query(models.TreatmentPlan).filter(models.TreatmentPlan.id == step.plan_id).first()
    if plan:
        all_done = all(s.status == "done" or s.status == "skipped" for s in plan.steps)
        if all_done and plan.steps:
            plan.status = "completed"
            db.commit()
    return step_to_dict(step)


@router.delete("/steps/{step_id}")
def delete_step(step_id: int, db: Session = Depends(get_db)):
    step = db.query(models.TreatmentStep).filter(models.TreatmentStep.id == step_id).first()
    if not step:
        raise HTTPException(404, "Addım tapılmadı")
    db.delete(step)
    db.commit()
    return {"ok": True}
