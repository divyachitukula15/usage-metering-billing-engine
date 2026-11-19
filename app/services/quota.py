
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import Tenant, Plan, UsageEvent, Subscription


def check_quota(db: Session, tenant: Tenant, api_calls: int, tokens: int):

    # Check current subscription
    subscription = db.query(Subscription).filter(
        Subscription.tenant_id == tenant.id
    ).order_by(Subscription.created_at.desc()).first()

    # Block unpaid or inactive paid subscriptions
    if subscription and subscription.plan_id == tenant.plan_id:
        if subscription.status not in ("active", "trialing"):
            free_plan = db.query(Plan).filter(
                Plan.name == "Free"
            ).first()

            if not free_plan or tenant.plan_id != free_plan.id:
                raise HTTPException(
                    status_code=402,
                    detail="Payment required. Please renew or upgrade your subscription."
                )

    now = datetime.now(timezone.utc)

    month_start = now.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    plan = db.query(Plan).filter(
        Plan.id == tenant.plan_id
    ).first()

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    usage = db.query(
        func.coalesce(func.sum(UsageEvent.api_calls), 0),
        func.coalesce(
            func.sum(
                UsageEvent.input_tokens + UsageEvent.output_tokens
            ), 0
        )
    ).filter(
        UsageEvent.tenant_id == tenant.id,
        UsageEvent.created_at >= month_start
    ).first()

    total_api_calls = usage[0] + api_calls
    total_tokens = usage[1] + tokens

    if total_api_calls > plan.monthly_api_limit:
        raise HTTPException(
            status_code=429,
            detail="Monthly API quota exceeded",
            headers={"Retry-After": "3600"}
        )

    if total_tokens > plan.monthly_token_limit:
        raise HTTPException(
            status_code=429,
            detail="Monthly token quota exceeded",
            headers={"Retry-After": "3600"}
        )
