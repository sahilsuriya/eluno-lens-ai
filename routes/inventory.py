"""
Inventory router — lens and coating stock management.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.inventory import CoatingInventory, LensInventory
from schemas.inventory import (
    CoatingInventoryOut, CoatingInventoryUpdate,
    InventoryCheckResult,
    LensInventoryOut, LensInventoryUpdate,
)
from services.order_service import check_lens_inventory

router = APIRouter(prefix="/inventory", tags=["Inventory"])


def _stock_status(qty: int, min_stock: int) -> str:
    if qty <= 0:
        return "out"
    if qty < min_stock:
        return "low"
    return "ok"


# ── Lens inventory ────────────────────────────────────────────────────────────

@router.get("/lenses", response_model=list[LensInventoryOut])
async def list_lenses(
    lens_type:  str | None = Query(None, alias="lensType"),
    lens_index: str | None = Query(None, alias="lensIndex"),
    db: AsyncSession = Depends(get_db),
):
    q = select(LensInventory).where(LensInventory.is_active == True)  # noqa: E712
    if lens_type:
        q = q.where(LensInventory.lens_type == lens_type)
    if lens_index:
        q = q.where(LensInventory.lens_index == lens_index)
    result = await db.execute(q)
    items = result.scalars().all()
    out = []
    for item in items:
        d = LensInventoryOut.model_validate(item)
        d.stock_status = _stock_status(item.qty_in_stock, item.min_stock)
        out.append(d)
    return out


@router.get("/lenses/{item_id}", response_model=LensInventoryOut)
async def get_lens(item_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LensInventory).where(LensInventory.id == item_id))
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Lens SKU not found")
    d = LensInventoryOut.model_validate(item)
    d.stock_status = _stock_status(item.qty_in_stock, item.min_stock)
    return d


@router.patch("/lenses/{item_id}", response_model=LensInventoryOut)
async def update_lens(item_id: int, data: LensInventoryUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LensInventory).where(LensInventory.id == item_id))
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Lens SKU not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(item, field, value)
    await db.flush()
    d = LensInventoryOut.model_validate(item)
    d.stock_status = _stock_status(item.qty_in_stock, item.min_stock)
    return d


@router.get("/check", response_model=InventoryCheckResult, summary="Check lens availability before ordering")
async def check_inventory(
    lens_type:  str = Query(..., alias="lensType"),
    lens_index: str = Query(..., alias="lensIndex"),
    db: AsyncSession = Depends(get_db),
):
    result = await check_lens_inventory(db, lens_type, lens_index)
    return InventoryCheckResult(**result)


# ── Coating inventory ─────────────────────────────────────────────────────────

@router.get("/coatings", response_model=list[CoatingInventoryOut])
async def list_coatings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CoatingInventory))
    items = result.scalars().all()
    out = []
    for item in items:
        d = CoatingInventoryOut.model_validate(item)
        d.stock_status = _stock_status(item.qty_in_stock, item.min_stock)
        out.append(d)
    return out


@router.patch("/coatings/{item_id}", response_model=CoatingInventoryOut)
async def update_coating(item_id: int, data: CoatingInventoryUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CoatingInventory).where(CoatingInventory.id == item_id))
    item = result.scalars().first()
    if not item:
        raise HTTPException(status_code=404, detail="Coating not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(item, field, value)
    await db.flush()
    d = CoatingInventoryOut.model_validate(item)
    d.stock_status = _stock_status(item.qty_in_stock, item.min_stock)
    return d


@router.get("/reorder-queue", summary="SKUs needing replenishment")
async def reorder_queue(db: AsyncSession = Depends(get_db)):
    """Returns all lens and coating SKUs below minimum stock level."""
    lens_result = await db.execute(
        select(LensInventory).where(
            LensInventory.is_active == True,  # noqa: E712
            LensInventory.qty_in_stock < LensInventory.min_stock,
        )
    )
    coat_result = await db.execute(
        select(CoatingInventory).where(
            CoatingInventory.qty_in_stock < CoatingInventory.min_stock
        )
    )
    lenses   = lens_result.scalars().all()
    coatings = coat_result.scalars().all()

    return {
        "lenses": [
            {
                "sku": i.sku, "lens_type": i.lens_type, "lens_index": i.lens_index,
                "qty_in_stock": i.qty_in_stock, "min_stock": i.min_stock,
                "supplier_name": i.supplier_name, "supplier_eta_days": i.supplier_eta_days,
            }
            for i in lenses
        ],
        "coatings": [
            {
                "coating_name": c.coating_name, "qty_in_stock": c.qty_in_stock,
                "min_stock": c.min_stock, "supplier_eta": c.supplier_eta,
            }
            for c in coatings
        ],
    }