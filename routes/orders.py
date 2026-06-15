"""
Orders router — full CRUD + stage updates + dashboard stats.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from schemas.order import (
    OrderCreate, OrderListResponse, OrderOut, OrderUpdate, StageUpdateRequest,
)
from schemas.inventory import InventoryCheckResult
from services import order_service

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.get("/dashboard", summary="Dashboard statistics")
async def dashboard(db: AsyncSession = Depends(get_db)):
    return await order_service.get_dashboard_stats(db)


@router.post("/", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
async def create_order(data: OrderCreate, db: AsyncSession = Depends(get_db)):
    return await order_service.create_order(db, data)


@router.get("/", response_model=OrderListResponse)
async def list_orders(
    stage:      Optional[str] = Query(None, description="Filter by stage"),
    lens_type:  Optional[str] = Query(None, alias="lensType"),
    store:      Optional[str] = Query(None),
    sla_filter: Optional[str] = Query(None, alias="slaStatus", description="ok | warn | breach"),
    search:     Optional[str] = Query(None),
    page:       int = Query(1, ge=1),
    size:       int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    items, total = await order_service.list_orders(
        db, stage=stage, lens_type=lens_type, store=store,
        sla_filter=sla_filter, search=search, page=page, size=size,
    )
    return OrderListResponse(total=total, page=page, size=size, items=items)


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(order_id: int, db: AsyncSession = Depends(get_db)):
    order = await order_service.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.patch("/{order_id}", response_model=OrderOut)
async def update_order(order_id: int, data: OrderUpdate, db: AsyncSession = Depends(get_db)):
    order = await order_service.update_order(db, order_id, data)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.post("/{order_id}/stage", response_model=OrderOut, summary="Update order stage")
async def update_stage(
    order_id: int,
    req: StageUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    order = await order_service.update_order_stage(db, order_id, req)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order(order_id: int, db: AsyncSession = Depends(get_db)):
    deleted = await order_service.delete_order(db, order_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Order not found")


@router.get("/{order_id}/inventory-check", response_model=InventoryCheckResult)
async def inventory_check(order_id: int, db: AsyncSession = Depends(get_db)):
    """Check if lens for this order is in-house."""
    order = await order_service.get_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    result = await order_service.check_lens_inventory(
        db, order.lens_type.value, order.lens_index.value
    )
    return InventoryCheckResult(**result)