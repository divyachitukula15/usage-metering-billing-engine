
import hashlib
import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Plan, Tenant
from app.routers import tenants, usage, webhooks, billing


@pytest.fixture
def client():

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )

    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(tenants.router)
    app.include_router(usage.router)
    app.include_router(webhooks.router)
    app.include_router(billing.router)

    app.state.TestingSessionLocal = TestingSessionLocal

    app.dependency_overrides[tenants.get_db] = override_get_db
    app.dependency_overrides[usage.get_db] = override_get_db
    app.dependency_overrides[webhooks.get_db] = override_get_db
    app.dependency_overrides[billing.get_db] = override_get_db

    db = TestingSessionLocal()

    db.add_all([
        Plan(
            id=1,
            name="Free",
            monthly_api_limit=1000,
            monthly_token_limit=100000,
            monthly_price=0
        ),
        Plan(
            id=2,
            name="Pro",
            monthly_api_limit=10000,
            monthly_token_limit=1000000,
            monthly_price=499
        ),
        Tenant(
            id=1,
            name="Test Customer",
            email="customer1@example.com",
            plan_id=1,
            api_key=hashlib.sha256(
                "test-api-key-1".encode()
            ).hexdigest()
        ),
        Tenant(
            id=2,
            name="Second Customer",
            email="customer2@example.com",
            plan_id=1,
            api_key=hashlib.sha256(
                "test-api-key-2".encode()
            ).hexdigest()
        )
    ])

    db.commit()
    db.close()

    with TestClient(
        app,
        headers={"X-API-Key": "test-api-key-1"}
    ) as test_client:
        yield test_client

    Base.metadata.drop_all(bind=engine)
    engine.dispose()
