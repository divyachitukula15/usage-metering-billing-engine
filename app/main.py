from fastapi import FastAPI
#from app.database import Base, engine
#from app import models
from app.routers import tenants
from app.routers import usage
from app.routers import billing
from app.routers import webhooks

#Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Usage Metering & Billing Engine",
    description="Track customer usage, enforce quotas, and calculate costs.",
    version="0.1.0",
)
app.include_router(tenants.router)
app.include_router(usage.router)
app.include_router(billing.router)
app.include_router(webhooks.router)

@app.get("/")
def home():
    return {
        "message": "Usage Metering & Billing Engine is running"
    }






#with engine.connect() as connection:
    print("PostgreSQL connected successfully!")