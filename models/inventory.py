"""
Inventory models for lenses and coatings kept in-house.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LensInventory(Base):
    """Represents a single lens SKU held in-house."""
    __tablename__ = "lens_inventory"

    id:         Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sku:        Mapped[str] = mapped_column(String(60), unique=True, index=True)
    lens_type:  Mapped[str] = mapped_column(String(40))    # Single Vision / Progressive …
    lens_index: Mapped[str] = mapped_column(String(10))    # 1.50 / 1.56 …
    coating:    Mapped[str] = mapped_column(String(60), default="Clear")

    # Power range this SKU covers (null = cut-to-order)
    sph_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    sph_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    cyl_max: Mapped[float | None] = mapped_column(Float, nullable=True)

    qty_in_stock: Mapped[int] = mapped_column(Integer, default=0)
    min_stock:    Mapped[int] = mapped_column(Integer, default=20)

    supplier_name: Mapped[str | None]     = mapped_column(String(120), nullable=True)
    supplier_eta_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_active: Mapped[bool]     = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class CoatingInventory(Base):
    """Coatings / films stocked in-house."""
    __tablename__ = "coating_inventory"

    id:           Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    coating_name: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    qty_in_stock: Mapped[int] = mapped_column(Integer, default=0)
    min_stock:    Mapped[int] = mapped_column(Integer, default=50)
    unit:         Mapped[str] = mapped_column(String(20), default="units")
    supplier_eta: Mapped[str | None] = mapped_column(String(80), nullable=True)
    updated_at:   Mapped[datetime]   = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )