
def test_create_tenant(client):

    response = client.post(
        "/tenants/",
        json={
            "name": "Test Customer",
            "email": "test@example.com",
            "plan_id": 1
        }
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Test Customer"
    assert response.json()["email"] == "test@example.com"


def test_duplicate_email(client):

    data = {
        "name": "Test Customer",
        "email": "test@example.com",
        "plan_id": 1
    }

    client.post("/tenants/", json=data)

    response = client.post("/tenants/", json=data)

    assert response.status_code == 409
    assert response.json()["detail"] == "Email already exists"


def test_invalid_email(client):

    response = client.post(
        "/tenants/",
        json={
            "name": "Test Customer",
            "email": "invalid-email",
            "plan_id": 1
        }
    )

    assert response.status_code == 422
