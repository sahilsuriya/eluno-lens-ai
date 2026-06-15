"""
Alerts router — SLA breach alerts and AI TAT predictions.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from schemas.alert import AlertOut, AlertMarkRead, TATprediction
from services import alert_service
from services.ai_service import predict_tat
from services.order_service import get_order, list_orders
from utils.sla import elapsed_days

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("/", response_model=list[AlertOut])
async def get_alerts(
    unread_only: bool = Query(False, alias="unreadOnly"),
    page: int = Query(1, ge=1),
    size: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    items, _ = await alert_service.get_alerts(db, unread_only=unread_only, page=page, size=size)
    return items


@router.post("/mark-read")
async def mark_read(body: AlertMarkRead, db: AsyncSession = Depends(get_db)):
    count = await alert_service.mark_alerts_read(db, body.ids)
    return {"marked": count}


@router.post("/scan", summary="Manually trigger SLA scan (also runs on schedule)")
async def trigger_scan():
    await alert_service.scan_and_fire_alerts()
    return {"status": "scan complete"}


@router.get("/tat-predictions", response_model=list[TATprediction], summary="AI TAT predictions for active orders")
async def tat_predictions(
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
):
    orders, _ = await list_orders(db, size=limit)
    active = [o for o in orders if o.stage.value != "Delivered"]
    results = []
    for order in active:
        ai = await predict_tat(order)
        results.append(
            TATprediction(
                order_id=order.id,
                lens_type=order.lens_type.value,
                current_stage=order.stage.value,
                elapsed_days=elapsed_days(order.placed_at),
                sla_days=order.sla_days,
                predicted_tat=ai.get("predicted_tat", order.sla_days),
                breach_prob=ai.get("breach_prob", 0.0),
                risk_level=ai.get("risk_level", "low"),
                ai_reasoning=ai.get("reasoning", ""),
            )
        )
    return results