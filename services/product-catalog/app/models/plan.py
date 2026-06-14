import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


class PlanFamily(Base):
    __tablename__ = "plan_families"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    is_custom_pricing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    versions: Mapped[list["Plan"]] = relationship(back_populates="family", lazy="selectin")
    pricing: Mapped[list["PlanPricing"]] = relationship(back_populates="family", lazy="selectin")
    entitlements: Mapped[list["PlanEntitlement"]] = relationship(
        back_populates="family", lazy="selectin"
    )


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plan_families.id"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    family: Mapped["PlanFamily"] = relationship(back_populates="versions", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("family_id", "version", name="uq_plans_family_version"),
        Index("idx_plans_active", "is_active", postgresql_where=text("is_active = true")),
    )


class PlanPricing(Base):
    __tablename__ = "plan_pricing"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plan_families.id"), nullable=False
    )
    plan_version: Mapped[int] = mapped_column(Integer, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    family: Mapped["PlanFamily"] = relationship(back_populates="pricing", lazy="selectin")

    __table_args__ = (
        UniqueConstraint(
            "family_id", "plan_version", "currency", name="uq_plan_pricing_plan_version_currency"
        ),
        Index("idx_plan_pricing_plan", "family_id", "plan_version"),
    )


class PlanEntitlement(Base):
    __tablename__ = "plan_entitlements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plan_families.id"), nullable=False
    )
    plan_version: Mapped[int] = mapped_column(Integer, nullable=False)
    feature_key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    family: Mapped["PlanFamily"] = relationship(back_populates="entitlements", lazy="selectin")

    __table_args__ = (
        UniqueConstraint(
            "family_id", "plan_version", "feature_key", name="uq_plan_entitlements_feature"
        ),
        Index("idx_plan_entitlements_plan", "family_id", "plan_version"),
        Index("idx_plan_entitlements_value", "value", postgresql_using="gin"),
    )


class ProductCatalogOutbox(Base):
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

    __table_args__ = (
        Index("idx_outbox_unpublished", "created_at", postgresql_where=text("published = false")),
    )
