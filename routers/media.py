from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from database import get_db
import models
import os, uuid, shutil
from typing import Optional

router = APIRouter()
UPLOAD_DIR = "static/uploads"


def media_to_dict(m):
    return {
        "id": m.id, "patient_id": m.patient_id, "step_id": m.step_id,
        "tooth_number": m.tooth_number, "type": m.type,
        "filename": m.filename, "filepath": m.filepath, "caption": m.caption,
        "url": f"/uploads/{m.filename}",
        "uploaded_at": m.uploaded_at.isoformat() if m.uploaded_at else None
    }


@router.post("/media/upload", status_code=201)
async def upload_media(
    file: UploadFile = File(...),
    patient_id: int = Form(...),
    type: str = Form("other"),
    step_id: Optional[int] = Form(None),
    tooth_number: Optional[int] = Form(None),
    caption: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    ext = os.path.splitext(file.filename)[1]
    fname = f"{uuid.uuid4().hex}{ext}"
    fpath = os.path.join(UPLOAD_DIR, fname)
    with open(fpath, "wb") as f:
        shutil.copyfileobj(file.file, f)
    m = models.Media(
        patient_id=patient_id, step_id=step_id, tooth_number=tooth_number,
        type=type, filename=fname, filepath=fpath, caption=caption
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return media_to_dict(m)


@router.get("/patients/{patient_id}/media")
def get_media(patient_id: int, type: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(models.Media).filter(models.Media.patient_id == patient_id)
    if type:
        q = q.filter(models.Media.type == type)
    return [media_to_dict(m) for m in q.order_by(models.Media.uploaded_at.desc()).all()]


@router.delete("/media/{media_id}")
def delete_media(media_id: int, db: Session = Depends(get_db)):
    m = db.query(models.Media).filter(models.Media.id == media_id).first()
    if not m:
        raise HTTPException(404, "Media tapılmadı")
    if m.filepath and os.path.exists(m.filepath):
        os.remove(m.filepath)
    db.delete(m)
    db.commit()
    return {"ok": True}
