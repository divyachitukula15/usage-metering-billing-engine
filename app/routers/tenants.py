
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Tenant
from app.schemas import TenantCreate

import secrets
import hashlib

router = APIRouter(prefix="/tenants", tags=["Tenants"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/")
def create_tenant(data: TenantCreate, db: Session = Depends(get_db)):
    existing = db.query(Tenant).filter(
        Tenant.email == data.email
    ).first()

    if existing:
        raise HTTPException(status_code=409, detail="Email already exists")

    api_key = secrets.token_urlsafe(32)
    hashed_api_key = hashlib.sha256(api_key.encode()).hexdigest()

    tenant = Tenant(
        name=data.name,
        email=data.email,
        plan_id=data.plan_id,
        api_key=hashed_api_key
    )

    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    return {
    "id": tenant.id,
    "name": tenant.name,
    "email": tenant.email,
    "plan_id": tenant.plan_id,
    "api_key": api_key
}