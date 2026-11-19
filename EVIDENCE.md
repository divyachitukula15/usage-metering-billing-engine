# Evidence — Usage Metering & Billing Engine

This document maps the capstone requirements to the implementation and evidence captured during development.

**Security:** Never commit `.env`, Stripe secrets, database passwords, or raw tenant API keys.

## 1. Idempotent usage metering

**Requirement:** Sending the same billable request twice with one idempotency key must create exactly one usage event.

**Implementation:** `POST /usage/` checks the idempotency key. An identical retry returns the existing event; conflicting reuse is rejected.

**Evidence:**
- `proofs/idempotency.png` — repeated request returns the original usage event.

## 2. Quota enforcement and response codes

**Implementation:**
- `402 Payment Required` for a disallowed inactive/lapsed paid subscription.
- `429 Too Many Requests` for monthly API-call or token quota exhaustion.
- Quota responses include `Retry-After: 3600`.

**Evidence:**
- `proofs/quota-enforcement-429.png` — quota exceeded response.
- `proofs/payment-required-402.png` — canceled subscription response.

## 3. Monthly usage and cost calculation

**Requirement:** Monthly usage must roll up into a cost figure per tenant.

**Implementation:** `GET /usage/summary/{tenant_id}` returns monthly API calls, token totals, and calculated cost. It requires the tenant's `X-API-Key`.

**Verified response:**
- Tenant ID: 6
- Month: November 2026
- API calls: 1
- Input tokens: 100
- Output tokens: 50
- Total tokens: 150
- Token cost: 30 micro USD
- API cost: 100 micro USD
- Total cost: 130 micro USD (`$0.00013`)

**Evidence:**
- `proofs/usage-cost-summary.png` — sanitized usage summary response.

## 4. Cached-input and reasoning-token pricing

**Requirement:** Cached input uses its lower rate. Reasoning tokens are not counted twice. Pricing values are configured in code.

**Implementation:** Pricing is configured in `app/config.py`; `app/services/cost.py` calculates regular input, cached input, output, and API-call costs. Reasoning tokens are included in output tokens.

**Test result:** `4 passed` from `tests/test_cost.py`.

**Evidence:**
- `proofs/pricing-tests.png` — cost calculation test results.

## 5. Stripe Checkout in test mode

**Requirement:** A customer can start a Stripe test Checkout session.

**Implementation:** `POST /billing/checkout/{tenant_id}/{plan_id}` creates a Stripe Checkout Session. Automated checkout tests use mocked Stripe calls.

**Verification:**
- Billing test file: `7 passed`.
- Created a Stripe Checkout Session through the API.
- Opened the Checkout URL and completed a test-mode payment successfully.
- No real payment was made.

**Evidence:**
- `proofs/billing-tests.png` — automated billing tests.
- `proofs/stripe-checkout-session.png` — successful Stripe test Checkout.

## 6. Webhook signature verification and duplicate-event handling

**Requirement:** Invalid signatures are rejected and duplicate Stripe events are not processed twice.

**Implementation:** `/webhooks/stripe` verifies `Stripe-Signature`, stores Stripe event IDs, and handles supported checkout/subscription events.

**Verification:**
- Webhook test file: `7 passed`.
- Stripe CLI listener forwarded events to the local FastAPI endpoint.
- `stripe trigger checkout.session.completed` returned HTTP 200.
- After completing the actual Stripe test Checkout, the webhook endpoint also returned HTTP 200.

**Evidence:**
- `proofs/webhook-tests.png` — automated webhook tests.
- `proofs/stripe-webhook-delivery.png` — Stripe CLI test event delivery.
- `proofs/stripe-checkout-webhook-200.png` — webhook delivery after successful Checkout.

## 7. Tenant authentication and isolation

**Implementation:**
- Tenant creation generates an API key and returns the raw key at creation.
- The database stores its SHA-256 hash.
- Usage recording and usage summaries require `X-API-Key`.
- The authenticated tenant must match the tenant ID in the request.

**Evidence:**
- `proofs/tenant-isolation-403.png` — cross-tenant access rejected.
- `proofs/unauthorized-401.png` — missing API key rejected.

**Scope limitation:** API-key authentication is applied to usage endpoints. Tenant-creation and billing routes need a broader authorization review before production exposure.

## 8. Database persistence and migrations

**Implementation:** PostgreSQL stores plans, tenants, usage events, subscriptions, Stripe webhook events, and background jobs. Alembic manages schema changes. The existing schema was registered as a baseline; a later migration creates `background_jobs`.

**Checks reported:**
- `alembic check` → `No new upgrade operations detected`.
- `alembic upgrade head` successfully applied the background-jobs migration.
- Current revision: `704deda52628 (head)`.
- Migration history contains the initial schema and background-jobs migration.

**Evidence:**
- `proofs/alembic-current.png`
- `proofs/alembic-history.png`

## 9. Background processing, retries, and failure logging

**Implementation:** A successful new usage event creates a `background_jobs` record. FastAPI `BackgroundTasks` invokes the usage-cost processor. The processor attempts a job up to three times, stores status/attempt/error details, and logs permanent failure.

**Relevant tests:**
- `test_background_job_completes`
- `test_background_job_retries_and_fails`

**Test result:** `2 passed, 1 warning`.

**Evidence:**
- `proofs/background-jobs-tests.png`

**Important limitation:** There is no separate worker/poller to recover pending jobs after an API process crash/restart. Retries occur within one invocation. Permanent failures are logged, but no external alert is sent.

## 10. Automated test suite

**Reported development results:**

| Test file | Result |
|---|---:|
| Full test suite | 35 passed |
| `tests/test_cost.py` | 4 passed |
| `tests/test_billing.py` | 7 passed |
| `tests/test_webhooks.py` | 7 passed |
| `tests/test_background_jobs.py` | 2 passed, 1 warning |

**Evidence:**
- `proofs/test-results.png`
- `proofs/pricing-tests.png`
- `proofs/billing-tests.png`
- `proofs/webhook-tests.png`
- `proofs/background-jobs-tests.png`

Run the full suite again before submission:

```bash
python -m pytest -v
```

## 11. API documentation

**Evidence:**
- `proofs/api-documentation.png` — Swagger UI documentation.

## 12. Evidence screenshot index

All evidence screenshots should be stored in the project's `proofs/` directory.

| Screenshot | What it demonstrates |
|---|---|
| `test-results.png` | Full test suite — 35 passed |
| `api-documentation.png` | Swagger API documentation |
| `idempotency.png` | Duplicate request handling |
| `quota-enforcement-429.png` | API quota enforcement |
| `payment-required-402.png` | Inactive subscription enforcement |
| `tenant-isolation-403.png` | Tenant isolation |
| `unauthorized-401.png` | Missing API key rejection |
| `alembic-current.png` | Current database migration |
| `alembic-history.png` | Migration history |
| `background-jobs-tests.png` | Background job tests |
| `usage-cost-summary.png` | Monthly usage and cost response |
| `pricing-tests.png` | Cost calculation tests |
| `billing-tests.png` | Automated billing tests |
| `webhook-tests.png` | Automated webhook tests |
| `stripe-checkout-session.png` | Successful Stripe test Checkout |
| `stripe-webhook-delivery.png` | Stripe CLI webhook test delivery |
| `stripe-checkout-webhook-200.png` | Webhook response after Checkout |

## 13. Remaining production considerations

- Complete authorization review for tenant creation and billing routes.
- Add API-key rotation/revocation and rate limiting.
- Consider a dedicated worker/queue with restart recovery and backoff.
- Add external failure notifications.
- Persist finalized costs in a dedicated billing ledger/invoice model.
- Derive `Retry-After` from the actual quota reset time rather than a fixed one-hour value.
- Add production deployment, monitoring, and secret-management controls.

Do not mark these production-hardening items complete until implemented and tested.