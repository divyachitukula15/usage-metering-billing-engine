
import json
import logging

from sqlalchemy.orm import Session, sessionmaker

from app.models import BackgroundJob, UsageEvent
from app.services.cost import calculate_cost

logger = logging.getLogger(__name__)


def create_background_job(db: Session, job_type: str, payload: dict):
    job = BackgroundJob(
        job_type=job_type,
        payload=json.dumps(payload),
        status="pending"
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    return job.id


def process_background_job(job_id: int, session_factory):
    db = session_factory()

    try:
        job = db.query(BackgroundJob).filter(
            BackgroundJob.id == job_id
        ).first()

        if not job or job.status == "completed":
            return

        for _ in range(job.attempts, job.max_attempts):
            job.status = "processing"
            job.attempts += 1
            db.commit()

            try:
                payload = json.loads(job.payload)

                if job.job_type != "usage_cost":
                    raise ValueError("Unknown background job type")

                usage = db.query(UsageEvent).filter(
                    UsageEvent.id == payload["usage_event_id"]
                ).first()

                if not usage:
                    raise ValueError("Usage event not found")

                cost = calculate_cost(
                    api_calls=usage.api_calls,
                    input_tokens=usage.input_tokens,
                    cached_input_tokens=usage.cached_input_tokens,
                    output_tokens=usage.output_tokens,
                    reasoning_tokens=usage.reasoning_tokens
                )

                payload["cost"] = cost
                job.payload = json.dumps(payload)
                job.status = "completed"
                job.last_error = None
                db.commit()

                logger.info("Background job %s completed", job_id)
                return

            except Exception as error:
                db.rollback()

                job = db.query(BackgroundJob).filter(
                    BackgroundJob.id == job_id
                ).first()

                job.last_error = str(error)

                if job.attempts >= job.max_attempts:
                    job.status = "failed"
                    logger.error(
                        "Background job %s permanently failed: %s",
                        job_id, error
                    )
                else:
                    job.status = "pending"
                    logger.warning(
                        "Background job %s failed. Retry %s/%s: %s",
                        job_id, job.attempts, job.max_attempts, error
                    )

                db.commit()

    finally:
        db.close()
