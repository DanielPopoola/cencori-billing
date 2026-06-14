import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.entitlements import EntitlementValue

_VALID_CURRENCIES = {
    "NGN",
    "USD",
    "EUR",
    "GBP",
    "JPY",
    "CAD",
    "AUD",
    "CHF",
    "CNY",
    "INR",
}


class PricingEntry(BaseModel):
    amount: int = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        upper = value.upper()
        if upper not in _VALID_CURRENCIES:
            raise ValueError(f"'{value}' is not a supported ISO 4217 currency code")
        return upper


class EntitlementEntry(BaseModel):
    feature_key: str = Field(min_length=1, max_length=100)
    value: EntitlementValue


class CreatePlanRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    pricing: list[PricingEntry] = Field(min_length=1)
    entitlements: list[EntitlementEntry] = Field(min_length=1)


class CreatePlanVersionRequest(BaseModel):
    pricing: list[PricingEntry] = Field(min_length=1)
    entitlements: list[EntitlementEntry] = Field(min_length=1)


class PricingResponse(BaseModel):
    family_id: uuid.UUID
    plan_name: str
    plan_version: int
    currency: str
    monthly_amount: int
    annual_amount: int
    annual_discount_rate: float
    billing_cadences: list[str] = ["monthly", "annual"]


class CustomPricingResponse(BaseModel):
    family_id: uuid.UUID
    plan_name: str
    plan_version: int
    is_custom_pricing: bool = True
    message: str = "Enterprise pricing is negotiated. Contact sales@cencori.com."


class EntitlementResponse(BaseModel):
    family_id: uuid.UUID
    plan_version: int
    feature_key: str
    value: EntitlementValue


class EntitlementsResponse(BaseModel):
    family_id: uuid.UUID
    plan_version: int
    entitlements: list[EntitlementEntry]


class PlanVersionResponse(BaseModel):
    id: uuid.UUID
    name: str
    version: int
    is_active: bool
    is_custom_pricing: bool
    pricing: list[PricingEntry]
    entitlements: list[EntitlementEntry]
    created_at: datetime

    model_config = {"from_attributes": True}


class DeactivatedPlanResponse(BaseModel):
    id: uuid.UUID
    name: str
    version: int
    is_active: bool
    deactivated_at: datetime
