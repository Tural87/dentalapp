from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
from schemas import ToothUpdate

router = APIRouter()


@router.get("/patients/{patient_id}/teeth")
def get_teeth(patient_id: int, db: Session = Depends(get_db)):
    teeth = db.query(models.Tooth).filter(models.Tooth.patient_id == patient_id).all()
    result = {t.tooth_number: {"status": t.status, "notes": t.notes} for t in teeth}
    return result


@router.put("/patients/{patient_id}/teeth/{tooth_num}")
def update_tooth(patient_id: int, tooth_num: int, data: ToothUpdate, db: Session = Depends(get_db)):
    tooth = db.query(models.Tooth).filter(
        models.Tooth.patient_id == patient_id,
        models.Tooth.tooth_number == tooth_num
    ).first()
    if tooth:
        tooth.status = data.status
        tooth.notes = data.notes
    else:
        tooth = models.Tooth(patient_id=patient_id, tooth_number=tooth_num,
                              status=data.status, notes=data.notes)
        db.add(tooth)
    db.commit()
    ev = models.TimelineEvent(
        patient_id=patient_id, event_type="tooth_updated",
        description=f"Diş {tooth_num} statusu: {data.status}", ref_id=tooth_num
    )
    db.add(ev)
    db.commit()
    return {"tooth_number": tooth_num, "status": data.status, "notes": data.notes}
