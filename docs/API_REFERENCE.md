# API Reference

Local base URL: `http://127.0.0.1:8000`

Use `http://127.0.0.1:8000/docs` to try endpoints through Swagger UI.

## `GET /`

Returns a message confirming that the API is running.

## `POST /tenants/`

Creates a tenant and generates an API key.

Example request:

```json
{
  "name": "Acme AI",
  "email": "ops@example.com",
  "plan_id": 1
}
```

The response includes the tenant details and the newly generated raw `api_key`. Store this key securely when it is returned; the database stores its SHA-256 hash, not the raw key.

Validation and behavior:
- `name` must not be empty.
- `email` must be valid.
- `plan_id` must refer to an existing plan.
- An existing email returns `409 Conflict`.

## `POST /usage/`

Records a usage event. Requires the header:

```http
X-API-Key: <tenant-api-key>
```

Example request:

```json
{
  "tenant_id": 1,
  "idempotency_key": "usage-request-001",
  "event_type": "llm_request",
  "api_calls": 1,
  "input_tokens": 1200,
  "output_tokens": 400,
  "cached_input_tokens": 300,
  "reasoning_tokens": 100
}
```

Validation and behavior:
- Count fields cannot be negative.
- Cached input tokens cannot exceed total input tokens.
- The API key identifies the tenant.
- The submitted `tenant_id` must match the authenticated tenant.
- If the idempotency key and all usage fields match an existing event for the same tenant, the existing event is returned.
- Reusing the key with different data is rejected.
- A key belonging to another tenant cannot be used to access that tenant's event.
- The quota service checks current-month usage before a new event is stored.
- A disallowed inactive/lapsed paid subscription returns `402`.
- An API-call or token quota breach returns `429` and includes `Retry-After: 3600`.
- A successful new usage event creates a background job for cost processing.

## `GET /usage/summary/{tenant_id}`

Requires `X-API-Key`.

Returns current-month totals for the authenticated tenant:
- API calls
- Input tokens
- Output tokens
- Cached input tokens
- Reasoning tokens
- Total tokens
- Calculated cost in micro-USD and USD

The requested `tenant_id` must match the authenticated tenant.

## Background usage-cost processing

A successful new usage request creates a `background_jobs` record with job type `usage_cost`. FastAPI schedules processing after the response.

The job stores:
- Job type and JSON payload
- Status (`pending`, `processing`, `completed`, or `failed`)
- Attempt count and maximum attempts
- Last error, if any

The current processor attempts a job up to three times and logs a permanent failure. The calculated cost is written into the job payload.

Operational limitation: this is triggered by FastAPI `BackgroundTasks` in the API process. There is no independent worker polling pending jobs after an application restart, and permanent failures do not trigger an external notification.

## `POST /billing/checkout/{tenant_id}/{plan_id}`

Creates a Stripe Checkout Session in subscription mode for a paid plan.

The current route accepts tenant and plan identifiers in the path. Review authorization before exposing this endpoint publicly.

Successful response contains `checkout_url` and `session_id`.

## `GET /billing/success?session_id=...`

Returns a checkout success message and session ID. It does not independently verify payment; subscription state must be confirmed from the signed Stripe webhook.

## `GET /billing/cancel`

Returns a checkout-cancelled message.

## `POST /webhooks/stripe`

Receives Stripe webhook events. The request must include the `Stripe-Signature` header.

Handled events:
- `checkout.session.completed`
- `customer.subscription.updated`
- `customer.subscription.deleted`

Behavior:
- Verifies the event using Stripe's webhook signature verification.
- Returns `400` for an invalid payload or signature.
- Stores Stripe event IDs to prevent duplicate processing.
- Creates/updates the local subscription record.
- Checkout completion synchronizes the tenant's plan to the purchased plan.

## Status codes

| Code | Meaning |
|---|---|
| `200` | Request completed |
| `400` | Invalid webhook or invalid checkout request |
| `401` | Missing or invalid tenant API key on usage endpoints |
| `402` | Paid subscription is inactive/lapsed and the requested plan is not permitted |
| `403` | Authenticated tenant attempts to access another tenant's usage |
| `404` | Tenant or plan not found |
| `409` | Duplicate email or conflicting idempotency-key reuse |
| `422` | Request validation failed |
| `429` | Monthly API-call or token quota exceeded; includes `Retry-After` |
| `500` | Stripe checkout or webhook processing failed |
