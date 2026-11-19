# Architecture

## Component view

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
  |       +---- API-key authentication
  |       +---- Tenant ownership validation
  |       +---- Idempotency validation
  |       +---- Quota service (402 / 429)
  |       +---- UsageEvent persistence
  |       +---- BackgroundJob record
  |                 |
  |                 v
  |            FastAPI BackgroundTasks
  |                 |
  |                 v
  |            Cost calculation
  |            (up to 3 attempts)
  |
  +---- Billing router ------> Stripe Checkout
  |
  +---- Webhook router <----- Stripe events
          |
          +---- Signature verification
          +---- Duplicate-event check
          +---- Subscription and tenant-plan update
  |
  v
PostgreSQL
  plans, tenants, usage_events, subscriptions,
  stripe_webhook_events, background_jobs
```

## Usage request flow

1. FastAPI validates the request body using the Pydantic schema.
2. The usage router reads the `X-API-Key` header, hashes the key, and finds the tenant.
3. The submitted tenant ID is checked against the authenticated tenant.
4. The idempotency key is checked. An identical retry returns the existing event; conflicting reuse is rejected.
5. The quota service checks monthly API-call and token usage.
6. An inactive/lapsed paid subscription that no longer permits usage returns `402`; a quota limit breach returns `429`.
7. An allowed usage event is committed to PostgreSQL.
8. A `background_jobs` row is created for cost processing.
9. FastAPI `BackgroundTasks` invokes the processor after the response. The processor records status and attempts, and logs a permanent failure after up to three attempts.

## Cost calculation flow

1. Calculate regular input tokens by subtracting cached input tokens from total input tokens.
2. Apply the regular input rate to regular input tokens.
3. Apply the cached input rate to cached input tokens.
4. Apply the output rate to output tokens.
5. Do not add reasoning tokens again because they are already included in output tokens.
6. Add the API-call charge.
7. Return the total in micro-USD and USD.
8. The background processor stores the calculated result in the job payload.

## Stripe event flow

1. The billing router creates a Stripe Checkout Session.
2. Stripe sends a webhook event to `/webhooks/stripe`.
3. The webhook handler verifies the signature.
4. The handler checks whether the event ID has already been stored.
5. Supported events create/update a local subscription record.
6. Checkout completion synchronizes the tenant's plan with the purchased plan.

## Database tables

| Table | Main responsibility |
|---|---|
| `plans` | Plan limits and monthly price |
| `tenants` | Tenant details, assigned plan, hashed API key |
| `usage_events` | Usage counts and idempotency key |
| `subscriptions` | Stripe subscription details and status |
| `stripe_webhook_events` | Stripe event IDs and processing status |
| `background_jobs` | Background task payload, status, attempts, and error |

## Database schema management

Alembic manages schema changes. The existing database was registered as a baseline migration, and the `background_jobs` table was added in a subsequent migration. The application does not call `Base.metadata.create_all()` at startup.

Useful commands:

```bash
alembic current
alembic check
alembic upgrade head
```

## Current design limitations

- Background execution is triggered by FastAPI `BackgroundTasks` in the API process; there is no independent worker polling/recovering pending jobs after a process restart.
- Retries happen within one processor invocation, not through a scheduled retry queue.
- Permanent failure is logged but does not send an external alert.
- API-key authentication is currently applied to usage endpoints; tenant and billing routes require a broader authorization review.
- API-key rotation/revocation and request rate limiting are not implemented.
- Usage values are supplied by the caller for demonstration; provider-side usage is not independently verified.
- Calculated costs are stored in the job payload rather than a dedicated invoice/ledger table.
- The fixed `Retry-After` value is a one-hour hint, not a computed quota-reset time.
