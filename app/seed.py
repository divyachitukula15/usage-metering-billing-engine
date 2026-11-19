from app.database import SessionLocal
from app.models import Plan

db = SessionLocal()

plans = [
    Plan(
        name="Free",
        monthly_api_limit=1000,
        monthly_token_limit=100000,
        monthly_price=0
    ),
    Plan(
        name="Pro",
        monthly_api_limit=10000,
        monthly_token_limit=1000000,
        monthly_price=999
    ),
    Plan(
    name="Test",
    monthly_api_limit=2,
    monthly_token_limit=1000,
    monthly_price=0
    )
]

for plan in plans:
    existing = db.query(Plan).filter(Plan.name == plan.name).first()

    if existing:
        existing.monthly_api_limit = plan.monthly_api_limit
        existing.monthly_token_limit = plan.monthly_token_limit
        existing.monthly_price = plan.monthly_price
    else:
        db.add(plan)

db.commit()

db.close()

print("Plans added successfully!")