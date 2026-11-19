
from pydantic import BaseModel, EmailStr, Field, model_validator


class TenantCreate(BaseModel):
    name: str = Field(min_length=1)
    email: EmailStr
    plan_id: int = Field(gt=0)


class UsageEventCreate(BaseModel):
    tenant_id: int = Field(gt=0)
    idempotency_key: str = Field(min_length=1)
    event_type: str = Field(min_length=1)

    api_calls: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_token_counts(self):
        if self.cached_input_tokens > self.input_tokens:
            raise ValueError(
                "Cached input tokens cannot exceed input tokens"
            )

        if self.reasoning_tokens > self.output_tokens:
            raise ValueError(
                "Reasoning tokens cannot exceed output tokens"
            )

        return self
