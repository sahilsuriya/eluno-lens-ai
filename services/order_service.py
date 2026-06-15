"""
Order service — all business logic for creating, updating, and querying orders.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import get_settings
from models.order import InvStatus, Order, OrderStage, OrderStatusLog
from models.alert import AlertChannel, AlertType, SLAAlert
from models.inventory import LensInventory
from schemas.order import OrderCreate, OrderUpdate, StageUpdateRequest
from services.ai_service import predict_tat
from services.notification_service import (
    build_alert_message, send_email, send_whatsapp,
)
from utils.sla import elapsed_days, sla_pct, sla_remaining, sla_status

settings = get_settings()


def _sla_for_lens(lens_type: str) -> int:
    return settings.sla_map.get(lens_type, 3)


def _enrich(order: Order) -> Order:
    """Attach computed SLA fields as plain attributes (not persisted)."""
    order.elapsed_days  = elapsed_days(order.placed_at)
    order.sla_pct       = sla_pct(order.placed_at, order.sla_days)
    order.sla_remaining = sla_remaining(order.placed_at, order.sla_days)
    order.sla_status    = sla_status(order.placed_at, order.sla_days)
    return order


# ── Inventory check ───────────────────────────────────────────────────────────

async def check_lens_inventory(
    db: AsyncSession, lens_type: str, lens_index: str
) -> dict:
    result = await db.execute(
        select(LensInventory).where(
            LensInventory.lens_type == lens_type,
            LensInventory.lens_index == lens_index,
            LensInventory.is_active == True,  # noqa: E712
        )
    )
    item = result.scalars().first()

    if not item:
        return {
            "available": False, "qty_in_stock": 0, "sku": None,
            "status": "not-stocked",
            "message": "Lens not stocked. Will be sourced externally (+1–2 days).",
            "extra_days": 2,
        }

    if item.qty_in_stock <= 0:
        return {
            "available": False, "qty_in_stock": 0, "sku": item.sku,
            "status": "out-of-stock",
            "message": f"Out of stock (SKU {item.sku}). Sourcing required (+{item.supplier_eta_days or 2} days).",
            "extra_days": item.supplier_eta_days or 2,
        }

    if item.qty_in_stock < item.min_stock:
        return {
            "available": True, "qty_in_stock": item.qty_in_stock, "sku": item.sku,
            "status": "low-stock",
            "message": f"Low stock: {item.qty_in_stock} units remaining (min {item.min_stock}). Order can proceed.",
            "extra_days": 0,
        }

    return {
        "available": True, "qty_in_stock": item.qty_in_stock, "sku": item.sku,
        "status": "in-house",
        "message": f"In stock: {item.qty_in_stock} units. Order can be fulfilled immediately.",
        "extra_days": 0,
    }


# ── CRUD ──────────────────────────────────────────────────────────────────────

async def create_order(db: AsyncSession, data: OrderCreate) -> Order:
    sla = _sla_for_lens(data.lens_type.value)

    # Check inventory to decide inv_status
    inv_check = await check_lens_inventory(db, data.lens_type.value, data.lens_index.value)
    inv_status = InvStatus.IN_HOUSE if inv_check["available"] else InvStatus.SOURCED

    order = Order(
        customer_name=data.customer_name,
        customer_phone=data.customer_phone,
        store_location=data.store_location,
        frame_reference=data.frame_reference,
        lens_type=data.lens_type,
        lens_index=data.lens_index,
        coating=data.coating,
        tint=data.tint,
        r_sph=data.r_sph, r_cyl=data.r_cyl, r_axis=data.r_axis,
        l_sph=data.l_sph, l_cyl=data.l_cyl, l_axis=data.l_axis,
        pd=data.pd,
        sla_days=sla,
        stage=OrderStage.PLACED,
        inv_status=inv_status,
    )
    db.add(order)
    await db.flush()   # get ID

    # Initial status log
    log = OrderStatusLog(
        order_id=order.id,
        from_stage=None,
        to_stage=OrderStage.PLACED.value,
        reason="Order placed",
    )
    db.add(log)

    # Decrement inventory
    if inv_status == InvStatus.IN_HOUSE:
        await _decrement_lens_stock(db, data.lens_type.value, data.lens_index.value)

    # Kick off AI prediction (best-effort)
    try:
        ai = await predict_tat(order)
        order.ai_risk          = ai.get("risk_level", "low")
        order.ai_predicted_tat = ai.get("predicted_tat")
        order.ai_breach_prob   = ai.get("breach_prob")
    except Exception:
        pass

    await db.flush()
    return _enrich(order)


async def _decrement_lens_stock(db: AsyncSession, lens_type: str, lens_index: str) -> None:
    result = await db.execute(
        select(LensInventory).where(
            LensInventory.lens_type == lens_type,
            LensInventory.lens_index == lens_index,
            LensInventory.is_active == True,  # noqa: E712
        )
    )
    item = result.scalars().first()
    if item and item.qty_in_stock > 0:
        item.qty_in_stock -= 1


async def get_order(db: AsyncSession, order_id: int) -> Optional[Order]:
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.status_logs), selectinload(Order.alerts))
    )
    order = result.scalars().first()
    return _enrich(order) if order else None


async def list_orders(
    db: AsyncSession,
    stage: Optional[str] = None,
    lens_type: Optional[str] = None,
    store: Optional[str] = None,
    sla_filter: Optional[str] = None,   # ok | warn | breach
    search: Optional[str] = None,
    page: int = 1,
    size: int = 50,
) -> tuple[list[Order], int]:
    q = select(Order).options(selectinload(Order.status_logs))

    if stage:
        q = q.where(Order.stage == stage)
    if lens_type:
        q = q.where(Order.lens_type == lens_type)
    if store:
        q = q.where(Order.store_location == store)
    if search:
        like = f"%{search}%"
        q = q.where(
            (Order.customer_name.ilike(like)) |
            (Order.customer_phone.ilike(like)) |
            (Order.id.cast("varchar").ilike(like))
        )

    total_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = total_result.scalar_one()

    q = q.order_by(Order.placed_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(q)
    orders = result.scalars().all()

    enriched = [_enrich(o) for o in orders]

    # SLA filter applied after enrichment (computed field)
    if sla_filter:
        enriched = [o for o in enriched if o.sla_status == sla_filter]
        total = len(enriched)

    return enriched, total


async def update_order_stage(
    db: AsyncSession,
    order_id: int,
    req: StageUpdateRequest,
) -> Optional[Order]:
    result = await db.execute(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.status_logs), selectinload(Order.alerts))
    )
    order = result.scalars().first()
    if not order:
        return None

    prev_stage = order.stage.value
    order.stage = req.stage

    if req.stage == OrderStage.DELIVERED:
        order.delivered_at = datetime.now(timezone.utc)

    log = OrderStatusLog(
        order_id=order.id,
        from_stage=prev_stage,
        to_stage=req.stage.value,
        reason=req.reason,
        changed_by=req.changed_by,
    )
    db.add(log)

    # Re-run AI prediction after stage change
    try:
        ai = await predict_tat(order)
        order.ai_risk          = ai.get("risk_level", order.ai_risk)
        order.ai_predicted_tat = ai.get("predicted_tat", order.ai_predicted_tat)
        order.ai_breach_prob   = ai.get("breach_prob", order.ai_breach_prob)
    except Exception:
        pass

    # Send notification if requested
    if req.alert_channel and req.reason:
        msg = build_alert_message(
            order.id,
            f"Stage → {req.stage.value}",
            req.reason,
        )
        if req.alert_channel == "whatsapp":
            await send_whatsapp(order.customer_phone, msg)
        elif req.alert_channel == "email":
            pass  # customer email not in model yet; extend as needed

    await db.flush()
    return _enrich(order)


async def update_order(
    db: AsyncSession, order_id: int, data: OrderUpdate
) -> Optional[Order]:
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalars().first()
    if not order:
        return None
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(order, field, value)
    await db.flush()
    return _enrich(order)


async def delete_order(db: AsyncSession, order_id: int) -> bool:
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalars().first()
    if not order:
        return False
    await db.delete(order)
    return True


# ── Dashboard stats ───────────────────────────────────────────────────────────

async def get_dashboard_stats(db: AsyncSession) -> dict:
    all_result = await db.execute(select(Order).options(selectinload(Order.status_logs)))
    all_orders = [_enrich(o) for o in all_result.scalars().all()]

    active = [o for o in all_orders if o.stage != OrderStage.DELIVERED]
    delivered = [o for o in all_orders if o.stage == OrderStage.DELIVERED]
    breached = [o for o in active if o.sla_status == "breach"]
    at_risk  = [o for o in active if o.sla_status == "warn"]

    avg_tat = 0.0
    if delivered:
        tats = [elapsed_days(o.placed_at) for o in delivered]
        avg_tat = round(sum(tats) / len(tats), 1)

    stage_counts: dict[str, int] = {}
    for o in all_orders:
        stage_counts[o.stage.value] = stage_counts.get(o.stage.value, 0) + 1

    return {
        "active_orders": len(active),
        "delivered_this_month": len(delivered),
        "sla_breaches": len(breached),
        "at_risk": len(at_risk),
        "avg_tat_days": avg_tat,
        "stage_distribution": stage_counts,
        "breach_orders": [{"id": o.id, "customer": o.customer_name, "stage": o.stage.value} for o in breached],
        "risk_orders": [{"id": o.id, "customer": o.customer_name, "stage": o.stage.value, "ai_risk": o.ai_risk} for o in at_risk],
    }