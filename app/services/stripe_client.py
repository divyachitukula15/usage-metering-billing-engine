
import stripe

from app.config import STRIPE_SECRET_KEY

if not STRIPE_SECRET_KEY:
    raise RuntimeError("STRIPE_SECRET_KEY is missing from .env")

stripe.api_key = STRIPE_SECRET_KEY
