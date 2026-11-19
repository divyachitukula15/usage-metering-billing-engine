
import json
from unittest.mock import patch

from app.models import Subscription


def make_event(event_id, event_type, obj):
    return {
        "id": event_id,
        "type": event_type,
        "data": {
            "object": obj
        }
    }


def send_event(client, event):
    return client.post(
        "/webhooks/stripe",
        content=json.dumps(event),
        headers={"stripe-signature": "test_signature"}
    )


@patch("app.routers.webhooks.stripe.Webhook.construct_event")
def test_invalid_signature(mock_construct, client):

    import stripe

    mock_construct.side_effect = stripe.error.SignatureVerificationError(
        "Invalid signature", "test_signature"
    )

    response = send_event(client, {})

    assert response.status_code == 400


@patch("app.routers.webhooks.stripe.Webhook.construct_event")
def test_checkout_completed(mock_construct, client):

    mock_construct.return_value = make_event(
        "evt_checkout_001",
        "checkout.session.completed",
        {
            "metadata": {
                "tenant_id": "1",
                "plan_id": "1"
            },
            "subscription": "sub_test_001",
            "payment_status": "paid",
            "customer": "cus_test_001"
        }
    )

    response = send_event(client, mock_construct.return_value)

    assert response.status_code == 200

    result = response.json()
    assert result["message"] == "Webhook processed successfully"


@patch("app.routers.webhooks.stripe.Webhook.construct_event")
def test_checkout_upgrades_tenant_to_pro(mock_construct, client):

    from app.models import Tenant

    event = make_event(
        "evt_pro_upgrade_001",
        "checkout.session.completed",
        {
            "metadata": {
                "tenant_id": "1",
                "plan_id": "2"
            },
            "subscription": "sub_pro_001",
            "payment_status": "paid",
            "customer": "cus_pro_001"
        }
    )

    mock_construct.return_value = event

    response = send_event(client, event)

    assert response.status_code == 200

    db = client.app.state.TestingSessionLocal()
    tenant = db.query(Tenant).filter(Tenant.id == 1).first()

    assert tenant.plan_id == 2

    db.close()


@patch("app.routers.webhooks.stripe.Webhook.construct_event")
def test_duplicate_webhook(mock_construct, client):

    event = make_event(
        "evt_duplicate_001",
        "customer.subscription.updated",
        {
            "id": "sub_test_001",
            "status": "active"
        }
    )

    mock_construct.return_value = event

    first = send_event(client, event)
    second = send_event(client, event)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["message"] == "Event already processed"


@patch("app.routers.webhooks.stripe.Webhook.construct_event")
def test_subscription_updated(mock_construct, client):

    from app.database import Base
    from app.models import Tenant, Plan

    event = make_event(
        "evt_updated_001",
        "customer.subscription.updated",
        {
            "id": "sub_test_002",
            "status": "past_due",
            "current_period_start": 1794700800,
            "current_period_end": 1797292800
        }
    )

    mock_construct.return_value = event

    # Create a subscription through checkout first.
    checkout = make_event(
        "evt_checkout_002",
        "checkout.session.completed",
        {
            "metadata": {"tenant_id": "1", "plan_id": "1"},
            "subscription": "sub_test_002",
            "payment_status": "paid",
            "customer": "cus_test_002"
        }
    )

    send_event(client, checkout)

    response = send_event(client, event)

    assert response.status_code == 200


@patch("app.routers.webhooks.stripe.Webhook.construct_event")
def test_subscription_deleted(mock_construct, client):

    checkout = make_event(
        "evt_checkout_003",
        "checkout.session.completed",
        {
            "metadata": {"tenant_id": "1", "plan_id": "2"},
            "subscription": "sub_test_003",
            "payment_status": "paid",
            "customer": "cus_test_003"
        }
    )

    mock_construct.return_value = checkout
    send_event(client, checkout)

    deleted = make_event(
        "evt_deleted_001",
        "customer.subscription.deleted",
        {"id": "sub_test_003"}
    )

    mock_construct.return_value = deleted

    response = send_event(client, deleted)

    assert response.status_code == 200


@patch("app.routers.webhooks.stripe.Webhook.construct_event")
def test_unknown_event(mock_construct, client):

    event = make_event(
        "evt_unknown_001",
        "some.unknown.event",
        {}
    )

    mock_construct.return_value = event

    response = send_event(client, event)

    assert response.status_code == 200
    assert response.json()["message"] == "Webhook processed successfully"
