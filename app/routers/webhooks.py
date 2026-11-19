
from datetime import datetime, timezone

import stripe

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import (
    Subscription,
    StripeWebhookEvent,
    Tenant,
    Plan
)
from app.config import STRIPE_WEBHOOK_SECRET

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    payload = await request.body()
    signature = request.headers.get("stripe-signature")

    # 1. Verify Stripe webhook signature
    try:
        event = stripe.Webhook.construct_event(
            payload,
            signature,
            STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(
            status_code=400,
            detail="Invalid webhook signature or payload"
        )

    event_id = event["id"]
    event_type = event["type"]

    # 2. Check duplicate webhook
    existing = db.query(StripeWebhookEvent).filter(
        StripeWebhookEvent.stripe_event_id == event_id
    ).first()

    if existing:
        return {"message": "Event already processed"}

    webhook_record = StripeWebhookEvent(
        stripe_event_id=event_id,
        event_type=event_type,
        processed=0
    )
    db.add(webhook_record)

    try:
        raw_obj = event["data"]["object"]

        obj = (
            raw_obj.to_dict()
            if hasattr(raw_obj, "to_dict")
            else raw_obj
        )

        # 3. Checkout completed
        if event_type == "checkout.session.completed":

            metadata = obj.get("metadata") or {}

            tenant_id = metadata.get("tenant_id")
            plan_id = metadata.get("plan_id")
            stripe_subscription_id = obj.get("subscription")

            if tenant_id and plan_id and stripe_subscription_id:

                tenant = db.query(Tenant).filter(
                    Tenant.id == int(tenant_id)
                ).first()

                plan = db.query(Plan).filter(
                    Plan.id == int(plan_id)
                ).first()

                if tenant and plan:

                    subscription = db.query(Subscription).filter(
                        Subscription.stripe_subscription_id
                        == stripe_subscription_id
                    ).first()

                    payment_status = obj.get("payment_status")

                    if not subscription:
                        subscription = Subscription(
                            tenant_id=tenant.id,
                            plan_id=plan.id,
                            status=(
                                "active"
                                if payment_status == "paid"
                                else "incomplete"
                            ),
                            stripe_customer_id=obj.get("customer"),
                            stripe_subscription_id=stripe_subscription_id
                        )
                        db.add(subscription)

                    else:
                        subscription.plan_id = plan.id
                        subscription.status = (
                            "active"
                            if payment_status == "paid"
                            else "incomplete"
                        )

                    # Update tenant plan only after successful payment
                    if payment_status == "paid":
                        tenant.plan_id = plan.id

        # 4. Subscription updated or deleted
        elif event_type in (
            "customer.subscription.updated",
            "customer.subscription.deleted"
        ):

            subscription = db.query(Subscription).filter(
                Subscription.stripe_subscription_id == obj["id"]
            ).first()

            if subscription:

                tenant = db.query(Tenant).filter(
                    Tenant.id == subscription.tenant_id
                ).first()

                if event_type == "customer.subscription.deleted":

                    subscription.status = "canceled"

                    # Downgrade tenant to Free plan
                    free_plan = db.query(Plan).filter(
                        Plan.name == "Free"
                    ).first()

                    if tenant and free_plan:
                        tenant.plan_id = free_plan.id

                else:
                    subscription.status = obj["status"]

                    # Sync plan when subscription is active
                    metadata = obj.get("metadata") or {}
                    plan_id = metadata.get("plan_id")

                    if (
                        tenant
                        and plan_id
                        and obj["status"] in ("active", "trialing")
                    ):
                        plan = db.query(Plan).filter(
                            Plan.id == int(plan_id)
                        ).first()

                        if plan:
                            tenant.plan_id = plan.id
                            subscription.plan_id = plan.id

                if obj.get("current_period_start"):
                    subscription.current_period_start = (
                        datetime.fromtimestamp(
                            obj["current_period_start"],
                            tz=timezone.utc
                        )
                    )

                if obj.get("current_period_end"):
                    subscription.current_period_end = (
                        datetime.fromtimestamp(
                            obj["current_period_end"],
                            tz=timezone.utc
                        )
                    )

        # 5. Mark webhook as processed
        webhook_record.processed = 1

        db.commit()

        return {
            "message": "Webhook processed successfully"
        }

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Webhook processing failed"
        )
