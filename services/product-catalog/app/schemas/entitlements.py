from typing import Annotated, Literal

from pydantic import BaseModel, Field


class BooleanEntitlementValue(BaseModel):
    type: Literal["boolean"]
    enabled: bool


class NumericEntitlementValue(BaseModel):
    type: Literal["numeric"]
    limit: Annotated[int, Field(ge=-1)]


# Discriminated union — Pydantic picks the right model from the "type" field.
# This means validation is strict: a numeric value without "limit" is rejected at
# the schema layer before it ever reaches the service or database.
EntitlementValue = Annotated[
    BooleanEntitlementValue | NumericEntitlementValue,
    Field(discriminator="type"),
]
