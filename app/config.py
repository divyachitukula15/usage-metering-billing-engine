
import os
from dotenv import load_dotenv

load_dotenv()

# Demo pricing in micro-USD per 1 million tokens
INPUT_TOKEN_PRICE = 100_000
CACHED_INPUT_TOKEN_PRICE = 25_000
OUTPUT_TOKEN_PRICE = 400_000

# API call cost: $0.0001
API_CALL_PRICE = 100

MICRO_USD = 1_000_000
TOKENS_PER_MILLION = 1_000_000

# Stripe configuration
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
