
from unittest.mock import patch, Mock


def test_tenant_not_found(client):
    response = client.post("/billing/checkout/999/2")

    assert response.status_code == 404
    assert response.json()["detail"] == "Tenant not found"


def test_plan_not_found(client):
    response = client.post("/billing/checkout/1/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Plan not found"


def test_free_plan_checkout(client):
    response = client.post("/billing/checkout/1/1")

    assert response.status_code == 400
    assert response.json()["detail"] == "Checkout is not required for free plans"


@patch("app.routers.billing.stripe_client.stripe.checkout.Session.create")
def test_successful_checkout(mock_create, client):

    mock_create.return_value = Mock(
        url="https://checkout.stripe.com/test",
        id="cs_test_123"
    )

    response = client.post("/billing/checkout/1/2")

    assert response.status_code == 200
    assert response.json() == {
        "checkout_url": "https://checkout.stripe.com/test",
        "session_id": "cs_test_123"
    }

    mock_create.assert_called_once()


@patch("app.routers.billing.stripe_client.stripe.checkout.Session.create")
def test_stripe_failure(mock_create, client):

    mock_create.side_effect = Exception("Stripe error")

    response = client.post("/billing/checkout/1/2")

    assert response.status_code == 500
    assert response.json()["detail"] == "Stripe error"


def test_payment_success(client):
    response = client.get("/billing/success?session_id=cs_test_123")

    assert response.status_code == 200
    assert response.json()["session_id"] == "cs_test_123"


def test_payment_cancel(client):
    response = client.get("/billing/cancel")

    assert response.status_code == 200
    assert response.json()["message"] == "Checkout was cancelled."
