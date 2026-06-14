from fastapi import status

from app.core.response import APIError


class PlanNotFoundError(APIError):
    def __init__(self, family_id: str, version: int | None = None) -> None:
        detail = f"Plan {family_id}"
        if version is not None:
            detail += f" version {version}"
        super().__init__(
            f"{detail} not found",
            status_code=status.HTTP_404_NOT_FOUND,
            code="plan_not_found",
        )


class PricingNotFoundError(APIError):
    def __init__(self, family_id: str, version: int, currency: str) -> None:
        super().__init__(
            f"No {currency} pricing found for plan {family_id} version {version}",
            status_code=status.HTTP_404_NOT_FOUND,
            code="pricing_not_found",
        )


class EntitlementNotFoundError(APIError):
    def __init__(self, family_id: str, version: int, feature_key: str) -> None:
        super().__init__(
            f"Feature '{feature_key}' not found on plan {family_id} version {version}",
            status_code=status.HTTP_404_NOT_FOUND,
            code="entitlement_not_found",
        )


class PlanVersionAlreadyInactiveError(APIError):
    def __init__(self, family_id: str, version: int) -> None:
        super().__init__(
            f"Plan {family_id} version {version} is already inactive",
            status_code=status.HTTP_409_CONFLICT,
            code="plan_version_already_inactive",
        )


class DuplicatePlanNameError(APIError):
    def __init__(self, name: str) -> None:
        super().__init__(
            f"A plan named '{name}' already exists",
            status_code=status.HTTP_409_CONFLICT,
            code="duplicate_plan_name",
        )


class UnauthorizedError(APIError):
    def __init__(self) -> None:
        super().__init__(
            "Missing or invalid admin token",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="unauthorized",
        )
