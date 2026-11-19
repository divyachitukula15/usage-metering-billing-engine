# Usage Metering & Billing Engine

A FastAPI backend that records tenant API and AI-token usage, enforces monthly plan limits, calculates usage costs, and integrates subscription billing with Stripe Checkout.

Built as the FlyRank Backend Track capstone.

## Features

- Tenant creation with a generated API key. The raw key is returned at creation; its SHA-256 hash is stored.
- API-key authentication for usage recording and usage-summary endpoints using the `X-API-Key` header.
- Tenant ownership checks on usage endpoints.
- Idempotent usage recording: repeating the same request with the same key returns the existing event; reusing the key with different data is rejected.
- Monthly API-call and token quota enforcement.
- `402 Payment Required` for an inactive/lapsed paid subscription where the paid plan is no longer permitted.
- `429 Too Many Requests` when monthly API-call or token quotas are exceeded, with a `Retry-After: 3600` response header.
- Monthly usage summaries and configurable demo cost calculations.
- Stripe Checkout and signed webhook handling, including duplicate-event protection and local subscription/plan updates.
- Database-backed background-job records for usage-cost processing, with up to three attempts and error logging on permanent failure.
- Alembic database migrations.
- Automated tests. The latest full test run reported by the developer during this build was **35 passed**.

Token counts are supplied by the caller as demo usage data. The application does not currently obtain token counts directly from an LLM provider.

## Technology

| Area | Technology |
|---|---|
| API | Python, FastAPI |
| Validation | Pydantic |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Database migrations | Alembic |
| Database driver | Psycopg |
| Local infrastructure | Docker Compose |
| Billing | Stripe test mode |
| Background task trigger | FastAPI `BackgroundTasks` |
| Tests | Pytest, FastAPI TestClient |

## Architecture

```text
Client
  |
  | X-API-Key
  v
FastAPI application
  |
  +---- Tenant router
  |
  +---- Usage router
  |       |
  |       +---- API-key authentication / tenant ownership
  |       +---- Idempotency check
  |       +---- Quota service (402 / 429)
  |       +---- UsageEvent persistence
  |       +---- Background job record
  |                 |
  |                 v
  |           Cost processing
  |           (up to 3 attempts)
  |
  +---- Billing router -----> Stripe Checkout
  |
  +---- Webhook router <----- Stripe events
  |       +---- Signature verification
  |       +---- Duplicate-event protection
  |       +---- Subscription / plan synchronization
  |
  v
PostgreSQL
  plans, tenants, usage_events, subscriptions,
  stripe_webhook_events, background_jobs
```

### Usage request flow

1. The client sends a usage request with `X-API-Key`.
2. The API hashes the supplied key and identifies the tenant.
3. The API verifies that the request's `tenant_id` belongs to the authenticated tenant.
4. The idempotency key is checked. An identical retry returns the original usage event; conflicting reuse is rejected.
5. The quota service checks the current month's API calls and tokens.
6. A permitted usage event is stored.
7. A background-job record is created and FastAPI schedules the cost-processing function.
8. The job records its status, attempt count, and last error. It makes up to three attempts.

### Stripe flow

1. The client requests a Checkout Session for a paid plan.
2. The API creates the session through Stripe.
3. Stripe sends an event to `/webhooks/stripe`.
4. The webhook signature is verified and the Stripe event ID is checked to prevent duplicate processing.
5. Supported subscription events update the local subscription state. Checkout completion also synchronizes the tenant's plan.

## Database tables

| Table | Purpose |
|---|---|
| `plans` | Plan names, monthly API limits, token limits, and prices |
| `tenants` | Tenant details, assigned plan, and hashed API key |
| `usage_events` | Usage counts, tenant ownership, and idempotency key |
| `subscriptions` | Stripe customer/subscription identifiers and status |
| `stripe_webhook_events` | Stripe event IDs and processing state |
| `background_jobs` | Job type, payload, status, attempts, and last error |

## Cost calculation

Pricing values are configured in `app/config.py`. They are demonstration rates, not live model-provider prices.

| Usage | Configured rate |
|---|---:|
| Regular input tokens | 100,000 micro-USD per 1 million tokens |
| Cached input tokens | 25,000 micro-USD per 1 million tokens |
| Output tokens | 400,000 micro-USD per 1 million tokens |
| API call | 100 micro-USD per call |

Calculation rules:

- Regular input tokens = total input tokens minus cached input tokens.
- Cached input tokens use the cached-input rate.
- Output tokens use the output rate.
- Reasoning tokens are included in output tokens and are not charged a second time.
- API-call cost is added to token cost.
- The service returns micro-USD and USD values.

## Run locally

### Prerequisites

- Python 3.11 or compatible
- Docker Desktop with Docker Compose
- Stripe test-mode credentials only if testing Stripe Checkout/webhooks

### 1. Create and activate a virtual environment

```bash
python -m venv venv
```

Git Bash:

```bash
source venv/Scripts/activate
```

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 3. Configure environment variables

Copy `.env.example` to `.env` and update values if needed.

The example database URL is configured for the included local PostgreSQL setup. Add your own Stripe **test-mode** values for:

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`

Never commit `.env` or share secret values.

### 4. Start PostgreSQL

```bash
docker compose up -d
```

Wait for the database container to become healthy.

### 5. Apply database migrations

```bash
alembic upgrade head
```

Migrations manage the schema. The application no longer creates tables automatically at startup.

### 6. Seed the Free and Pro plans

```bash
python -m app.seed
```

### 7. Start the API

```bash
uvicorn app.main:app --reload
```

Open:

- API root: `http://127.0.0.1:8000/`
- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

### 8. Run tests

```bash
python -m pytest -v
```

The latest full test run reported during this development session was **35 passed**. Re-run the suite against the exact repository version before submission and retain the fresh terminal output as evidence.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | API health/message |
| `POST` | `/tenants/` | Create a tenant and return its API key |
| `POST` | `/usage/` | Record usage; requires `X-API-Key` |
| `GET` | `/usage/summary/{tenant_id}` | Current-month usage and cost; requires `X-API-Key` |
| `POST` | `/billing/checkout/{tenant_id}/{plan_id}` | Create a Stripe Checkout Session |
| `GET` | `/billing/success?session_id=...` | Checkout return endpoint |
| `GET` | `/billing/cancel` | Checkout cancellation return endpoint |
| `POST` | `/webhooks/stripe` | Receive signed Stripe webhook events |

See [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md) for request examples, headers, and status codes.

## Stripe test-mode flow

1. Add your Stripe test secret key to `.env`.
2. Start the API and PostgreSQL, and ensure the Free and Pro plans exist.
3. Create a tenant and retain the returned API key securely.
4. Call the checkout endpoint and complete the returned URL using Stripe test payment details.
5. In another terminal, run:

```bash
stripe listen --forward-to localhost:8000/webhooks/stripe
```

6. Copy the webhook signing secret printed by Stripe CLI into `STRIPE_WEBHOOK_SECRET` in `.env`, then restart the API.
7. Complete a test checkout and inspect the webhook result and local subscription/tenant plan state.

Stripe test mode does not process real payments. Never put live Stripe secrets in this repository.

## Known limitations and production considerations

This is a capstone/local-development implementation, not a production billing platform.

- **Background execution reliability:** jobs are persisted in PostgreSQL, but execution is triggered by FastAPI `BackgroundTasks` in the API process. There is no separate continuously running worker or automatic recovery/polling of pending jobs after a process crash/restart.
- **Retry and alerting:** the current function makes up to three attempts during one invocation and logs permanent failures. It does not send an external alert (email, Slack, etc.).
- **Tenant authentication scope:** API-key authentication and tenant ownership checks protect the usage recording and usage-summary endpoints. The remaining tenant/billing routes need a complete authorization review before production use.
- **API-key lifecycle:** keys are returned at tenant creation and stored hashed, but key rotation/revocation and rate limiting are not implemented.
- **Usage source:** usage/token counts are client-supplied demo data; no LLM provider integration independently verifies them.
- **Cost persistence:** calculated cost is stored in the background-job payload; there is no separate immutable invoice/ledger table.
- **Quota retry timing:** the current `Retry-After` value is a fixed one-hour hint, not a calculated quota-reset timestamp.
- **Operations:** deployment, monitoring, alert delivery, concurrency/race-condition hardening, and production secret management remain future work.

These limitations should be addressed before production use. Do not describe the project as production-ready.

## Suggested repository name

`flyrank-capstone-metering-billing`

Keep `.env`, virtual environments, Python caches, and test caches out of Git.
