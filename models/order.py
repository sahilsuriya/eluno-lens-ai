"""
Order model — tracks the full lifecycle of a single eyewear order.
Each status transition is stored in OrderStatusLog so we have a complete audit trail.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Enums ────────────────────────────────────────────────────────────────────

class OrderStage(str, enum.Enum):
    PLACED           = "Placed"
    INVENTORY_CHECK  = "Inventory Check"
    LAB_CUTTING      = "Lab Cutting"
    EDGING           = "Edging"
    COATING          = "Coating"
    QC_CHECK         = "QC Check"
    DISPATCH         = "Dispatch"
    DELIVERED        = "Delivered"


class LensType(str, enum.Enum):
    SINGLE_VISION = "Single Vision"
    PROGRESSIVE   = "Progressive"
    BIFOCAL       = "Bifocal"
    OFFICE        = "Office"


class LensIndex(str, enum.Enum):
    I150 = "1.50"
    I156 = "1.56"
    I160 = "1.60"
    I167 = "1.67"
    I174 = "1.74"


class Coating(str, enum.Enum):
    AR            = "Anti-Reflective"
    BLUE_CUT      = "Blue Cut"
    PHOTOCHROMIC  = "Photochromic"
    POLARISED     = "Polarised"
    PLAIN         = "Plain"


class AIRisk(str, enum.Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


class InvStatus(str, enum.Enum):
    IN_HOUSE = "in-house"
    SOURCED  = "sourced"


# ── Order ────────────────────────────────────────────────────────────────────

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Customer
    customer_name:  Mapped[str] = mapped_column(String(120))
    customer_phone: Mapped[str] = mapped_column(String(20))
    store_location: Mapped[str] = mapped_column(String(60))

    # Frame
    frame_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)

    # Lens specification
    lens_type:  Mapped[LensType]  = mapped_column(Enum(LensType))
    lens_index: Mapped[LensIndex] = mapped_column(Enum(LensIndex))
    coating:    Mapped[Coating]   = mapped_column(Enum(Coating))
    tint:       Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Prescription
    r_sph: Mapped[str | None] = mapped_column(String(10), nullable=True)
    r_cyl: Mapped[str | None] = mapped_column(String(10), nullable=True)
    r_axis: Mapped[str | None] = mapped_column(String(10), nullable=True)
    l_sph: Mapped[str | None] = mapped_column(String(10), nullable=True)
    l_cyl: Mapped[str | None] = mapped_column(String(10), nullable=True)
    l_axis: Mapped[str | None] = mapped_column(String(10), nullable=True)
    pd: Mapped[str | None] = mapped_column(String(10), nullable=True)  # pupillary distance

    # Lifecycle
    stage:       Mapped[OrderStage] = mapped_column(Enum(OrderStage), default=OrderStage.PLACED)
    sla_days:    Mapped[int]        = mapped_column(Integer)            # working days
    inv_status:  Mapped[InvStatus]  = mapped_column(Enum(InvStatus), default=InvStatus.IN_HOUSE)

    # AI fields
    ai_risk:          Mapped[AIRisk | None] = mapped_column(Enum(AIRisk), nullable=True)
    ai_predicted_tat: Mapped[int | None]    = mapped_column(Integer, nullable=True)   # days
    ai_breach_prob:   Mapped[float | None]  = mapped_column(nullable=True)            # 0-1

    # Timestamps
    placed_at:    Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at:   Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    # Relations
    status_logs: Mapped[list[OrderStatusLog]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderStatusLog.changed_at"
    )
    alerts: Mapped[list["models.alert.SLAAlert"]] = relationship(  # type: ignore[name-defined]
        back_populates="order", cascade="all, delete-orphan"
    )


# ── Status log ───────────────────────────────────────────────────────────────

class OrderStatusLog(Base):
    __tablename__ = "order_status_logs"

    id:         Mapped[int]       = mapped_column(Integer, primary_key=True, index=True)
    order_id:   Mapped[int]       = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    from_stage: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_stage:   Mapped[str]       = mapped_column(String(40))
    reason:     Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
    changed_at: Mapped[datetime]  = mapped_column(DateTime(timezone=True), default=utcnow)

    order: Mapped[Order] = relationship(back_populates="status_logs")