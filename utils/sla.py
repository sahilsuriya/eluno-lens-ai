"""
SLA calculation helpers.
All time math uses UTC. 'Elapsed days' is calendar days for simplicity;
swap for a working-day calendar library if needed.
"""
from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def elapsed_days(placed_at: datetime) -> int:
    delta = utcnow() - placed_at.replace(tzinfo=timezone.utc)
    return max(0, delta.days)


def sla_pct(placed_at: datetime, sla_days: int) -> float:
    """Percentage of SLA window consumed (0-100, can exceed 100)."""
    if sla_days <= 0:
        return 100.0
    return round((elapsed_days(placed_at) / sla_days) * 100, 1)


def sla_remaining(placed_at: datetime, sla_days: int) -> int:
    """Days remaining before SLA breach (negative = already breached)."""
    return sla_days - elapsed_days(placed_at)


def sla_status(placed_at: datetime, sla_days: int) -> str:
    """Return 'ok' | 'warn' | 'breach'."""
    pct = sla_pct(placed_at, sla_days)
    if pct >= 100:
        return "breach"
    if pct >= 80:
        return "warn"
    return "ok"