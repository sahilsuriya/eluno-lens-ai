from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from models.order import AIRisk, Coating, InvStatus, LensIndex, LensType, OrderStage


# ── Prescription sub-schema ───────────────────────────────────────────────────

class Prescription(BaseModel):
    r_sph:  Optional[str] = None
    r_cyl:  Optional[str] = None
    r_axis: Optional[str] = None
    l_sph:  Optional[str] = None
    l_cyl:  Optional[str] = None
    l_axis: Optional[str] = None
    pd:     Optional[str] = None


# ── Status log sub-schema ─────────────────────────────────────────────────────

class StatusLogOut(BaseModel):
    id:         int
    from_stage: Optional[str]
    to_stage:   str
    reason:     Optional[str]
    changed_by: Optional[str]
    changed_at: datetime

    model_config = {"from_attributes": True}


# ── Order schemas ─────────────────────────────────────────────────────────────

class OrderCreate(BaseModel):
    customer_name:   str  = Field(..., min_length=1, max_length=120)
    customer_phone:  str  = Field(..., max_length=20)
    store_location:  str  = Field(..., max_length=60)
    frame_reference: Optional[str] = None

    lens_type:  LensType
    lens_index: LensIndex
    coating:    Coating
    tint:       Optional[str] = None

    # Prescription fields (flat — easier for frontend form)
    r_sph:  Optional[str] = None
    r_cyl:  Optional[str] = None
    r_axis: Optional[str] = None
    l_sph:  Optional[str] = None
    l_cyl:  Optional[str] = None
    l_axis: Optional[str] = None
    pd:     Optional[str] = None


class OrderUpdate(BaseModel):
    """Partial update — only provided fields are changed."""
    customer_name:   Optional[str] = None
    customer_phone:  Optional[str] = None
    store_location:  Optional[str] = None
    frame_reference: Optional[str] = None
    lens_type:       Optional[LensType]  = None
    lens_index:      Optional[LensIndex] = None
    coating:         Optional[Coating]   = None
    tint:            Optional[str] = None
    r_sph:  Optional[str] = None
    r_cyl:  Optional[str] = None
    r_axis: Optional[str] = None
    l_sph:  Optional[str] = None
    l_cyl:  Optional[str] = None
    l_axis: Optional[str] = None
    pd:     Optional[str] = None


class StageUpdateRequest(BaseModel):
    stage:         OrderStage
    reason:        Optional[str] = Field(None, max_length=500)
    changed_by:    Optional[str] = None
    alert_channel: Optional[str] = None   # "email" | "whatsapp" | None


class OrderOut(BaseModel):
    id:              int
    customer_name:   str
    customer_phone:  str
    store_location:  str
    frame_reference: Optional[str]

    lens_type:  LensType
    lens_index: LensIndex
    coating:    Coating
    tint:       Optional[str]

    r_sph:  Optional[str]
    r_cyl:  Optional[str]
    r_axis: Optional[str]
    l_sph:  Optional[str]
    l_cyl:  Optional[str]
    l_axis: Optional[str]
    pd:     Optional[str]

    stage:            OrderStage
    sla_days:         int
    inv_status:       InvStatus
    ai_risk:          Optional[AIRisk]
    ai_predicted_tat: Optional[int]
    ai_breach_prob:   Optional[float]

    placed_at:    datetime
    delivered_at: Optional[datetime]
    updated_at:   datetime

    status_logs: list[StatusLogOut] = []

    # Computed
    elapsed_days:    int = 0
    sla_pct:         float = 0.0
    sla_remaining:   int = 0
    sla_status:      str = "ok"   # ok | warn | breach

    model_config = {"from_attributes": True}


class OrderListItem(BaseModel):
    """Lightweight version for list endpoints."""
    id:            int
    customer_name: str
    store_location: str
    lens_type:     LensType
    lens_index:    LensIndex
    stage:         OrderStage
    sla_days:      int
    ai_risk:       Optional[AIRisk]
    placed_at:     datetime
    sla_status:    str
    sla_remaining: int

    model_config = {"from_attributes": True}


class OrderListResponse(BaseModel):
    total:  int
    page:   int
    size:   int
    items:  list[OrderListItem]