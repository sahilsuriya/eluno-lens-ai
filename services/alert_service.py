"""
Alert service.
- scan_and_fire_alerts(): called by APScheduler every 30 min.
  Scans active orders for SLA breaches / at-risk states and creates SLAAlert rows.
- get_alerts(): returns paginated alerts for the dashboard.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import AsyncSessionLocal
from models.alert import AlertChannel, AlertType, SLAAlert
from models.order import Order, OrderStage
from services.notification_service import (
    build_alert_message, send_email, send_whatsapp,
)
from services.ai_service import predict_tat
from utils.sla import elapsed_days, sla_status

logger = logging.getLogger(__name__)
ALERT_EMAIL = "ops@eluno.co"    # internal ops email


async def _alert_exists(db: AsyncSession, order_id: int, alert_type: AlertType) -> bool:
    """Avoid duplicate alerts for the same order+type within one day."""
    from sqlalchemy import and_, func
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=12)
    result = await db.execute(
        select(SLAAlert).where(
            and_(
                SLAAlert.order_id == order_id,
                SLAAlert.alert_type == alert_type,
                SLAAlert.created_at >= cutoff,
            )
        )
    )
    return result.scalars().first() is not None


async def _fire_alert(
    db: AsyncSession,
    order: Order,
    alert_type: AlertType,
    message: str,
    channel: AlertChannel = AlertChannel.INTERNAL,
) -> None:
    if await _alert_exists(db, order.id, alert_type):
        return

    alert = SLAAlert(
        order_id=order.id,
        alert_type=alert_type,
        channel=channel,
        message=message,
    )
    db.add(alert)

    # Send external notification
    if channel == AlertChannel.WHATSAPP:
        sent = await send_whatsapp(order.customer_phone, message)
        if sent:
            alert.sent = True
            alert.sent_at = datetime.now(timezone.utc)
    elif channel == AlertChannel.EMAIL:
        sent = await send_email(ALERT_EMAIL, f"SLA Alert – Order #{order.id}", f"<p>{message}</p>")
        if sent:
            alert.sent = True
            alert.sent_at = datetime.now(timezone.utc)


async def scan_and_fire_alerts() -> None:
    """Background job: scan all active orders and fire alerts where needed."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Order)
            .where(Order.stage != OrderStage.DELIVERED)
            .options(selectinload(Order.status_logs))
        )
        orders = result.scalars().all()
        logger.info("Alert scan: checking %d active orders", len(orders))

        for order in orders:
            status = sla_status(order.placed_at, order.sla_days)
            elapsed = elapsed_days(order.placed_at)

            # 1. SLA Breach
            if status == "breach":
                msg = build_alert_message(
                    order.id, "SLA Breached",
                    f"{order.lens_type} | Stage: {order.stage.value} | {elapsed}d elapsed (SLA {order.sla_days}d)"
                )
                await _fire_alert(db, order, AlertType.SLA_BREACH, msg, AlertChannel.EMAIL)

            # 2. SLA At Risk (>80%)
            elif status == "warn":
                msg = build_alert_message(
                    order.id, "SLA At Risk",
                    f"{order.lens_type} | Stage: {order.stage.value} | {order.sla_days - elapsed}d remaining"
                )
                await _fire_alert(db, order, AlertType.SLA_AT_RISK, msg, AlertChannel.INTERNAL)

            # 3. AI: predicted breach even though not yet at 80%
            if order.ai_breach_prob and order.ai_breach_prob >= 0.7 and status == "ok":
                ai_result = await predict_tat(order)
                msg = build_alert_message(
                    order.id, "AI Breach Risk",
                    f"AI predicts {ai_result['breach_prob']*100:.0f}% breach probability. "
                    f"Reason: {ai_result['reasoning']}"
                )
                await _fire_alert(db, order, AlertType.SLA_AT_RISK, msg, AlertChannel.INTERNAL)

            # 4. Stage stuck — same stage for > (sla_days / 3) days
            if order.status_logs:
                last_change = order.status_logs[-1].changed_at
                days_in_stage = (datetime.now(timezone.utc) - last_change.replace(tzinfo=timezone.utc)).days
                stuck_threshold = max(1, order.sla_days // 3)
                if days_in_stage >= stuck_threshold and order.stage not in (OrderStage.PLACED, OrderStage.DELIVERED):
                    msg = build_alert_message(
                        order.id, "Stage Stuck",
                        f"Order has been in '{order.stage.value}' for {days_in_stage} days."
                    )
                    await _fire_alert(db, order, AlertType.STAGE_STUCK, msg, AlertChannel.INTERNAL)

        await db.commit()
        logger.info("Alert scan complete")


async def get_alerts(
    db: AsyncSession,
    unread_only: bool = False,
    page: int = 1,
    size: int = 50,
) -> tuple[list[SLAAlert], int]:
    from sqlalchemy import func
    q = select(SLAAlert)
    if unread_only:
        q = q.where(SLAAlert.read == False)  # noqa: E712
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    q = q.order_by(SLAAlert.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(q)
    return result.scalars().all(), total


async def mark_alerts_read(db: AsyncSession, ids: list[int]) -> int:
    result = await db.execute(select(SLAAlert).where(SLAAlert.id.in_(ids)))
    alerts = result.scalars().all()
    for a in alerts:
        a.read = True
    await db.flush()
    return len(alerts)