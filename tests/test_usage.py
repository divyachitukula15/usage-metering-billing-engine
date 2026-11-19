
def test_record_usage(client):

    response = client.post(
        "/usage/",
        json={
            "tenant_id": 1,
            "idempotency_key": "event-001",
            "event_type": "api",
            "api_calls": 1,
            "input_tokens": 100,
            "output_tokens": 50
        }
    )

    assert response.status_code == 200
    print(response.text)
    assert response.json()["tenant_id"] == 1
    assert response.json()["input_tokens"] == 100
    

def test_duplicate_usage(client):

    data = {
        "tenant_id": 1,
        "idempotency_key": "event-001",
        "event_type": "api",
        "api_calls": 1,
        "input_tokens": 100,
        "output_tokens": 50
    }

    first = client.post("/usage/", json=data)
    second = client.post("/usage/", json=data)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


def test_idempotency_key_with_different_data(client):

    data = {
        "tenant_id": 1,
        "idempotency_key": "event-001",
        "event_type": "api",
        "api_calls": 1,
        "input_tokens": 100,
        "output_tokens": 50
    }

    client.post("/usage/", json=data)

    data["input_tokens"] = 200

    response = client.post("/usage/", json=data)

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Idempotency key reused with different data"
    )


def test_idempotency_key_used_by_another_tenant(client):

    data = {
        "tenant_id": 1,
        "idempotency_key": "event-001",
        "event_type": "api",
        "api_calls": 1,
        "input_tokens": 100,
        "output_tokens": 50
    }

    client.post("/usage/", json=data)

    data["tenant_id"] = 2

    response = client.post("/usage/", json=data)

    assert response.status_code == 403
    assert response.json()["detail"] == "Access denied: Tenant mismatch"


def test_api_quota_exceeded(client):

    response = client.post(
        "/usage/",
        json={
            "tenant_id": 1,
            "idempotency_key": "quota-001",
            "event_type": "api",
            "api_calls": 1001,
            "input_tokens": 0,
            "output_tokens": 0
        }
    )

    assert response.status_code == 429
    assert response.json()["detail"] == "Monthly API quota exceeded"
    assert response.headers["Retry-After"] == "3600"

def test_usage_summary(client):

    client.post(
        "/usage/",
        json={
            "tenant_id": 1,
            "idempotency_key": "event-001",
            "event_type": "api",
            "api_calls": 2,
            "input_tokens": 100,
            "output_tokens": 50
        }
    )

    response = client.get("/usage/summary/1")

    assert response.status_code == 200
    print("STATUS:", response.status_code)
    print("RESPONSE:", response.text)

    result = response.json()

    assert result["api_calls"] == 2
    assert result["input_tokens"] == 100
    assert result["output_tokens"] == 50
    assert result["total_tokens"] == 150


def test_usage_for_invalid_tenant(client):

    response = client.post(
        "/usage/",
        json={
            "tenant_id": 999,
            "idempotency_key": "event-001",
            "event_type": "api",
            "api_calls": 1,
            "input_tokens": 100,
            "output_tokens": 50
        }
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Tenant not found"


def test_inactive_pro_subscription_returns_402(client):

    from app.models import Tenant, Subscription

    db = client.app.state.TestingSessionLocal()

    tenant = db.query(Tenant).filter(Tenant.id == 1).first()
    tenant.plan_id = 2

    subscription = Subscription(
        tenant_id=1,
        plan_id=2,
        status="past_due"
    )

    db.add(subscription)
    db.commit()
    db.close()

    response = client.post(
        "/usage/",
        json={
            "tenant_id": 1,
            "idempotency_key": "payment-required-001",
            "event_type": "api",
            "api_calls": 1,
            "input_tokens": 100,
            "output_tokens": 50
        }
    )

    assert response.status_code == 402
    assert "Payment required" in response.json()["detail"]

def test_token_quota_exceeded(client):
    response = client.post(
        "/usage/",
        json={
            "tenant_id": 1,
            "idempotency_key": "token-quota-001",
            "event_type": "api",
            "api_calls": 1,
            "input_tokens": 100001,
            "output_tokens": 0
        }
    )

    assert response.status_code == 429
    assert response.json()["detail"] == "Monthly token quota exceeded"
    assert response.headers["Retry-After"] == "3600"

def test_usage_summary_isolated_by_tenant(client):
    client.post(
        "/usage/",
        json={
            "tenant_id": 1,
            "idempotency_key": "tenant-1-event",
            "event_type": "api",
            "api_calls": 5,
            "input_tokens": 100,
            "output_tokens": 50
        }
    )

    response = client.get("/usage/summary/2",headers={"X-API-Key": "test-api-key-2"})

    assert response.status_code == 200
    assert response.json()["tenant_id"] == 2
    assert response.json()["api_calls"] == 0


def test_missing_api_key(client):
    response = client.get(
        "/usage/summary/1",
        headers={"X-API-Key": ""}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "API key missing"


def test_invalid_api_key(client):
    response = client.get(
        "/usage/summary/1",
        headers={"X-API-Key": "invalid-key"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"