from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class LensInventoryOut(BaseModel):
    id:            int
    sku:           str
    lens_type:     str
    lens_index:    str
    coating:       str
    sph_min:       Optional[float]
    sph_max:       Optional[float]
    cyl_max:       Optional[float]
    qty_in_stock:  int
    min_stock:     int
    supplier_name: Optional[str]
    supplier_eta_days: Optional[int]
    is_active:     bool
    updated_at:    datetime
    stock_status:  str = "ok"    # ok | low | out

    model_config = {"from_attributes": True}


class LensInventoryUpdate(BaseModel):
    qty_in_stock:      Optional[int]   = None
    min_stock:         Optional[int]   = None
    supplier_name:     Optional[str]   = None
    supplier_eta_days: Optional[int]   = None
    is_active:         Optional[bool]  = None


class CoatingInventoryOut(BaseModel):
    id:           int
    coating_name: str
    qty_in_stock: int
    min_stock:    int
    unit:         str
    supplier_eta: Optional[str]
    updated_at:   datetime
    stock_status: str = "ok"

    model_config = {"from_attributes": True}


class CoatingInventoryUpdate(BaseModel):
    qty_in_stock: Optional[int] = None
    min_stock:    Optional[int] = None
    supplier_eta: Optional[str] = None


class InventoryCheckResult(BaseModel):
    available:    bool
    qty_in_stock: int
    sku:          Optional[str]
    status:       str      # "in-house" | "low-stock" | "out-of-stock" | "not-stocked"
    message:      str
    extra_days:   int = 0  # extra TAT days if not in-house