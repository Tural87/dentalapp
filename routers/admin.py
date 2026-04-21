from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
import models, json, os

router = APIRouter()
SETTINGS_FILE = "settings.json"
DEFAULT_SETTINGS = {"clinic_name": "DentalApp", "doctor_name": "", "phone": "", "address": ""}


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    return DEFAULT_SETTINGS.copy()


def save_settings(data: dict):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@router.get("/admin/settings")
def get_settings():
    return load_settings()


@router.put("/admin/settings")
def update_settings(data: dict):
    current = load_settings()
    current.update(data)
    save_settings(current)
    return current
