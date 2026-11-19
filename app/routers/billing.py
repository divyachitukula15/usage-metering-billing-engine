
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Tenant, Plan
from app.services import stripe_client

router = APIRouter(prefix="/billing", tags=["Billing"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/checkout/{tenant_id}/{plan_id}")
def create_checkout_session(
    tenant_id: int,
    plan_id: int,
    db: Session = Depends(get_db)
):
    tenant = db.query(Tenant).filter(
        Tenant.id == tenant_id
    ).first()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    plan = db.query(Plan).filter(
        Plan.id == plan_id
    ).first()

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    if plan.monthly_price <= 0:
        raise HTTPException(
            status_code=400,
            detail="Checkout is not required for free plans"
        )

    try:
        session = stripe_client.stripe.checkout.Session.create(
            mode="subscription",
            customer_email=tenant.email,
            line_items=[
                {
                    "price_data": {
                        "currency": "inr",
                        "unit_amount": plan.monthly_price * 100,
                        "recurring": {"interval": "month"},
                        "product_data": {
                            "name": f"{plan.name} Plan"
                        }
                    },
                    "quantity": 1
                }
            ],
            metadata={
                "tenant_id": str(tenant.id),
                "plan_id": str(plan.id)
            },

            subscription_data={
                "metadata": {
                    "tenant_id": str(tenant.id),
                    "plan_id": str(plan.id)
                }
            },

            success_url="http://localhost:8000/billing/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="http://localhost:8000/billing/cancel"
        )

        return {
            "checkout_url": session.url,
            "session_id": session.id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/success")
def payment_success(session_id: str):
    return {
        "message": "Checkout completed. Payment confirmation is pending webhook verification.",
        "session_id": session_id
    }


@router.get("/cancel")
def payment_cancel():
    return {
        "message": "Checkout was cancelled."
    }