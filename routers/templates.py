from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
from schemas import ServiceCreate, TemplateCreate, TemplateStepCreate

router = APIRouter()


def service_to_dict(s):
    return {
        "id": s.id, "name": s.name, "icon": s.icon,
        "description": s.description, "default_simulation_type": s.default_simulation_type,
        "templates": [tmpl_to_dict(t) for t in s.templates]
    }


def tmpl_to_dict(t):
    return {
        "id": t.id, "service_id": t.service_id, "name": t.name,
        "description": t.description,
        "steps": [{"id": s.id, "order": s.order, "title": s.title,
                   "description": s.description, "default_duration_days": s.default_duration_days}
                  for s in sorted(t.steps, key=lambda x: x.order)]
    }


@router.get("/services")
def list_services(db: Session = Depends(get_db)):
    return [service_to_dict(s) for s in db.query(models.Service).all()]


@router.post("/services", status_code=201)
def create_service(data: ServiceCreate, db: Session = Depends(get_db)):
    s = models.Service(**data.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return service_to_dict(s)


@router.put("/services/{service_id}")
def update_service(service_id: int, data: ServiceCreate, db: Session = Depends(get_db)):
    s = db.query(models.Service).filter(models.Service.id == service_id).first()
    if not s:
        raise HTTPException(404, "Xidmət tapılmadı")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    db.commit()
    return service_to_dict(s)


@router.delete("/services/{service_id}")
def delete_service(service_id: int, db: Session = Depends(get_db)):
    s = db.query(models.Service).filter(models.Service.id == service_id).first()
    if not s:
        raise HTTPException(404, "Xidmət tapılmadı")
    db.delete(s)
    db.commit()
    return {"ok": True}


@router.post("/services/{service_id}/templates", status_code=201)
def create_template(service_id: int, data: TemplateCreate, db: Session = Depends(get_db)):
    t = models.ServiceTemplate(service_id=service_id, **data.model_dump())
    db.add(t)
    db.commit()
    db.refresh(t)
    return tmpl_to_dict(t)


@router.put("/templates/{template_id}")
def update_template(template_id: int, data: TemplateCreate, db: Session = Depends(get_db)):
    t = db.query(models.ServiceTemplate).filter(models.ServiceTemplate.id == template_id).first()
    if not t:
        raise HTTPException(404, "Şablon tapılmadı")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    db.commit()
    return tmpl_to_dict(t)


@router.delete("/templates/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db)):
    t = db.query(models.ServiceTemplate).filter(models.ServiceTemplate.id == template_id).first()
    if not t:
        raise HTTPException(404, "Şablon tapılmadı")
    db.delete(t)
    db.commit()
    return {"ok": True}


@router.post("/templates/{template_id}/steps", status_code=201)
def add_template_step(template_id: int, data: TemplateStepCreate, db: Session = Depends(get_db)):
    s = models.TemplateStep(template_id=template_id, **data.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return {"id": s.id, "order": s.order, "title": s.title,
            "description": s.description, "default_duration_days": s.default_duration_days}


@router.delete("/template-steps/{step_id}")
def delete_template_step(step_id: int, db: Session = Depends(get_db)):
    s = db.query(models.TemplateStep).filter(models.TemplateStep.id == step_id).first()
    if not s:
        raise HTTPException(404, "Addım tapılmadı")
    db.delete(s)
    db.commit()
    return {"ok": True}
