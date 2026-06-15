"""
SLA Alert model — one row per alert fired for an order.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AlertType(str, enum.Enum):
    SLA_BREACH      = "sla_breach"
    SLA_AT_RISK     = "sla_at_risk"
    QC_FAIL_RISK    = "qc_fail_risk"
    STAGE_STUCK     = "stage_stuck"
    LOW_STOCK       = "low_stock"


class AlertChannel(str, enum.Enum):
    EMAIL    = "email"
    WHATSAPP = "whatsapp"
    INTERNAL = "internal"   # dashboard only


class SLAAlert(Base):
    __tablename__ = "sla_alerts"

    id:          Mapped[int]       = mapped_column(Integer, primary_key=True, index=True)
    order_id:    Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=True, index=True
    )
    alert_type:  Mapped[AlertType]  = mapped_column(Enum(AlertType))
    channel:     Mapped[AlertChannel] = mapped_column(Enum(AlertChannel), default=AlertChannel.INTERNAL)
    message:     Mapped[str]        = mapped_column(Text)
    sent:        Mapped[bool]       = mapped_column(Boolean, default=False)
    read:        Mapped[bool]       = mapped_column(Boolean, default=False)
    created_at:  Mapped[datetime]   = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at:     Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    order: Mapped["models.order.Order | None"] = relationship(  # type: ignore[name-defined]
        back_populates="alerts"
    )