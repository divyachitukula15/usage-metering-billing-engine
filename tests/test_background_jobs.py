
import json

from app.models import BackgroundJob, UsageEvent
from app.services.background_jobs import process_background_job


def test_background_job_completes(client):
    db = client.app.state.TestingSessionLocal()

    try:
        usage = UsageEvent(
            tenant_id=1,
            idempotency_key="background-event-001",
            event_type="api",
            api_calls=1,
            input_tokens=100,
            output_tokens=50
        )
        db.add(usage)
        db.commit()
        db.refresh(usage)

        job = BackgroundJob(
            job_type="usage_cost",
            payload=json.dumps({"usage_event_id": usage.id})
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        process_background_job(job.id, client.app.state.TestingSessionLocal)

        db.refresh(job)

        assert job.status == "completed"
        assert job.attempts == 1
        assert "cost" in json.loads(job.payload)

    finally:
        db.close()


def test_background_job_retries_and_fails(client):
    db = client.app.state.TestingSessionLocal()

    try:
        job = BackgroundJob(
            job_type="invalid_job",
            payload="{}"
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        process_background_job(job.id, client.app.state.TestingSessionLocal)

        db.refresh(job)

        assert job.status == "failed"
        assert job.attempts == 3
        assert job.last_error is not None

    finally:
        db.close()
