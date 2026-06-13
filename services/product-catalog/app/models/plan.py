import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Plan(Base):
    """
    One row per plan version. Append-only — rows are never updated after creation.

    The combination of (name, version) is unique, making "Pro v1" and "Pro v2"
    distinct, permanent, auditable records.
    """

    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_custom_pricing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    pricing: Mapped[list["PlanPricing"]] = relationship(back_populates="plan", lazy="selectin")
    entitlements: Mapped[list["PlanEntitlement"]] = relationship(back_populates="plan", lazy="selectin")


class PlanPricing(Base):
    """
    One row per plan version per currency.
    Amount is stored in minor units (kobo for NGN, cents for USD).

    Enterprise plans have no pricing rows — is_custom_pricing handles that case.
    """

    __tablename__ = "plan_pricing"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False
    )
    plan_version: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    plan: Mapped["Plan"] = relationship(back_populates="pricing")


class PlanEntitlement(Base):
    """
    One row per plan version per feature key.
    Value is a JSONB discriminated union: {"type": "boolean"} or {"type": "numeric"}.
    limit: -1 on numeric features means unlimited.
    """

    __tablename__ = "plan_entitlements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False
    )
    plan_version: Mapped[int] = mapped_column(Integer, nullable=False)
    feature_key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    plan: Mapped["Plan"] = relationship(back_populates="entitlements")


class ProductCatalogOutbox(Base):
    """
    Transactional outbox for Kafka event publishing.
    Written in the same transaction as plan writes — never separately.
    The outbox worker polls unpublished rows and publishes them to Kafka.
    """

    __tablename__ = "product_catalog_outbox"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    publish_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
