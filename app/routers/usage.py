
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import SessionLocal
from app.models import Tenant, UsageEvent
from app.schemas import UsageEventCreate
from app.services.quota import check_quota
from app.services.cost import calculate_cost

import hashlib
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session, sessionmaker

from app.services.background_jobs import (
    create_background_job,
    process_background_job
)

router = APIRouter(prefix="/usage", tags=["Usage"])

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_tenant(
    api_key: str = Depends(api_key_header),
    db: Session = Depends(get_db)
):
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key missing"
        )

    hashed_api_key = hashlib.sha256(api_key.encode()).hexdigest()

    tenant = db.query(Tenant).filter(
        Tenant.api_key == hashed_api_key
    ).first()

    if not tenant:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    return tenant



@router.post("/")
def record_usage(
    data: UsageEventCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant)
):
    tenant = db.query(Tenant).filter(
        Tenant.id == data.tenant_id
    ).first()

    if not tenant:
        raise HTTPException(
            status_code=404,
            detail="Tenant not found"
        )

    if data.tenant_id != current_tenant.id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: Tenant mismatch"
        )

    existing = db.query(UsageEvent).filter(
        UsageEvent.idempotency_key == data.idempotency_key
    ).first()

    if existing:
        if existing.tenant_id != current_tenant.id:
            raise HTTPException(
                status_code=409,
                detail="Idempotency key already used"
            )

        if (
            existing.event_type != data.event_type
            or existing.api_calls != data.api_calls
            or existing.input_tokens != data.input_tokens
            or existing.output_tokens != data.output_tokens
            or existing.cached_input_tokens != data.cached_input_tokens
            or existing.reasoning_tokens != data.reasoning_tokens
        ):
            raise HTTPException(
                status_code=409,
                detail="Idempotency key reused with different data"
            )

        return existing

    total_tokens = data.input_tokens + data.output_tokens

    check_quota(
        db, current_tenant, data.api_calls, total_tokens
    )

    usage = UsageEvent(**data.model_dump())

    db.add(usage)
    db.commit()
    db.refresh(usage)

    job_id = create_background_job(
        db,
        "usage_cost",
        {"usage_event_id": usage.id}
    )

    session_factory = sessionmaker(
        bind=db.get_bind(),
        expire_on_commit=False
    )

    background_tasks.add_task(
        process_background_job,
        job_id,
        session_factory
    )

    return {
    "id": usage.id,
    "tenant_id": usage.tenant_id,
    "idempotency_key": usage.idempotency_key,
    "event_type": usage.event_type,
    "api_calls": usage.api_calls,
    "input_tokens": usage.input_tokens,
    "output_tokens": usage.output_tokens,
    "cached_input_tokens": usage.cached_input_tokens,
    "reasoning_tokens": usage.reasoning_tokens,
    "created_at": usage.created_at
}



@router.get("/summary/{tenant_id}")
def get_usage_summary(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_tenant: Tenant = Depends(get_current_tenant)
):
    if tenant_id != current_tenant.id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: Tenant mismatch"
        )

    now = datetime.now(timezone.utc)

    month_start = now.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    usage = db.query(
        func.coalesce(func.sum(UsageEvent.api_calls), 0).label("api_calls"),
        func.coalesce(func.sum(UsageEvent.input_tokens), 0).label("input_tokens"),
        func.coalesce(func.sum(UsageEvent.output_tokens), 0).label("output_tokens"),
        func.coalesce(func.sum(UsageEvent.cached_input_tokens), 0).label("cached_tokens"),
        func.coalesce(func.sum(UsageEvent.reasoning_tokens), 0).label("reasoning_tokens")
    ).filter(
        UsageEvent.tenant_id == current_tenant.id,
        UsageEvent.created_at >= month_start
    ).first()

    cost = calculate_cost(
        api_calls=usage.api_calls,
        input_tokens=usage.input_tokens,
        cached_input_tokens=usage.cached_tokens,
        output_tokens=usage.output_tokens,
        reasoning_tokens=usage.reasoning_tokens
    )

    return {
        "tenant_id": current_tenant.id,
        "month": now.strftime("%Y-%m"),
        "api_calls": usage.api_calls,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cached_input_tokens": usage.cached_tokens,
        "reasoning_tokens": usage.reasoning_tokens,
        "total_tokens": usage.input_tokens + usage.output_tokens,
        "cost": cost
    }
